import os

import pandas as pd


RAW_PATH = "data/raw/msft_trades_raw.csv"
OUTPUT_PATH = "data/cleaned/msft_trades_clean.csv"


def clean_trades(df):
    """
    Clean raw Alpaca trade data and transform it
    into the initial TradeOps execution schema.
    """

    df = df.copy()

    # Rename Alpaca raw fields
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

    # Parse timestamp
    df["execution_timestamp"] = pd.to_datetime(
        df["execution_timestamp"],
        errors="coerce",
        utc=True,
    )

    # Convert numeric fields
    df["price"] = pd.to_numeric(
        df["price"],
        errors="coerce",
    )

    df["quantity"] = pd.to_numeric(
        df["quantity"],
        errors="coerce",
    )

    # Standardise symbol
    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Standardise venue
    df["venue"] = (
        df["venue"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Remove exact duplicates
    df = df.drop_duplicates()

    # Remove records missing critical fields
    df = df.dropna(
        subset=[
            "market_trade_id",
            "symbol",
            "price",
            "quantity",
            "execution_timestamp",
        ]
    )

    # Remove impossible values
    df = df[
        (df["price"] > 0)
        & (df["quantity"] > 0)
    ]

    # Create TradeOps internal trade ID
    df["trade_id"] = [
        f"TRD-{i:06d}"
        for i in range(1, len(df) + 1)
    ]

    # Add simulated internal fields
    df["currency"] = "USD"

    # Reorder columns
    df = df[
        [
            "trade_id",
            "market_trade_id",
            "symbol",
            "quantity",
            "price",
            "currency",
            "venue",
            "execution_timestamp",
            "trade_conditions",
            "tape",
        ]
    ]

    return df


if __name__ == "__main__":

    df_raw = pd.read_csv(RAW_PATH)

    df_clean = clean_trades(df_raw)

    os.makedirs(
        "data/cleaned",
        exist_ok=True,
    )

    df_clean.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print("TradeOps cleaning complete")
    print("-" * 40)

    print()
    print("Sample cleaned rows:")
    print(df_clean.head())

    print()
    print(f"Raw rows: {len(df_raw)}")
    print(f"Clean rows: {len(df_clean)}")

    print()
    print("Cleaned columns:")
    print(df_clean.columns.tolist())

    print()
    print(f"Cleaned file saved to:")
    print(OUTPUT_PATH)