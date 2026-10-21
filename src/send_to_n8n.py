from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv


# --------------------------------------------------
# Environment
# --------------------------------------------------

load_dotenv()

N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL"
)


# --------------------------------------------------
# Paths
# --------------------------------------------------

INPUT_PATH = Path(
    "data/processed/"
    "trade_breaks_sla.csv"
)

STATE_PATH = Path(
    "data/state/"
    "dispatch_state.csv"
)


# --------------------------------------------------
# Dispatch configuration
# --------------------------------------------------

ELIGIBLE_SEVERITIES = {
    "HIGH",
    "CRITICAL",
}


STATE_COLUMNS = [
    "dedup_key",
    "last_dispatched_at",
    "last_dispatched_severity",
    "last_dispatched_sla_status",
    "last_dispatched_break_status",
    "dispatch_attempts",
    "dispatch_status",
    "last_dispatch_error",
]


# --------------------------------------------------
# JSON-safe conversion
# --------------------------------------------------

def json_safe(value):
    """
    Convert pandas / NumPy values into JSON-safe
    native Python values.

    NaN / pd.NA / NaT -> None
    Timestamp          -> ISO 8601
    NumPy scalar       -> Python scalar
    """

    if value is None:
        return None


    try:

        if pd.isna(value):
            return None

    except (
        TypeError,
        ValueError,
    ):

        pass


    if isinstance(
        value,
        pd.Timestamp,
    ):

        return (
            value.isoformat()
        )


    if hasattr(
        value,
        "item",
    ):

        try:

            return (
                value.item()
            )

        except Exception:

            pass


    return value


def clean_payload(value):
    """
    Recursively convert nested payload values into
    JSON-compliant Python objects.
    """

    if isinstance(
        value,
        dict,
    ):

        return {
            key: clean_payload(item)
            for key, item
            in value.items()
        }


    if isinstance(
        value,
        list,
    ):

        return [
            clean_payload(item)
            for item
            in value
        ]


    return json_safe(
        value
    )


# --------------------------------------------------
# Dispatch state
# --------------------------------------------------

def load_dispatch_state() -> pd.DataFrame:

    if not STATE_PATH.exists():

        return pd.DataFrame(
            columns=STATE_COLUMNS
        )


    state = pd.read_csv(
        STATE_PATH
    )


    for column in STATE_COLUMNS:

        if column not in state.columns:

            state[column] = (
                pd.NA
            )


    state[
        "last_dispatched_at"
    ] = pd.to_datetime(
        state[
            "last_dispatched_at"
        ],
        errors="coerce",
        utc=True,
    )


    return state[
        STATE_COLUMNS
    ].copy()


def save_dispatch_state(
    state: pd.DataFrame,
) -> None:

    STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    for column in STATE_COLUMNS:

        if column not in state.columns:

            state[column] = (
                pd.NA
            )


    state[
        STATE_COLUMNS
    ].to_csv(
        STATE_PATH,
        index=False,
    )


# --------------------------------------------------
# Dispatch decision
# --------------------------------------------------

def should_dispatch(
    row: pd.Series,
    previous: pd.Series | None,
) -> bool:
    """
    Send when:

    - new incident
    - previous attempt failed
    - severity changed
    - SLA status changed
    - lifecycle status changed

    Otherwise skip duplicate unchanged events.
    """

    if previous is None:
        return True


    previous_status = str(
        previous.get(
            "dispatch_status",
            "",
        )
    ).upper()


    # Retry failures automatically
    if previous_status == "FAILED":
        return True


    current_severity = str(
        row.get(
            "severity"
        )
    )

    old_severity = str(
        previous.get(
            "last_dispatched_severity"
        )
    )


    current_sla = str(
        row.get(
            "sla_status"
        )
    )

    old_sla = str(
        previous.get(
            "last_dispatched_sla_status"
        )
    )


    current_break_status = str(
        row.get(
            "break_status"
        )
    )

    old_break_status = str(
        previous.get(
            "last_dispatched_break_status"
        )
    )


    return any(
        [
            (
                current_severity
                != old_severity
            ),
            (
                current_sla
                != old_sla
            ),
            (
                current_break_status
                != old_break_status
            ),
        ]
    )


# --------------------------------------------------
# Payload
# --------------------------------------------------

