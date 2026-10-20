import os

import numpy as np
import pandas as pd


EXECUTIONS_PATH = "data/processed/executions.csv"
CLEARING_PATH = "data/processed/clearing.csv"

RESULTS_PATH = "data/processed/reconciliation_results.csv"
BREAKS_PATH = "data/processed/trade_breaks.csv"


# --------------------------------------------------
# Reconciliation configuration
# --------------------------------------------------

PRICE_TOLERANCE = 0.01

# Normal simulated clearing latency is around
# 2–8 minutes, so anything above 15 minutes
# will be considered late.
LATE_CLEARING_THRESHOLD_SECONDS = 15 * 60


# --------------------------------------------------
# Reconciliation engine
# --------------------------------------------------

def reconcile_trades(executions, clearing):
    """
    Reconcile execution records against clearing records.

    Supports:
    - missing clearing records
    - orphan clearing records
    - duplicate clearing records
    - quantity mismatches
    - price mismatches
    - account mismatches
    - currency mismatches
    - side mismatches
    - failed clearing
    - late clearing
    - multiple simultaneous breaks
    """

    executions = executions.copy()
    clearing = clearing.copy()

    # --------------------------------------------------
    # Parse timestamps
    # --------------------------------------------------

    executions["execution_timestamp"] = pd.to_datetime(
        executions["execution_timestamp"],
        errors="coerce",
        utc=True,
    )

    clearing["clearing_timestamp"] = pd.to_datetime(
        clearing["clearing_timestamp"],
        errors="coerce",
        utc=True,
    )

    # --------------------------------------------------
    # Count clearing records for each trade
    #
    # > 1 means DUPLICATE_CLEARING_RECORD
    # --------------------------------------------------

    clearing_counts = (
        clearing
        .groupby("trade_id")
        .size()
        .rename("clearing_record_count")
        .reset_index()
    )

    # --------------------------------------------------
    # Select canonical clearing record
    #
    # If duplicates exist, compare against the
    # earliest clearing record while separately
    # flagging the duplicate.
    # --------------------------------------------------

    canonical_clearing = (
        clearing
        .sort_values("clearing_timestamp")
        .drop_duplicates(
            subset=["trade_id"],
            keep="first",
        )
    )

    # --------------------------------------------------
    # Merge execution and clearing systems
    # --------------------------------------------------

    merged = executions.merge(
        canonical_clearing,
        on="trade_id",
        how="outer",
        suffixes=("_exec", "_clear"),
        indicator=True,
    )

    merged = merged.merge(
        clearing_counts,
        on="trade_id",
        how="left",
    )

    merged["clearing_record_count"] = (
        merged["clearing_record_count"]
        .fillna(0)
        .astype(int)
    )

    # --------------------------------------------------
    # Calculate operational metrics
    # --------------------------------------------------

    merged["execution_notional"] = (
        merged["quantity_exec"]
        * merged["price_exec"]
    )

    merged["quantity_difference"] = (
        merged["quantity_exec"]
        - merged["quantity_clear"]
    )

    merged["price_difference"] = (
        merged["price_exec"]
        - merged["price_clear"]
    )

    merged["affected_notional"] = (
        merged["quantity_difference"].abs()
        * merged["price_exec"]
    )

    merged["clearing_latency_seconds"] = (
        (
            merged["clearing_timestamp"]
            - merged["execution_timestamp"]
        )
        .dt.total_seconds()
    )

    # --------------------------------------------------
    # Detect multiple breaks per trade
    # --------------------------------------------------

    def detect_breaks(row):
        breaks = []

        # Execution exists but clearing does not
        if row["_merge"] == "left_only":
            return ["MISSING_CLEARING_RECORD"]

        # Clearing exists but execution does not
        if row["_merge"] == "right_only":
            return ["MISSING_EXECUTION_RECORD"]

        # Duplicate clearing messages
        if row["clearing_record_count"] > 1:
            breaks.append(
                "DUPLICATE_CLEARING_RECORD"
            )

        # Quantity
        if (
            pd.notna(row["quantity_exec"])
            and pd.notna(row["quantity_clear"])
            and row["quantity_exec"]
            != row["quantity_clear"]
        ):
            breaks.append(
                "QUANTITY_MISMATCH"
            )

        # Price
        if (
            pd.notna(row["price_exec"])
            and pd.notna(row["price_clear"])
            and abs(
                row["price_exec"]
                - row["price_clear"]
            )
            > PRICE_TOLERANCE
        ):
            breaks.append(
                "PRICE_MISMATCH"
            )

        # Side
        if (
            pd.notna(row["side_exec"])
            and pd.notna(row["side_clear"])
            and row["side_exec"]
            != row["side_clear"]
        ):
            breaks.append(
                "SIDE_MISMATCH"
            )

        # Account
        if (
            pd.notna(row["account_exec"])
            and pd.notna(row["account_clear"])
            and row["account_exec"]
            != row["account_clear"]
        ):
            breaks.append(
                "ACCOUNT_MISMATCH"
            )

        # Currency
        if (
            pd.notna(row["currency_exec"])
            and pd.notna(row["currency_clear"])
            and row["currency_exec"]
            != row["currency_clear"]
        ):
            breaks.append(
                "CURRENCY_MISMATCH"
            )

        # Failed clearing
        if (
            pd.notna(
                row["clearing_status"]
            )
            and row["clearing_status"]
            == "FAILED"
        ):
            breaks.append(
                "SETTLEMENT_FAILED"
            )

        # Late clearing
        latency = row[
            "clearing_latency_seconds"
        ]

        if (
            pd.notna(latency)
            and latency
            > LATE_CLEARING_THRESHOLD_SECONDS
        ):
            breaks.append(
                "LATE_CLEARING"
            )

        if not breaks:
            breaks.append("MATCHED")

        return breaks

    merged["exceptions"] = merged.apply(
        detect_breaks,
        axis=1,
    )

    # --------------------------------------------------
    # Break count
    # --------------------------------------------------

    merged["break_count"] = (
        merged["exceptions"]
        .apply(
            lambda x:
            0
            if x == ["MATCHED"]
            else len(x)
        )
    )

    # --------------------------------------------------
    # Reconciliation status
    # --------------------------------------------------

    merged["reconciliation_status"] = (
        merged["break_count"]
        .apply(
            lambda x:
            "MATCHED"
            if x == 0
            else "BREAK"
        )
    )

    # --------------------------------------------------
    # CSV-friendly exception representation
    # --------------------------------------------------

    merged["exception_types"] = (
        merged["exceptions"]
        .apply("|".join)
    )

    return merged


