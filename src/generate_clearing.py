import os
import random
from datetime import timedelta

import numpy as np
import pandas as pd


INPUT_PATH = "data/processed/executions.csv"
OUTPUT_PATH = "data/processed/clearing.csv"

random.seed(42)
np.random.seed(42)


def generate_clearing(df):
    """
    Generate synthetic clearing records from
    canonical execution records.

    Most records will match executions, while
    selected records will contain controlled
    operational breaks.
    """

    df = df.copy()

    clearing = pd.DataFrame()

    # --------------------------------------------------
    # Base clearing records
    # --------------------------------------------------

    clearing["record_source"] = "CLEARING"
    clearing["trade_id"] = df["trade_id"]
    clearing["symbol"] = df["symbol"]
    clearing["side"] = df["side"]
    clearing["quantity"] = df["quantity"]
    clearing["price"] = df["price"]
    clearing["currency"] = df["currency"]
    clearing["account"] = df["account"]

    # Add clearing IDs
    clearing["clearing_id"] = [
        f"CLR-{i:06d}"
        for i in range(1, len(df) + 1)
    ]

    # Parse execution timestamp
    execution_time = pd.to_datetime(
        df["execution_timestamp"],
        utc=True,
    )

    # Simulate normal clearing latency:
    # roughly 2-8 minutes after execution
    latency_seconds = np.random.randint(
        120,
        480,
        size=len(df),
    )

    clearing["clearing_timestamp"] = (
        execution_time
        + pd.to_timedelta(
            latency_seconds,
            unit="s",
        )
    )

    clearing["clearing_status"] = "CONFIRMED"

    # --------------------------------------------------
    # Inject controlled trade breaks
    # --------------------------------------------------

    n = len(clearing)

    indices = np.arange(n)
    np.random.shuffle(indices)

    # Number of injected errors
    quantity_idx = indices[0:8]
    price_idx = indices[8:14]
    account_idx = indices[14:19]
    currency_idx = indices[19:22]
    side_idx = indices[22:25]
    failed_idx = indices[25:29]
    late_idx = indices[29:34]

    # Quantity mismatches
    clearing.loc[
        quantity_idx,
        "quantity",
    ] = (
        clearing.loc[
            quantity_idx,
            "quantity",
        ]
        + np.random.randint(
            1,
            100,
            size=len(quantity_idx),
        )
    )

    # Price mismatches
    clearing.loc[
        price_idx,
        "price",
    ] = (
        clearing.loc[
            price_idx,
            "price",
        ]
        + 0.50
    )

    # Account mismatches
    clearing.loc[
        account_idx,
        "account",
    ] = "ACC-9999"

    # Currency mismatches
    clearing.loc[
        currency_idx,
        "currency",
    ] = "EUR"

    # Side mismatches
    clearing.loc[
        side_idx,
        "side",
    ] = clearing.loc[
        side_idx,
        "side",
    ].map(
        {
            "BUY": "SELL",
            "SELL": "BUY",
        }
    )

    # Failed clearing status
    clearing.loc[
        failed_idx,
        "clearing_status",
    ] = "FAILED"

    # Late clearing
    clearing.loc[
        late_idx,
        "clearing_timestamp",
    ] = (
        clearing.loc[
            late_idx,
            "clearing_timestamp",
        ]
        + timedelta(minutes=30)
    )

    # --------------------------------------------------
    # Remove some clearing records
    # creates MISSING_CLEARING_RECORD
    # --------------------------------------------------

    missing_idx = indices[34:39]

    clearing = clearing.drop(
        index=missing_idx,
    )

    # --------------------------------------------------
    # Duplicate some clearing records
    # creates DUPLICATE_CLEARING_RECORD
    # --------------------------------------------------

    duplicate_idx = indices[39:42]

    duplicates = clearing.loc[
        clearing.index.intersection(
            duplicate_idx
        )
    ].copy()

    if not duplicates.empty:
        duplicates["clearing_id"] = [
            f"CLR-DUP-{i:03d}"
            for i in range(
                1,
                len(duplicates) + 1,
            )
        ]

        duplicates["clearing_timestamp"] = (
            pd.to_datetime(
                duplicates["clearing_timestamp"],
                utc=True,
            )
            + timedelta(seconds=1)
        )

        clearing = pd.concat(
            [
                clearing,
                duplicates,
            ],
            ignore_index=True,
        )

    # Sort for readability
    clearing = clearing.sort_values(
        by=[
            "trade_id",
            "clearing_timestamp",
        ]
    )

    return clearing


if __name__ == "__main__":

    executions = pd.read_csv(INPUT_PATH)

    clearing = generate_clearing(
        executions
    )

    os.makedirs(
        "data/processed",
        exist_ok=True,
    )

    clearing.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print("TradeOps clearing generation complete")
    print("-" * 45)

    print()
    print("Sample clearing records:")
    print(clearing.head())

    print()
    print(f"Execution rows: {len(executions)}")
    print(f"Clearing rows: {len(clearing)}")

    print()
    print("Clearing columns:")
    print(clearing.columns.tolist())

    print()
    print("Clearing status counts:")
    print(
        clearing[
            "clearing_status"
        ].value_counts()
    )

    print()
    print("Saved to:")
    print(OUTPUT_PATH)