def build_payload(
    row: pd.Series,
) -> dict:
    """
    Build the TradeOps -> n8n event.

    TradeOps remains authoritative for:
    exception_type, severity, lifecycle and SLA.
    """

    payload = {

        "source": (
            "TRADEOPS"
        ),


        # ------------------------------------------
        # Identity
        # ------------------------------------------

        "break_id": (
            row.get(
                "break_id"
            )
        ),

        "dedup_key": (
            row.get(
                "dedup_key"
            )
        ),

        "trade_id": (
            row.get(
                "trade_id"
            )
        ),

        "exception_type": (
            row.get(
                "exception_type"
            )
        ),


        # ------------------------------------------
        # Trade
        # ------------------------------------------

        "trade": {

            "symbol": (
                row.get(
                    "symbol_exec"
                )
            ),

            "side": (
                row.get(
                    "side_exec"
                )
            ),

            "venue": (
                row.get(
                    "venue"
                )
            ),

            "account": (
                row.get(
                    "account_exec"
                )
            ),

            "currency": (
                row.get(
                    "currency_exec"
                )
            ),
        },


        # ------------------------------------------
        # Reconciliation evidence
        # ------------------------------------------

        "reconciliation": {

            "execution_quantity": (
                row.get(
                    "quantity_exec"
                )
            ),

            "clearing_quantity": (
                row.get(
                    "quantity_clear"
                )
            ),

            "quantity_difference": (
                row.get(
                    "quantity_difference"
                )
            ),

            "execution_price": (
                row.get(
                    "price_exec"
                )
            ),

            "clearing_price": (
                row.get(
                    "price_clear"
                )
            ),

            "price_difference": (
                row.get(
                    "price_difference"
                )
            ),

            "execution_side": (
                row.get(
                    "side_exec"
                )
            ),

            "clearing_side": (
                row.get(
                    "side_clear"
                )
            ),

            "execution_account": (
                row.get(
                    "account_exec"
                )
            ),

            "clearing_account": (
                row.get(
                    "account_clear"
                )
            ),

            "execution_currency": (
                row.get(
                    "currency_exec"
                )
            ),

            "clearing_currency": (
                row.get(
                    "currency_clear"
                )
            ),
        },


        # ------------------------------------------
        # Exposure
        # ------------------------------------------

        "exposure": {

            "execution_notional": (
                row.get(
                    "execution_notional"
                )
            ),

            "affected_notional": (
                row.get(
                    "affected_notional"
                )
            ),
        },


        # ------------------------------------------
        # Clearing
        # ------------------------------------------

        "clearing": {

            "status": (
                row.get(
                    "clearing_status"
                )
            ),

            "latency_seconds": (
                row.get(
                    "clearing_latency_seconds"
                )
            ),

            "record_count": (
                row.get(
                    "clearing_record_count"
                )
            ),

            "timestamp": (
                row.get(
                    "clearing_timestamp"
                )
            ),
        },


        # ------------------------------------------
        # Risk
        # ------------------------------------------

        "risk": {

            "severity_score": (
                row.get(
                    "severity_score"
                )
            ),

            "severity": (
                row.get(
                    "severity"
                )
            ),

            "priority_rank": (
                row.get(
                    "priority_rank"
                )
            ),
        },


        # ------------------------------------------
        # SLA
        # ------------------------------------------

        "sla": {

            "age_minutes": (
                row.get(
                    "age_minutes"
                )
            ),

            "sla_minutes": (
                row.get(
                    "sla_minutes"
                )
            ),

            "remaining_minutes": (
                row.get(
                    "sla_remaining_minutes"
                )
            ),

            "consumed_pct": (
                row.get(
                    "sla_consumed_pct"
                )
            ),

            "status": (
                row.get(
                    "sla_status"
                )
            ),
        },


        # ------------------------------------------
        # Lifecycle
        # ------------------------------------------

        "lifecycle": {

            "detected_at": (
                row.get(
                    "detected_at"
                )
            ),

            "first_seen_at": (
                row.get(
                    "first_seen_at"
                )
            ),

            "last_seen_at": (
                row.get(
                    "last_seen_at"
                )
            ),

            "resolved_at": (
                row.get(
                    "resolved_at"
                )
            ),

            "break_status": (
                row.get(
                    "break_status"
                )
            ),
        },
    }


    return clean_payload(
        payload
    )


# --------------------------------------------------
# POST one incident
# --------------------------------------------------

