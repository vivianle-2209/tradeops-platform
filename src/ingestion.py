import os

import pandas as pd
import requests
from dotenv import load_dotenv


# --------------------------------------------------
# Load environment variables
# --------------------------------------------------

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

BASE_URL = "https://data.alpaca.markets/v2/stocks"


# --------------------------------------------------
# Validate credentials
# --------------------------------------------------

if not API_KEY or not SECRET_KEY:
    raise ValueError(
        "Alpaca API credentials were not found. "
        "Check your .env file."
    )


# --------------------------------------------------
# Fetch historical trades
# --------------------------------------------------

def fetch_trades(
    symbol,
    start,
    end,
    limit=1000,
):
    """
    Fetch historical stock trades from Alpaca.

    Parameters
    ----------
    symbol : str
        Stock ticker, e.g. "MSFT".

    start : str
        Start timestamp in ISO 8601 format.

    end : str
        End timestamp in ISO 8601 format.

    limit : int
        Maximum number of trades to request.

    Returns
    -------
    pandas.DataFrame
        Raw trade records returned by Alpaca.
    """

    url = f"{BASE_URL}/{symbol}/trades"

    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY,
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

    data = response.json()

    trades = data.get("trades", [])

    df = pd.DataFrame(trades)

    # Alpaca's single-symbol endpoint does not
    # repeat the ticker inside each trade record,
    # so add it manually.
    if not df.empty:
        df["symbol"] = symbol.upper()

    return df


# --------------------------------------------------
# Save raw data
# --------------------------------------------------

def save_raw_trades(
    df,
    symbol,
):
    """
    Save the raw API response to data/raw.
    """

    os.makedirs(
        "data/raw",
        exist_ok=True,
    )

    output_path = (
        f"data/raw/"
        f"{symbol.lower()}_trades_raw.csv"
    )

    df.to_csv(
        output_path,
        index=False,
    )

    return output_path


# --------------------------------------------------
# Run ingestion
# --------------------------------------------------

if __name__ == "__main__":

    symbol = "MSFT"

    df = fetch_trades(
        symbol=symbol,
        start="2026-10-19T14:00:00Z",
        end="2026-10-19T14:05:00Z",
        limit=1000,
    )

    output_path = save_raw_trades(
        df=df,
        symbol=symbol,
    )

    print()
    print("TradeOps ingestion complete")
    print("-" * 40)

    print()
    print("Sample rows:")
    print(df.head())

    print()
    print(f"Rows retrieved: {len(df)}")

    print()
    print("Columns:")
    print(df.columns.tolist())

    print()
    print(f"Raw file saved to:")
    print(output_path)