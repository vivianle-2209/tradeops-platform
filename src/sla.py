"""
TradeOps persistent SLA lifecycle processing.

Reads:
    data/processed/trade_breaks_scored.csv

Writes:
    data/processed/trade_breaks_sla.csv
    data/state/break_lifecycle.csv

A break is uniquely identified by:
    dedup_key = trade_id:exception_type

The lifecycle state persists between pipeline runs so that
first_seen_at and age_minutes do not reset every run.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


# ==================================================
# Paths
# ==================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "trade_breaks_scored.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "trade_breaks_sla.csv"
)

STATE_PATH = (
    PROJECT_ROOT
    / "data"
    / "state"
    / "break_lifecycle.csv"
)


# ==================================================
# SLA configuration
# ==================================================

SLA_MINUTES = {
    "CRITICAL": 15,
    "HIGH": 30,
    "MEDIUM": 60,
    "LOW": 240,
}

SLA_AT_RISK_FRACTION = 0.75

SLA_PRIORITY = {
    "BREACHED": 1,
    "AT_RISK": 2,
    "WITHIN_SLA": 3,
    "UNKNOWN": 4,
    "CLOSED": 5,
}


LIFECYCLE_COLUMNS = [
    "dedup_key",
    "break_id",
    "trade_id",
    "exception_type",
    "severity",
    "first_seen_at",
    "last_seen_at",
    "resolved_at",
    "break_status",
]


# ==================================================
# Time helpers
# ==================================================

def utc_now() -> pd.Timestamp:
    """
    Return current UTC time at whole-second precision.

    Whole-second precision avoids dtype conflicts between timestamps
    loaded from CSV and newly generated timestamps.
    """

    return (
        pd.Timestamp.now(
            tz="UTC"
        )
        .floor("s")
    )


def normalize_datetime_series(
    series: pd.Series,
) -> pd.Series:
    """
    Normalise any datetime-like Series to datetime64[ns, UTC].
    """

    values = pd.to_datetime(
        series,
        errors="coerce",
        utc=True,
    )

    return values.astype(
        "datetime64[ns, UTC]"
    )


def normalize_datetime_columns(
    frame: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """
    Guarantee consistent UTC nanosecond timestamp columns.
    """

    frame = frame.copy()

    for column in columns:

        if column not in frame.columns:

            frame[column] = pd.Series(
                pd.NaT,
                index=frame.index,
                dtype="datetime64[ns, UTC]",
            )

        else:

            frame[column] = (
                normalize_datetime_series(
                    frame[column]
                )
            )

    return frame


# ==================================================
# Atomic CSV writer
# ==================================================

def write_csv_atomic(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    """
    Write through a temporary file before replacing the destination.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    frame.to_csv(
        temp_path,
        index=False,
    )

    os.replace(
        temp_path,
        path,
    )


# ==================================================
# Lifecycle state
# ==================================================

def empty_lifecycle_state() -> pd.DataFrame:
    """
    Return an empty lifecycle dataframe with the expected schema.
    """

    frame = pd.DataFrame(
        columns=LIFECYCLE_COLUMNS
    )

    return normalize_datetime_columns(
        frame,
        [
            "first_seen_at",
            "last_seen_at",
            "resolved_at",
        ],
    )


def load_lifecycle_state() -> pd.DataFrame:
    """
    Load previously persisted lifecycle state.
    """

    if not STATE_PATH.exists():
        return empty_lifecycle_state()

    try:

        state = pd.read_csv(
            STATE_PATH
        )

    except pd.errors.EmptyDataError:

        return empty_lifecycle_state()


    for column in LIFECYCLE_COLUMNS:

        if column not in state.columns:
            state[column] = pd.NA


    state = state[
        LIFECYCLE_COLUMNS
    ].copy()


    state = normalize_datetime_columns(
        state,
        [
            "first_seen_at",
            "last_seen_at",
            "resolved_at",
        ],
    )


    if not state.empty:

        state["dedup_key"] = (
            state["dedup_key"]
            .astype("string")
        )

        state = (
            state
            .dropna(
                subset=[
                    "dedup_key"
                ]
            )
            .drop_duplicates(
                subset=[
                    "dedup_key"
                ],
                keep="last",
            )
            .reset_index(
                drop=True
            )
        )


    return state


# ==================================================
# Current break preparation
# ==================================================