# --------------------------------------------------
# Create one row per individual break
# --------------------------------------------------

def create_break_table(results):
    """
    Explode reconciliation results so each
    operational exception becomes one row.
    """

    breaks = results[
        results["reconciliation_status"]
        == "BREAK"
    ].copy()

    breaks = breaks.explode(
        "exceptions"
    )

    breaks = breaks.rename(
        columns={
            "exceptions": "exception_type"
        }
    )

    breaks = breaks.reset_index(
        drop=True
    )

    # Create unique break IDs
    breaks["break_id"] = [
        f"BRK-{i:06d}"
        for i in range(
            1,
            len(breaks) + 1,
        )
    ]

    # Logical incident key for downstream
    # n8n deduplication
    breaks["dedup_key"] = (
        breaks["trade_id"]
        .astype(str)
        + ":"
        + breaks["exception_type"]
        .astype(str)
    )

    # Initial incident state
    breaks["break_status"] = "OPEN"

    # Select useful downstream fields
    desired_columns = [
        "break_id",
        "dedup_key",
        "trade_id",
        "exception_type",
        "symbol_exec",
        "side_exec",
        "venue",
        "account_exec",
        "currency_exec",
        "quantity_exec",
        "quantity_clear",
        "quantity_difference",
        "price_exec",
        "price_clear",
        "price_difference",
        "execution_notional",
        "affected_notional",
        "execution_timestamp",
        "clearing_timestamp",
        "clearing_latency_seconds",
        "clearing_status",
        "clearing_record_count",
        "break_status",
    ]

    # Only select columns that actually exist
    desired_columns = [
        column
        for column in desired_columns
        if column in breaks.columns
    ]

    return breaks[
        desired_columns
    ]


# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":

    executions = pd.read_csv(
        EXECUTIONS_PATH
    )

    clearing = pd.read_csv(
        CLEARING_PATH
    )

    results = reconcile_trades(
        executions,
        clearing,
    )

    break_table = create_break_table(
        results
    )

    os.makedirs(
        "data/processed",
        exist_ok=True,
    )

    # Save reconciliation-level results
    results_to_save = (
        results
        .drop(
            columns=["exceptions"],
            errors="ignore",
        )
    )

    results_to_save.to_csv(
        RESULTS_PATH,
        index=False,
    )

    # Save one-row-per-break table
    break_table.to_csv(
        BREAKS_PATH,
        index=False,
    )

    # --------------------------------------------------
    # Console reporting
    # --------------------------------------------------

    print()
    print(
        "TradeOps reconciliation complete"
    )
    print("-" * 45)

    total_trades = len(results)

    matched_trades = (
        results[
            "reconciliation_status"
        ]
        .eq("MATCHED")
        .sum()
    )

    broken_trades = (
        results[
            "reconciliation_status"
        ]
        .eq("BREAK")
        .sum()
    )

    print()
    print(
        f"Total trades:   {total_trades}"
    )

    print(
        f"Matched trades: {matched_trades}"
    )

    print(
        f"Broken trades:  {broken_trades}"
    )

    print(
        f"Total breaks:   {len(break_table)}"
    )

    print()

    if len(break_table) > 0:

        print("Breaks by type:")

        print(
            break_table[
                "exception_type"
            ]
            .value_counts()
        )

    print()
    print(
        "Sample broken trades:"
    )

    sample_columns = [
        "trade_id",
        "exception_types",
        "break_count",
        "execution_notional",
        "affected_notional",
        "clearing_latency_seconds",
    ]

    print(
        results.loc[
            results[
                "reconciliation_status"
            ]
            == "BREAK",
            sample_columns,
        ]
        .head(10)
        .to_string(index=False)
    )

    print()
    print(
        "Reconciliation results saved to:"
    )
    print(RESULTS_PATH)

    print()
    print(
        "Trade breaks saved to:"
    )
    print(BREAKS_PATH)