import os

import pandas as pd


INPUT_PATH = "data/processed/trade_breaks_scored.csv"
OUTPUT_PATH = "data/processed/trade_breaks_sla.csv"


# --------------------------------------------------
# SLA thresholds by severity
# --------------------------------------------------

SLA_MINUTES = {
    "CRITICAL": 15,
    "HIGH": 30,
    "MEDIUM": 60,
    "LOW": 240,
}


def add_sla_tracking(df):
    """
    Add operational ageing and SLA fields
    to scored trade breaks.
    """

    df = df.copy()

    # --------------------------------------------------
    # Parse timestamps
    # --------------------------------------------------

    if "execution_timestamp" in df.columns:
        df["execution_timestamp"] = pd.to_datetime(
            df["execution_timestamp"],
            errors="coerce",
            utc=True,
        )

    if "clearing_timestamp" in df.columns:
        df["clearing_timestamp"] = pd.to_datetime(
            df["clearing_timestamp"],
            errors="coerce",
            utc=True,
        )

    # --------------------------------------------------
    # Use clearing timestamp as first-seen proxy
    #
    # Later, once TradeOps runs repeatedly, we can
    # persist true first_seen_at / last_seen_at values.
    # --------------------------------------------------

    df["first_seen_at"] = df["clearing_timestamp"]

    df["last_seen_at"] = df["clearing_timestamp"]

    # --------------------------------------------------
    # Calculate current age
    # --------------------------------------------------

    now = pd.Timestamp.now(tz="UTC")

    df["detected_at"] = now
    df["first_seen_at"] = now
    df["last_seen_at"] = now
    df["resolved_at"] = pd.NaT
    df["break_status"] = "OPEN"

    df["age_minutes"] = (
        (
            now
            - df["first_seen_at"]
        )
        .dt.total_seconds()
        / 60
    )   

    # Guard against negative values
    df["age_minutes"] = (
        df["age_minutes"]
        .clip(lower=0)
    )

    # --------------------------------------------------
    # SLA threshold
    # --------------------------------------------------

    df["sla_minutes"] = (
        df["severity"]
        .map(SLA_MINUTES)
    )

    # --------------------------------------------------
    # SLA remaining
    # --------------------------------------------------

    df["sla_remaining_minutes"] = (
        df["sla_minutes"]
        - df["age_minutes"]
    )

    # --------------------------------------------------
    # SLA status
    # --------------------------------------------------

    def classify_sla(row):

        if row["break_status"] != "OPEN":
            return "CLOSED"

        if pd.isna(row["sla_minutes"]):
            return "UNKNOWN"

        if row["age_minutes"] > row["sla_minutes"]:
            return "BREACHED"

        # Warning when >= 75% of SLA window consumed
        if row["age_minutes"] >= (
            row["sla_minutes"] * 0.75
        ):
            return "AT_RISK"

        return "WITHIN_SLA"

    df["sla_status"] = df.apply(
        classify_sla,
        axis=1,
    )

    # --------------------------------------------------
    # Percentage of SLA consumed
    # --------------------------------------------------

    df["sla_consumed_pct"] = (
        df["age_minutes"]
        / df["sla_minutes"]
        * 100
    )

    # --------------------------------------------------
    # Rank operational urgency
    # --------------------------------------------------

    sla_priority = {
        "BREACHED": 1,
        "AT_RISK": 2,
        "WITHIN_SLA": 3,
        "UNKNOWN": 4,
        "CLOSED": 5,
    }

    df["sla_priority"] = (
        df["sla_status"]
        .map(sla_priority)
    )

    df = df.sort_values(
        by=[
            "sla_priority",
            "severity_score",
            "age_minutes",
        ],
        ascending=[
            True,
            False,
            False,
        ],
    )

    return df


if __name__ == "__main__":

    breaks = pd.read_csv(
        INPUT_PATH
    )

    breaks_sla = add_sla_tracking(
        breaks
    )

    os.makedirs(
        "data/processed",
        exist_ok=True,
    )

    breaks_sla.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print(
        "TradeOps SLA tracking complete"
    )
    print("-" * 45)

    print()
    print(
        f"Breaks tracked: {len(breaks_sla)}"
    )

    print()
    print("SLA status distribution:")

    print(
        breaks_sla[
            "sla_status"
        ]
        .value_counts()
    )

    print()
    print(
        "Highest urgency breaks:"
    )

    display_columns = [
        "break_id",
        "trade_id",
        "exception_type",
        "severity",
        "severity_score",
        "age_minutes",
        "sla_minutes",
        "sla_remaining_minutes",
        "sla_status",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in breaks_sla.columns
    ]

    print(
        breaks_sla[
            display_columns
        ]
        .head(10)
        .to_string(index=False)
    )

    print()
    print(
        "SLA-enriched breaks saved to:"
    )

    print(
        OUTPUT_PATH
    )