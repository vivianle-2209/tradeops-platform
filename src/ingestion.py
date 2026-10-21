import os
from datetime import timedelta

import pandas as pd
import requests
from dotenv import load_dotenv


# --------------------------------------------------
# Environment
# --------------------------------------------------

load_dotenv()

API_KEY = os.getenv(
    "ALPACA_API_KEY"
)

SECRET_KEY = os.getenv(
    "ALPACA_SECRET_KEY"
)


BASE_URL = (
    "https://data.alpaca.markets/v2/stocks"
)


# --------------------------------------------------
# TradeOps market basket
# --------------------------------------------------

WINDOWS_MINUTES = 15

SYMBOLS = [
    "MSFT",
    "AAPL",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
]


RAW_OUTPUT_PATH = (
    "data/raw/market_trades_raw.csv"
)


# --------------------------------------------------
# Validate credentials
# --------------------------------------------------

if not API_KEY or not SECRET_KEY:

    raise ValueError(
        "Alpaca API credentials were not found. "
        "Check your .env file."
    )


# --------------------------------------------------
# Fetch trades for one symbol
# --------------------------------------------------

def fetch_trades(
    symbol: str,
    start: str,
    end: str,
    limit: int = 1000,
) -> pd.DataFrame:
    """
    Fetch historical IEX trades for one symbol
    from Alpaca.
    """

    symbol = (
        str(symbol)
        .strip()
        .upper()
    )

    url = (
        f"{BASE_URL}/"
        f"{symbol}/trades"
    )


    headers = {
        "APCA-API-KEY-ID": (
            API_KEY
        ),
        "APCA-API-SECRET-KEY": (
            SECRET_KEY
        ),
    }


    params = {
        "start": start,
        "end": end,
        "limit": limit,
        "feed": "iex",
        "sort": "asc",
    }


    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    trades = payload.get(
        "trades",
        [],
    )


    df = pd.DataFrame(
        trades
    )


    if not df.empty:

        df["symbol"] = (
            symbol
        )


    return df


# --------------------------------------------------
# Fetch complete symbol basket
# --------------------------------------------------

def fetch_market_basket(
    symbols: list[str],
    start: str,
    end: str,
    limit_per_symbol: int = 1000,
) -> pd.DataFrame:
    """
    Fetch trades for all configured symbols and
    combine them into one raw dataset.
    """

    frames = []


    for symbol in symbols:

        print(
            f"Fetching {symbol}..."
        )


        try:

            symbol_df = (
                fetch_trades(
                    symbol=symbol,
                    start=start,
                    end=end,
                    limit=limit_per_symbol,
                )
            )


            print(
                f"  {symbol}: "
                f"{len(symbol_df)} rows"
            )


            if not symbol_df.empty:

                frames.append(
                    symbol_df
                )


        except requests.RequestException as exc:

            print(
                f"  {symbol}: FAILED | "
                f"{exc}"
            )


    if not frames:

        return pd.DataFrame()


    combined = pd.concat(
        frames,
        ignore_index=True,
    )


    return combined


# --------------------------------------------------
# Save combined raw dataset
# --------------------------------------------------

def save_raw_trades(
    df: pd.DataFrame,
) -> str:
    """
    Save combined multi-symbol trade data.
    """

    os.makedirs(
        "data/raw",
        exist_ok=True,
    )


    df.to_csv(
        RAW_OUTPUT_PATH,
        index=False,
    )


    return (
        RAW_OUTPUT_PATH
    )


# --------------------------------------------------
# Determine ingestion window
# --------------------------------------------------

def build_time_window(
    minutes: int = WINDOWS_MINUTES,
) -> tuple[str, str]:
    """
    Build a recent UTC time window.

    Alpaca may not return trades outside market
    activity periods, so this function only defines
    the requested interval.
    """

    end = pd.Timestamp.now(
        tz="UTC"
    )

    start = (
        end
        - timedelta(
            minutes=minutes
        )
    )


    return (
        start.isoformat(),
        end.isoformat(),
    )


# --------------------------------------------------
# Run
# --------------------------------------------------

if __name__ == "__main__":

    start_time, end_time = (
        build_time_window(
            minutes=WINDOWS_MINUTES
        )
    )


    print()
    print(
        "TradeOps market-data ingestion"
    )

    print(
        "-" * 45
    )


    print(
        f"Start: {start_time}"
    )

    print(
        f"End:   {end_time}"
    )

    print(
        f"Symbols: "
        f"{', '.join(SYMBOLS)}"
    )


    df = (
        fetch_market_basket(
            symbols=SYMBOLS,
            start=start_time,
            end=end_time,
            limit_per_symbol=1000,
        )
    )


    if df.empty:

        raise RuntimeError(
            "No market trade data was returned "
            "for the configured symbol basket."
        )


    output_path = (
        save_raw_trades(
            df
        )
    )


    print()
    print(
        "TradeOps ingestion complete"
    )

    print(
        "-" * 45
    )


    print(
        f"Rows retrieved: "
        f"{len(df)}"
    )


    print()
    print(
        "Rows by symbol:"
    )

    print(
        df[
            "symbol"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )


    print()
    print(
        "Raw file saved to:"
    )

    print(
        output_path
    )