def send_break(
    payload: dict,
) -> requests.Response:

    response = requests.post(
        N8N_WEBHOOK_URL,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    return response


# --------------------------------------------------
# Attempt number
# --------------------------------------------------

def next_attempt_number(
    previous: pd.Series | None,
) -> int:

    if previous is None:
        return 1


    value = previous.get(
        "dispatch_attempts",
        0,
    )


    try:

        if pd.isna(value):
            value = 0

        return (
            int(value)
            + 1
        )

    except (
        TypeError,
        ValueError,
    ):

        return 1


# --------------------------------------------------
# Main dispatch
# --------------------------------------------------

def dispatch_breaks() -> dict:

    if not N8N_WEBHOOK_URL:

        raise ValueError(
            "N8N_WEBHOOK_URL was not found. "
            "Check your .env file or environment."
        )


    if not INPUT_PATH.exists():

        raise FileNotFoundError(
            f"Input file not found: "
            f"{INPUT_PATH}"
        )


    breaks = pd.read_csv(
        INPUT_PATH
    )


    required = [
        "dedup_key",
        "trade_id",
        "severity",
    ]


    missing = [
        column
        for column in required
        if column
        not in breaks.columns
    ]


    if missing:

        raise ValueError(
            "Missing required dispatch columns: "
            + ", ".join(
                missing
            )
        )


    # --------------------------------------------------
    # Only active HIGH / CRITICAL incidents
    # --------------------------------------------------

    eligible = breaks[
        breaks[
            "severity"
        ]
        .astype(str)
        .str.upper()
        .isin(
            ELIGIBLE_SEVERITIES
        )
    ].copy()


    if "break_status" in eligible.columns:

        eligible = eligible[
            eligible[
                "break_status"
            ]
            .astype(str)
            .str.upper()
            .eq("OPEN")
        ].copy()


    # --------------------------------------------------
    # Previous state
    # --------------------------------------------------

    state = (
        load_dispatch_state()
    )


    state_lookup = {}


    if not state.empty:

        state_latest = (
            state
            .drop_duplicates(
                subset=[
                    "dedup_key"
                ],
                keep="last",
            )
        )


        state_lookup = {

            str(
                row[
                    "dedup_key"
                ]
            ): row

            for _, row
            in state_latest.iterrows()
        }


    # Preserve existing rows
    updated_state = {}


    if not state.empty:

        for _, state_row in (
            state.iterrows()
        ):

            key = str(
                state_row[
                    "dedup_key"
                ]
            )

            updated_state[
                key
            ] = (
                state_row.to_dict()
            )


    sent = 0
    skipped = 0
    failed = 0


    # --------------------------------------------------
    # Process breaks
    # --------------------------------------------------

    for _, row in (
        eligible.iterrows()
    ):

        dedup_key = str(
            row[
                "dedup_key"
            ]
        )


        previous = (
            state_lookup.get(
                dedup_key
            )
        )


        if not should_dispatch(
            row,
            previous,
        ):

            skipped += 1

            print(
                f"SKIPPED | "
                f"{dedup_key}"
            )

            continue


        attempts = (
            next_attempt_number(
                previous
            )
        )


        payload = (
            build_payload(
                row
            )
        )


        try:

            send_break(
                payload
            )


            sent += 1


            now = pd.Timestamp.now(
                tz="UTC"
            )


            updated_state[
                dedup_key
            ] = {

                "dedup_key": (
                    dedup_key
                ),

                "last_dispatched_at": (
                    now
                ),

                "last_dispatched_severity": (
                    json_safe(
                        row.get(
                            "severity"
                        )
                    )
                ),

                "last_dispatched_sla_status": (
                    json_safe(
                        row.get(
                            "sla_status"
                        )
                    )
                ),

                "last_dispatched_break_status": (
                    json_safe(
                        row.get(
                            "break_status"
                        )
                    )
                ),

                "dispatch_attempts": (
                    attempts
                ),

                "dispatch_status": (
                    "SENT"
                ),

                "last_dispatch_error": (
                    ""
                ),
            }


            print(
                f"SENT    | "
                f"{dedup_key}"
            )


        except Exception as exc:

            failed += 1


            updated_state[
                dedup_key
            ] = {

                "dedup_key": (
                    dedup_key
                ),

                "last_dispatched_at": (
                    previous.get(
                        "last_dispatched_at"
                    )
                    if previous is not None
                    else pd.NaT
                ),

                "last_dispatched_severity": (
                    previous.get(
                        "last_dispatched_severity"
                    )
                    if previous is not None
                    else pd.NA
                ),

                "last_dispatched_sla_status": (
                    previous.get(
                        "last_dispatched_sla_status"
                    )
                    if previous is not None
                    else pd.NA
                ),

                "last_dispatched_break_status": (
                    previous.get(
                        "last_dispatched_break_status"
                    )
                    if previous is not None
                    else pd.NA
                ),

                "dispatch_attempts": (
                    attempts
                ),

                "dispatch_status": (
                    "FAILED"
                ),

                "last_dispatch_error": (
                    str(exc)
                ),
            }


            print(
                f"FAILED  | "
                f"{dedup_key} "
                f"| {exc}"
            )


    # --------------------------------------------------
    # Persist state
    # --------------------------------------------------

    updated_state_df = (
        pd.DataFrame(
            list(
                updated_state.values()
            )
        )
    )


    save_dispatch_state(
        updated_state_df
    )


    return {

        "eligible": int(
            len(
                eligible
            )
        ),

        "sent": sent,

        "skipped": skipped,

        "failed": failed,
    }


# --------------------------------------------------
# Run
# --------------------------------------------------

if __name__ == "__main__":

    result = (
        dispatch_breaks()
    )


    print()
    print(
        "TradeOps n8n dispatch complete"
    )

    print(
        "-" * 45
    )


    print(
        f"Eligible: "
        f"{result['eligible']}"
    )

    print(
        f"Sent:     "
        f"{result['sent']}"
    )

    print(
        f"Skipped:  "
        f"{result['skipped']}"
    )

    print(
        f"Failed:   "
        f"{result['failed']}"
    )