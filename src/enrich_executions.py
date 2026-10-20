import os
import random

import numpy as np
import pandas as pd


INPUT_PATH = "data/cleaned/msft_trades_clean.csv"
OUTPUT_PATH = "data/processed/executions.csv"

random.seed(42)
np.random.seed(42)


ACCOUNTS = [
    "ACC-1001",
    "ACC-2001",
    "ACC-3001",
    "ACC-4001",
]

TRADERS = [
    "TR-0101",
    "TR-0202",
    "TR-0303",
    "TR-0404",
]


def enrich_executions(df):
    """
    Add simulated internal trading attributes
    to cleaned market trade records.
    """

    df = df.copy()

    # Simulated BUY / SELL direction
    df["side"] = np.random.choice(
        ["BUY", "SELL"],
        size=len(df),
    )

    # Simulated account ownership
    df["account"] = np.random.choice(
        ACCOUNTS,
        size=len(df),
    )

    # Simulated trader ownership
    df["trader_id"] = np.random.choice(
        TRADERS,
        size=len(df),
    )

    # Generate internal order IDs
    df["order_id"] = [
        f"ORD-{i:06d}"
        for i in range(1, len(df) + 1)
    ]

    # Mark record source
    df["record_source"] = "EXECUTION"

    # Reorder into TradeOps execution schema
    df = df[
        [
            "record_source",
            "trade_id",
            "order_id",
            "market_trade_id",
            "symbol",
            "side",
            "quantity",
            "price",
            "currency",
            "account",
            "venue",
            "execution_timestamp",
            "trader_id",
            "trade_conditions",
            "tape",
        ]
    ]

    return df


if __name__ == "__main__":

    df_clean = pd.read_csv(INPUT_PATH)

    df_executions = enrich_executions(df_clean)

    os.makedirs(
        "data/processed",
        exist_ok=True,
    )

    df_executions.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print("TradeOps execution enrichment complete")
    print("-" * 45)

    print()
    print("Sample execution records:")
    print(df_executions.head())

    print()
    print(f"Execution rows: {len(df_executions)}")

    print()
    print("Execution columns:")
    print(df_executions.columns.tolist())

    print()
    print("Saved to:")
    print(OUTPUT_PATH)