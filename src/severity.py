import os

import numpy as np
import pandas as pd


INPUT_PATH = "data/processed/trade_breaks.csv"
OUTPUT_PATH = "data/processed/trade_breaks_scored.csv"


# --------------------------------------------------
# Base risk weights by exception type
# --------------------------------------------------

EXCEPTION_WEIGHTS = {
    "MISSING_CLEARING_RECORD": 35,
    "MISSING_EXECUTION_RECORD": 35,
    "DUPLICATE_CLEARING_RECORD": 20,
    "QUANTITY_MISMATCH": 30,
    "PRICE_MISMATCH": 25,
    "SIDE_MISMATCH": 40,
    "ACCOUNT_MISMATCH": 30,
    "CURRENCY_MISMATCH": 35,
    "SETTLEMENT_FAILED": 45,
    "LATE_CLEARING": 20,
}


# --------------------------------------------------
# Notional exposure score
# --------------------------------------------------

def notional_score(row):
    """
    Score operational exposure based on affected notional.
    """

    affected_notional = row.get(
        "affected_notional",
        0,
    )

    execution_notional = row.get(
        "execution_notional",
        0,
    )

    if pd.isna(affected_notional):
        affected_notional = 0

    if pd.isna(execution_notional):
        execution_notional = 0

    # Use affected notional where available.
    # For exceptions without a direct quantity difference,
    # fall back to total execution notional.
    exposure = (
        affected_notional
        if affected_notional > 0
        else execution_notional
    )

    if exposure >= 1_000_000:
        return 25

    if exposure >= 500_000:
        return 20

    if exposure >= 100_000:
        return 15

    if exposure >= 25_000:
        return 10

    if exposure > 0:
        return 5

    return 0


# --------------------------------------------------
# Clearing latency score
# --------------------------------------------------

def latency_score(row):
    """
    Increase severity for aged/late exceptions.
    """

    latency = row.get(
        "clearing_latency_seconds",
        0,
    )

    if pd.isna(latency):
        return 0

    minutes = latency / 60

    if minutes >= 60:
        return 20

    if minutes >= 30:
        return 15

    if minutes >= 15:
        return 10

    if minutes >= 8:
        return 5

    return 0


# --------------------------------------------------
# Difference magnitude score
# --------------------------------------------------

def mismatch_magnitude_score(row):
    """
    Add risk based on the relative size of
    quantity or price discrepancies.
    """

    exception_type = row.get(
        "exception_type",
        "",
    )

    # ----------------------------------------------
    # Quantity mismatch
    # ----------------------------------------------

    if exception_type == "QUANTITY_MISMATCH":

        execution_quantity = row.get(
            "quantity_exec",
            np.nan,
        )

        quantity_difference = row.get(
            "quantity_difference",
            np.nan,
        )

        if (
            pd.isna(execution_quantity)
            or pd.isna(quantity_difference)
            or execution_quantity == 0
        ):
            return 0

        ratio = (
            abs(quantity_difference)
            / abs(execution_quantity)
        )

        if ratio >= 0.50:
            return 20

        if ratio >= 0.25:
            return 15

        if ratio >= 0.10:
            return 10

        if ratio > 0:
            return 5

    # ----------------------------------------------
    # Price mismatch
    # ----------------------------------------------

    if exception_type == "PRICE_MISMATCH":

        execution_price = row.get(
            "price_exec",
            np.nan,
        )

        price_difference = row.get(
            "price_difference",
            np.nan,
        )

        if (
            pd.isna(execution_price)
            or pd.isna(price_difference)
            or execution_price == 0
        ):
            return 0

        ratio = (
            abs(price_difference)
            / abs(execution_price)
        )

        if ratio >= 0.05:
            return 20

        if ratio >= 0.02:
            return 15

        if ratio >= 0.01:
            return 10

        if ratio > 0:
            return 5

    return 0


# --------------------------------------------------
# Status score
# --------------------------------------------------

def status_score(row):
    """
    Failed clearing receives additional risk.
    """

    status = row.get(
        "clearing_status",
        "",
    )

    if status == "FAILED":
        return 20

    return 0


# --------------------------------------------------
# Calculate full severity
# --------------------------------------------------

def calculate_severity(row):
    """
    Calculate a 0-100 operational risk score.
    """

    exception_type = row.get(
        "exception_type",
        "",
    )

    base_score = EXCEPTION_WEIGHTS.get(
        exception_type,
        10,
    )

    score = (
        base_score
        + notional_score(row)
        + latency_score(row)
        + mismatch_magnitude_score(row)
        + status_score(row)
    )

    # Cap at 100
    return min(
        int(score),
        100,
    )


# --------------------------------------------------
# Map numeric score to severity level
# --------------------------------------------------

def severity_level(score):

    if score >= 75:
        return "CRITICAL"

    if score >= 50:
        return "HIGH"

    if score >= 30:
        return "MEDIUM"

    return "LOW"


# --------------------------------------------------
# Score all breaks
# --------------------------------------------------

def score_breaks(df):

    df = df.copy()

    df["severity_score"] = df.apply(
        calculate_severity,
        axis=1,
    )

    df["severity"] = (
        df["severity_score"]
        .apply(severity_level)
    )

    # Sort highest-risk issues first
    df = df.sort_values(
        by=[
            "severity_score",
            "execution_notional",
        ],
        ascending=[
            False,
            False,
        ],
    )

    # Operational priority rank
    df["priority_rank"] = range(
        1,
        len(df) + 1,
    )

    return df


# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":

    breaks = pd.read_csv(
        INPUT_PATH
    )

    scored_breaks = score_breaks(
        breaks
    )

    os.makedirs(
        "data/processed",
        exist_ok=True,
    )

    scored_breaks.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print(
        "TradeOps severity scoring complete"
    )
    print("-" * 45)

    print()
    print(
        f"Breaks scored: {len(scored_breaks)}"
    )

    print()
    print("Severity distribution:")

    print(
        scored_breaks[
            "severity"
        ]
        .value_counts()
    )

    print()
    print(
        "Top priority breaks:"
    )

    display_columns = [
        "priority_rank",
        "break_id",
        "trade_id",
        "exception_type",
        "severity_score",
        "severity",
        "execution_notional",
        "affected_notional",
        "clearing_latency_seconds",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in scored_breaks.columns
    ]

    print(
        scored_breaks[
            display_columns
        ]
        .head(10)
        .to_string(index=False)
    )

    print()
    print(
        "Scored breaks saved to:"
    )

    print(
        OUTPUT_PATH
    )