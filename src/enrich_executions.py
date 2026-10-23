
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def enrich_executions(df: pd.DataFrame) -> pd.DataFrame:
    """Synthetic attributes keyed by permanent identity, independent of batch/order."""
    from src.contracts import execution_frame, stable_id
    df = df.copy()
    seeds = df['trade_id'].map(lambda value: int(stable_id('ATTR', value).split('-')[1][:16], 16))
    df['side'] = seeds.map(lambda value: ['BUY', 'SELL'][value % 2])
    df['account'] = seeds.map(lambda value: ACCOUNTS[(value // 2) % len(ACCOUNTS)])
    df['trader_id'] = seeds.map(lambda value: TRADERS[(value // 8) % len(TRADERS)])
    df['order_id'] = df['trade_id'].map(lambda value: stable_id('ORD', value))
    df['record_source'] = 'EXECUTION'
    df['execution_notional'] = df['quantity'] * df['price']
    return execution_frame(df)



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