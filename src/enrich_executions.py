import os
import random

import numpy as np
import pandas as pd


INPUT_PATH = (
    "data/cleaned/"
    "market_trades_cleaned.csv"
)

OUTPUT_PATH = (
    "data/processed/"
    "executions.csv"
)


# --------------------------------------------------
# Reproducibility
# --------------------------------------------------

random.seed(
    42
)

np.random.seed(
    42
)


# --------------------------------------------------
# Synthetic internal trading attributes
# --------------------------------------------------

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


def enrich_executions(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add simulated internal TradeOps attributes
    to cleaned market trade records.
    """

    df = df.copy()


    # --------------------------------------------------
    # Simulated BUY / SELL direction
    # --------------------------------------------------

    df["side"] = (
        np.random.choice(
            [
                "BUY",
                "SELL",
            ],
            size=len(df),
        )
    )


    # --------------------------------------------------
    # Synthetic account ownership
    # --------------------------------------------------

    df["account"] = (
        np.random.choice(
            ACCOUNTS,
            size=len(df),
        )
    )


    # --------------------------------------------------
    # Synthetic trader ownership
    # --------------------------------------------------

    df["trader_id"] = (
        np.random.choice(
            TRADERS,
            size=len(df),
        )
    )


    # --------------------------------------------------
    # Internal order IDs
    # --------------------------------------------------

    df["order_id"] = [
        f"ORD-{i:06d}"
        for i in range(
            1,
            len(df) + 1,
        )
    ]


    # --------------------------------------------------
    # Record source
    # --------------------------------------------------

    df[
        "record_source"
    ] = "EXECUTION"


    # --------------------------------------------------
    # Ensure execution notional exists
    # --------------------------------------------------

    if (
        "execution_notional"
        not in df.columns
    ):

        df[
            "execution_notional"
        ] = (
            pd.to_numeric(
                df["quantity"],
                errors="coerce",
            )
            *
            pd.to_numeric(
                df["price"],
                errors="coerce",
            )
        )


    # --------------------------------------------------
    # Final execution schema
    # --------------------------------------------------

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
            "execution_notional",
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

    df_clean = pd.read_csv(
        INPUT_PATH
    )


    df_executions = (
        enrich_executions(
            df_clean
        )
    )


    os.makedirs(
        "data/processed",
        exist_ok=True,
    )


    df_executions.to_csv(
        OUTPUT_PATH,
        index=False,
    )


    print()
    print(
        "TradeOps execution enrichment complete"
    )

    print(
        "-" * 45
    )


    print(
        f"Execution rows: "
        f"{len(df_executions)}"
    )


    print()
    print(
        "Executions by symbol:"
    )

    print(
        df_executions[
            "symbol"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )


    print()
    print(
        "Saved to:"
    )

    print(
        OUTPUT_PATH
    )