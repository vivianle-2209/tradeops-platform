import os

import duckdb
import pandas as pd
import requests
from dotenv import load_dotenv


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

DB_PATH = "data/tradeops.duckdb"

N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL"
)


# --------------------------------------------------
# Validate configuration
# --------------------------------------------------

if not N8N_WEBHOOK_URL:
    raise ValueError(
        "N8N_WEBHOOK_URL was not found. "
        "Check your .env file."
    )


# --------------------------------------------------
# Load breaks from DuckDB
# --------------------------------------------------

def load_breaks_for_triage():
    """
    Load open TradeOps breaks that should be
    sent to the downstream n8n triage agent.

    Start with HIGH and CRITICAL exceptions.
    """

    con = duckdb.connect(
        DB_PATH,
        read_only=True,
    )

    query = """
        SELECT
            break_id,
            dedup_key,
            trade_id,
            exception_type,

            symbol_exec AS symbol,
            side_exec AS side,
            venue,
            account_exec AS account,
            currency_exec AS currency,

            quantity_exec AS execution_quantity,
            quantity_clear AS clearing_quantity,
            quantity_difference,

            price_exec AS execution_price,
            price_clear AS clearing_price,
            price_difference,

            execution_notional,
            affected_notional,

            clearing_latency_seconds,
            clearing_status,

            severity_score,
            severity,

            detected_at,
            first_seen_at,
            last_seen_at,

            age_minutes,
            sla_minutes,
            sla_remaining_minutes,
            sla_status,

            break_status

        FROM trade_breaks

        WHERE break_status = 'OPEN'

        AND severity IN (
            'HIGH',
            'CRITICAL'
        )

        ORDER BY
            severity_score DESC,
            priority_rank ASC

    """

    df = con.execute(
        query
    ).fetchdf()

    con.close()

    return df


# --------------------------------------------------
# Convert row to JSON-safe payload
# --------------------------------------------------

def build_payload(row):
    """
    Convert one TradeOps break into a payload
    suitable for the n8n triage workflow.
    """

    payload = {
        "source": "TRADEOPS",

        "break_id": row["break_id"],
        "dedup_key": row["dedup_key"],
        "trade_id": row["trade_id"],

        "exception_type": row[
            "exception_type"
        ],

        "trade": {
            "symbol": row["symbol"],
            "side": row["side"],
            "venue": row["venue"],
            "account": row["account"],
            "currency": row["currency"],
        },

        "reconciliation": {
            "execution_quantity": (
                row["execution_quantity"]
            ),
            "clearing_quantity": (
                row["clearing_quantity"]
            ),
            "quantity_difference": (
                row["quantity_difference"]
            ),

            "execution_price": (
                row["execution_price"]
            ),
            "clearing_price": (
                row["clearing_price"]
            ),
            "price_difference": (
                row["price_difference"]
            ),
        },

        "exposure": {
            "execution_notional": (
                row["execution_notional"]
            ),
            "affected_notional": (
                row["affected_notional"]
            ),
        },

        "clearing": {
            "status": row[
                "clearing_status"
            ],
            "latency_seconds": (
                row[
                    "clearing_latency_seconds"
                ]
            ),
        },

        "risk": {
            "severity_score": (
                row["severity_score"]
            ),
            "severity": row["severity"],
        },

        "sla": {
            "age_minutes": (
                row["age_minutes"]
            ),
            "sla_minutes": (
                row["sla_minutes"]
            ),
            "remaining_minutes": (
                row[
                    "sla_remaining_minutes"
                ]
            ),
            "status": row["sla_status"],
        },

        "lifecycle": {
            "detected_at": row[
                "detected_at"
            ],
            "first_seen_at": row[
                "first_seen_at"
            ],
            "last_seen_at": row[
                "last_seen_at"
            ],
            "break_status": row[
                "break_status"
            ],
        },
    }

    return clean_payload(payload)


# --------------------------------------------------
# JSON-safe conversion
# --------------------------------------------------

def clean_payload(value):
    """
    Convert pandas / NumPy values into normal
    Python JSON-compatible values.
    """

    if isinstance(value, dict):
        return {
            key: clean_payload(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            clean_payload(item)
            for item in value
        ]

    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        return value.item()

    return value


# --------------------------------------------------
# Send one break
# --------------------------------------------------

def send_break(payload):

    response = requests.post(
        N8N_WEBHOOK_URL,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    return response


# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":

    breaks = load_breaks_for_triage()

    print()
    print(
        "TradeOps → n8n integration"
    )
    print("-" * 45)

    print(
        f"Eligible breaks: {len(breaks)}"
    )

    print()

    success_count = 0
    failure_count = 0

    for _, row in breaks.iterrows():

        payload = build_payload(
            row
        )

        try:

            response = send_break(
                payload
            )

            success_count += 1

            print(
                f"✓ Sent "
                f"{row['break_id']} "
                f"| {row['trade_id']} "
                f"| {row['exception_type']} "
                f"| {row['severity']}"
            )

        except requests.RequestException as exc:

            failure_count += 1

            print(
                f"✗ Failed "
                f"{row['break_id']}: "
                f"{exc}"
            )

    print()
    print("-" * 45)

    print(
        f"Successfully sent: "
        f"{success_count}"
    )

    print(
        f"Failed: "
        f"{failure_count}"
    )