def prepare_breaks(
    breaks: pd.DataFrame,
) -> pd.DataFrame:
    """
    Standardise scored trade-break data before SLA processing.
    """

    df = breaks.copy()

    if df.empty:
        return df


    required_columns = [
        "trade_id",
        "exception_type",
        "severity",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            "Missing required SLA input columns: "
            + ", ".join(
                missing
            )
        )


    # --------------------------------------------------
    # Standardise identifiers
    # --------------------------------------------------

    df["trade_id"] = (
        df["trade_id"]
        .astype(str)
        .str.strip()
    )

    df["exception_type"] = (
        df["exception_type"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["severity"] = (
        df["severity"]
        .astype(str)
        .str.strip()
        .str.upper()
    )


    # --------------------------------------------------
    # Canonical dedup key
    # --------------------------------------------------

    canonical_key = (
        df["trade_id"]
        + ":"
        + df["exception_type"]
    )


    if "dedup_key" not in df.columns:

        df["dedup_key"] = canonical_key

    else:

        missing_key = (
            df["dedup_key"].isna()
            |
            df["dedup_key"]
            .astype(str)
            .str.strip()
            .eq("")
        )

        df.loc[
            missing_key,
            "dedup_key",
        ] = canonical_key.loc[
            missing_key
        ]

        df["dedup_key"] = (
            df["dedup_key"]
            .astype(str)
            .str.strip()
        )


    # --------------------------------------------------
    # Break ID fallback
    # --------------------------------------------------

    if "break_id" not in df.columns:

        df["break_id"] = [
            f"BRK-{index:06d}"
            for index
            in range(
                1,
                len(df) + 1,
            )
        ]


    # --------------------------------------------------
    # Numeric fields
    # --------------------------------------------------

    if "severity_score" not in df.columns:
        df["severity_score"] = np.nan

    df["severity_score"] = pd.to_numeric(
        df["severity_score"],
        errors="coerce",
    )


    if "affected_notional" in df.columns:

        df["affected_notional"] = pd.to_numeric(
            df["affected_notional"],
            errors="coerce",
        )


    return df


# ==================================================
# Lifecycle logic
# ==================================================

def apply_lifecycle_state(
    current_breaks: pd.DataFrame,
    now: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Merge the latest break snapshot with persisted lifecycle state.

    Current incidents:
        OPEN
        preserve first_seen_at
        update last_seen_at

    Incidents that disappeared:
        RESOLVED
        resolved_at set once
    """

    df = current_breaks.copy()

    now = (
        pd.Timestamp(now)
        .floor("s")
    )

    if now.tzinfo is None:

        now = now.tz_localize(
            "UTC"
        )

    else:

        now = now.tz_convert(
            "UTC"
        )


    state = load_lifecycle_state()


    # ==================================================
    # No current breaks
    # ==================================================

    if df.empty:

        if state.empty:
            return df, state


        state = normalize_datetime_columns(
            state,
            [
                "first_seen_at",
                "last_seen_at",
                "resolved_at",
            ],
        )


        open_mask = (
            state["break_status"]
            .astype(str)
            .eq("OPEN")
        )

        newly_resolved = (
            open_mask
            &
            state["resolved_at"]
            .isna()
        )


        state.loc[
            newly_resolved,
            "resolved_at",
        ] = now


        state.loc[
            open_mask,
            "break_status",
        ] = "RESOLVED"


        return df, state


    # ==================================================
    # Previous first-seen lookup
    # ==================================================

    previous_first_seen = {}

    if not state.empty:

        previous_first_seen = (
            state
            .set_index(
                "dedup_key"
            )[
                "first_seen_at"
            ]
            .to_dict()
        )


    # ==================================================
    # Current break lifecycle
    # ==================================================

    first_seen_values = []


    for dedup_key in df[
        "dedup_key"
    ]:

        previous = (
            previous_first_seen.get(
                dedup_key
            )
        )


        if (
            previous is None
            or pd.isna(previous)
        ):

            first_seen_values.append(
                now
            )

        else:

            first_seen_values.append(
                previous
            )


    df["first_seen_at"] = (
        normalize_datetime_series(
            pd.Series(
                first_seen_values,
                index=df.index,
            )
        )
    )


    df["last_seen_at"] = pd.Series(
        now,
        index=df.index,
        dtype="datetime64[ns, UTC]",
    )


    df["resolved_at"] = pd.Series(
        pd.NaT,
        index=df.index,
        dtype="datetime64[ns, UTC]",
    )


    df["detected_at"] = (
        df["first_seen_at"]
    )


    df["break_status"] = "OPEN"


    current_state = pd.DataFrame(
        {
            "dedup_key":
                df["dedup_key"],

            "break_id":
                df["break_id"],

            "trade_id":
                df["trade_id"],

            "exception_type":
                df["exception_type"],

            "severity":
                df["severity"],

            "first_seen_at":
                df["first_seen_at"],

            "last_seen_at":
                df["last_seen_at"],

            "resolved_at":
                df["resolved_at"],

            "break_status":
                df["break_status"],
        }
    )


    current_state = normalize_datetime_columns(
        current_state,
        [
            "first_seen_at",
            "last_seen_at",
            "resolved_at",
        ],
    )


    # ==================================================
    # Find previously open breaks that disappeared
    # ==================================================

    current_keys = set(
        current_state[
            "dedup_key"
        ]
        .dropna()
        .astype(str)
    )


    if state.empty:

        old_only = empty_lifecycle_state()

    else:

        old_only = (
            state[
                ~state["dedup_key"]
                .astype(str)
                .isin(
                    current_keys
                )
            ]
            .copy()
        )


    if not old_only.empty:

        old_only = normalize_datetime_columns(
            old_only,
            [
                "first_seen_at",
                "last_seen_at",
                "resolved_at",
            ],
        )


        was_open = (
            old_only["break_status"]
            .astype(str)
            .eq("OPEN")
        )


        newly_resolved = (
            was_open
            &
            old_only["resolved_at"]
            .isna()
        )


        old_only.loc[
            newly_resolved,
            "resolved_at",
        ] = now


        old_only.loc[
            was_open,
            "break_status",
        ] = "RESOLVED"


    # ==================================================
    # Complete lifecycle state
    # ==================================================

    complete_state = pd.concat(
        [
            current_state,
            old_only,
        ],
        ignore_index=True,
    )


    complete_state = (
        complete_state
        .drop_duplicates(
            subset=[
                "dedup_key"
            ],
            keep="first",
        )
        .reset_index(
            drop=True
        )
    )


    complete_state = normalize_datetime_columns(
        complete_state,
        [
            "first_seen_at",
            "last_seen_at",
            "resolved_at",
        ],
    )


    return df, complete_state


# ==================================================
# SLA classification
# ==================================================

def classify_sla(
    row: pd.Series,
) -> str:
    """
    Calculate the operational SLA classification.
    """

    if row.get(
        "break_status"
    ) != "OPEN":

        return "CLOSED"


    sla_minutes = row.get(
        "sla_minutes"
    )

    age_minutes = row.get(
        "age_minutes"
    )


    if (
        pd.isna(sla_minutes)
        or pd.isna(age_minutes)
    ):

        return "UNKNOWN"


    if age_minutes > sla_minutes:

        return "BREACHED"


    if age_minutes >= (
        sla_minutes
        * SLA_AT_RISK_FRACTION
    ):

        return "AT_RISK"


    return "WITHIN_SLA"


# ==================================================
# Main SLA transformation
# ==================================================

def add_sla_tracking(
    breaks: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply persistent lifecycle state and SLA calculations.
    """

    df = prepare_breaks(
        breaks
    )


    now = utc_now()


    df, lifecycle_state = (
        apply_lifecycle_state(
            df,
            now,
        )
    )


    if df.empty:
        return df, lifecycle_state


    # --------------------------------------------------
    # Break age
    # --------------------------------------------------

    df["first_seen_at"] = (
        normalize_datetime_series(
            df["first_seen_at"]
        )
    )


    now_series = pd.Series(
        now,
        index=df.index,
        dtype="datetime64[ns, UTC]",
    )


    df["age_minutes"] = (
        (
            now_series
            - df["first_seen_at"]
        )
        .dt.total_seconds()
        .div(60)
        .clip(
            lower=0
        )
    )


    # --------------------------------------------------
    # SLA target
    # --------------------------------------------------

    df["sla_minutes"] = (
        df["severity"]
        .map(
            SLA_MINUTES
        )
    )


    df["sla_minutes"] = pd.to_numeric(
        df["sla_minutes"],
        errors="coerce",
    )


    # --------------------------------------------------
    # SLA remaining
    # --------------------------------------------------

    df["sla_remaining_minutes"] = (
        df["sla_minutes"]
        - df["age_minutes"]
    )


    # --------------------------------------------------
    # SLA consumed %
    # --------------------------------------------------

    df["sla_consumed_pct"] = np.where(
        (
            df["sla_minutes"]
            .notna()
            &
            df["sla_minutes"]
            .gt(0)
        ),
        (
            df["age_minutes"]
            / df["sla_minutes"]
            * 100
        ),
        np.nan,
    )


    # --------------------------------------------------
    # SLA status
    # --------------------------------------------------

    df["sla_status"] = (
        df.apply(
            classify_sla,
            axis=1,
        )
    )


    # --------------------------------------------------
    # SLA priority
    # --------------------------------------------------

    df["sla_priority"] = (
        df["sla_status"]
        .map(
            SLA_PRIORITY
        )
        .fillna(
            SLA_PRIORITY[
                "UNKNOWN"
            ]
        )
        .astype(int)
    )


    # --------------------------------------------------
    # Sort by urgency
    # --------------------------------------------------

    sort_columns = [
        "sla_priority",
        "severity_score",
        "age_minutes",
    ]

    ascending = [
        True,
        False,
        False,
    ]


    if "affected_notional" in df.columns:

        sort_columns.append(
            "affected_notional"
        )

        ascending.append(
            False
        )


    df = (
        df
        .sort_values(
            by=sort_columns,
            ascending=ascending,
            na_position="last",
        )
        .reset_index(
            drop=True
        )
    )


    # --------------------------------------------------
    # Operational priority rank
    # --------------------------------------------------

    df["priority_rank"] = (
        np.arange(
            1,
            len(df) + 1,
        )
    )


    return df, lifecycle_state


# ==================================================
# Entry point
# ==================================================

def main() -> None:

    if not INPUT_PATH.exists():

        raise FileNotFoundError(
            (
                "SLA input file not found: "
                f"{INPUT_PATH}"
            )
        )


    breaks = pd.read_csv(
        INPUT_PATH
    )


    breaks_sla, lifecycle_state = (
        add_sla_tracking(
            breaks
        )
    )


    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    write_csv_atomic(
        lifecycle_state,
        STATE_PATH,
    )


    write_csv_atomic(
        breaks_sla,
        OUTPUT_PATH,
    )


    # --------------------------------------------------
    # Console summary
    # --------------------------------------------------

    print()
    print(
        "TradeOps SLA processing complete"
    )
    print(
        "-" * 50
    )


    print(
        f"Current breaks: "
        f"{len(breaks_sla):,}"
    )


    print(
        f"Lifecycle records: "
        f"{len(lifecycle_state):,}"
    )


    if not lifecycle_state.empty:

        open_count = int(
            lifecycle_state[
                "break_status"
            ]
            .astype(str)
            .eq("OPEN")
            .sum()
        )


        resolved_count = int(
            lifecycle_state[
                "break_status"
            ]
            .astype(str)
            .eq("RESOLVED")
            .sum()
        )


        print(
            f"Lifecycle OPEN: "
            f"{open_count:,}"
        )

        print(
            f"Lifecycle RESOLVED: "
            f"{resolved_count:,}"
        )


    if not breaks_sla.empty:

        print()
        print(
            "SLA status distribution:"
        )

        print(
            breaks_sla[
                "sla_status"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )


        print()
        print(
            "Highest urgency breaks:"
        )


        display_columns = [
            "priority_rank",
            "break_id",
            "trade_id",
            "symbol_exec",
            "exception_type",
            "severity",
            "severity_score",
            "age_minutes",
            "sla_minutes",
            "sla_remaining_minutes",
            "sla_status",
            "break_status",
        ]


        display_columns = [
            column
            for column
            in display_columns
            if column
            in breaks_sla.columns
        ]


        print(
            breaks_sla[
                display_columns
            ]
            .head(10)
            .to_string(
                index=False
            )
        )


    print()
    print(
        f"SLA output: {OUTPUT_PATH}"
    )

    print(
        f"Lifecycle state: {STATE_PATH}"
    )


if __name__ == "__main__":
    main()