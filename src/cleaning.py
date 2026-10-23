
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os

import pandas as pd
from src.contracts import trade_identity
from src.config import Settings


RAW_PATH = (
    "data/raw/market_trades_raw.csv"
)

OUTPUT_PATH = (
    "data/cleaned/"
    "market_trades_cleaned.csv"
)


def clean_trades(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clean Alpaca market trades and transform them
    into the initial TradeOps execution schema.
    """

    df = df.copy()


    # --------------------------------------------------
    # Rename Alpaca fields
    # --------------------------------------------------

    df = df.rename(
        columns={
            "i": "market_trade_id",
            "p": "price",
            "s": "quantity",
            "t": "execution_timestamp",
            "x": "venue",
            "z": "tape",
            "c": "trade_conditions",
        }
    )


    # --------------------------------------------------
    # Validate required fields
    # --------------------------------------------------

    required = [
        "market_trade_id",
        "symbol",
        "price",
        "quantity",
        "execution_timestamp",
        "venue",
    ]


    missing = [
        column
        for column in required
        if column
        not in df.columns
    ]


    if missing:

        raise ValueError(
            "Raw trade data is missing "
            "required columns: "
            + ", ".join(
                missing
            )
        )


    # --------------------------------------------------
    # Parse timestamp
    # --------------------------------------------------

    df[
        "execution_timestamp"
    ] = pd.to_datetime(
        df[
            "execution_timestamp"
        ],
        errors="coerce",
        utc=True,
    )


    # --------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------

    df["price"] = pd.to_numeric(
        df["price"],
        errors="coerce",
    )

    df["quantity"] = pd.to_numeric(
        df["quantity"],
        errors="coerce",
    )


    # --------------------------------------------------
    # Standardise symbol
    # --------------------------------------------------

    df["symbol"] = (
        df["symbol"]
        .astype("string")
        .str.strip()
        .str.upper()
    )


    # --------------------------------------------------
    # Standardise venue
    # --------------------------------------------------

    if "venue" in df.columns:

        df["venue"] = (
            df["venue"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    else:

        df["venue"] = pd.NA


    # --------------------------------------------------
    # Optional Alpaca fields
    # --------------------------------------------------

    if (
        "trade_conditions"
        not in df.columns
    ):

        df[
            "trade_conditions"
        ] = pd.NA


    if "tape" not in df.columns:

        df["tape"] = pd.NA


    # --------------------------------------------------
    # Remove exact duplicates
    # --------------------------------------------------

    # Conditions from the API are lists; serialize before duplicate comparison.
    import json
    df["trade_conditions"] = df["trade_conditions"].map(
        lambda value: json.dumps(value) if isinstance(value, list) else value)


    # --------------------------------------------------
    # Remove invalid critical fields
    # --------------------------------------------------

    if df[required].isna().any().any() or df["symbol"].str.strip().eq("").any():
        raise ValueError("Invalid required source fields; checkpoint must not advance")
    if df["price"].le(0).any() or df["quantity"].le(0).any():
        raise ValueError("Nonpositive source economics; checkpoint must not advance")

    df = df.dropna(
        subset=[
            "market_trade_id",
            "symbol",
            "price",
            "quantity",
            "execution_timestamp",
        ]
    )


    # --------------------------------------------------
    # Remove impossible values
    # --------------------------------------------------

    df = df[
        (
            df["price"] > 0
        )
        &
        (
            df["quantity"] > 0
        )
    ].copy()


    # --------------------------------------------------
    # Stable deterministic ordering
    # --------------------------------------------------

    df = (
        df
        .sort_values(
            by=[
                "execution_timestamp",
                "symbol",
                "market_trade_id",
            ],
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )


    # --------------------------------------------------
    # Internal TradeOps trade ID
    # --------------------------------------------------

    if "source" not in df:
        df["source"] = Settings.source
    df["market_trade_id"] = df["market_trade_id"].astype("string")
    df["trade_id"] = [trade_identity(row.source, row.symbol, row.market_trade_id,
                         row.execution_timestamp, row.venue)
                      for row in df.itertuples()]
    df = df.drop_duplicates("trade_id", keep="last")


    # --------------------------------------------------
    # Currency
    # --------------------------------------------------

    df["currency"] = "USD"


    # --------------------------------------------------
    # Execution notional
    # --------------------------------------------------

    df[
        "execution_notional"
    ] = (
        df["quantity"]
        * df["price"]
    )


    # --------------------------------------------------
    # Final schema
    # --------------------------------------------------

    df = df[
        [
            "trade_id",
            "source",
            "market_trade_id",
            "symbol",
            "quantity",
            "price",
            "execution_notional",
            "currency",
            "venue",
            "execution_timestamp",
            "trade_conditions",
            "tape",
        ]
    ]


    return df


if __name__ == "__main__":

    df_raw = pd.read_csv(
        RAW_PATH
    )


    df_clean = clean_trades(
        df_raw
    )


    os.makedirs(
        "data/cleaned",
        exist_ok=True,
    )


    df_clean.to_csv(
        OUTPUT_PATH,
        index=False,
    )


    print()
    print(
        "TradeOps cleaning complete"
    )

    print(
        "-" * 45
    )


    print(
        f"Raw rows:   "
        f"{len(df_raw)}"
    )

    print(
        f"Clean rows: "
        f"{len(df_clean)}"
    )


    print()
    print(
        "Trades by symbol:"
    )

    print(
        df_clean[
            "symbol"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )


    print()
    print(
        "Cleaned file saved to:"
    )

    print(
        OUTPUT_PATH
    )
