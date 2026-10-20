import os

import duckdb
import pandas as pd


DB_PATH = "data/tradeops.duckdb"

EXECUTIONS_PATH = "data/processed/executions.csv"
CLEARING_PATH = "data/processed/clearing.csv"
RECON_PATH = "data/processed/reconciliation_results.csv"
BREAKS_PATH = "data/processed/trade_breaks_sla.csv"

def load_csv(path):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    return pd.read_csv(path)


def load_database():
    """
    Load TradeOps processed datasets into DuckDB.
    """

    executions = load_csv(
        EXECUTIONS_PATH
    )

    clearing = load_csv(
        CLEARING_PATH
    )

    reconciliation = load_csv(
        RECON_PATH
    )

    trade_breaks = load_csv(
        BREAKS_PATH
    )

    os.makedirs(
        "data",
        exist_ok=True,
    )

    con = duckdb.connect(
        DB_PATH
    )

    # ------------------------------------------
    # Executions
    # ------------------------------------------

    con.register(
        "executions_df",
        executions,
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE executions AS
        SELECT *
        FROM executions_df
        """
    )

    # ------------------------------------------
    # Clearing
    # ------------------------------------------

    con.register(
        "clearing_df",
        clearing,
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE clearing_records AS
        SELECT *
        FROM clearing_df
        """
    )

    # ------------------------------------------
    # Reconciliation
    # ------------------------------------------

    con.register(
        "reconciliation_df",
        reconciliation,
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE reconciliation_results AS
        SELECT *
        FROM reconciliation_df
        """
    )

    # ------------------------------------------
    # Trade breaks
    # ------------------------------------------

    con.register(
        "trade_breaks_df",
        trade_breaks,
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE trade_breaks AS
        SELECT *
        FROM trade_breaks_df
        """
    )

    # ------------------------------------------
    # Validation
    # ------------------------------------------

    tables = con.execute(
        """
        SHOW TABLES
        """
    ).fetchdf()

    print()
    print(
        "TradeOps database load complete"
    )
    print("-" * 45)

    print()
    print("Database tables:")
    print(
        tables.to_string(
            index=False
        )
    )

    print()

    for table in [
        "executions",
        "clearing_records",
        "reconciliation_results",
        "trade_breaks",
    ]:

        count = con.execute(
            f"""
            SELECT COUNT(*)
            FROM {table}
            """
        ).fetchone()[0]

        print(
            f"{table}: {count} rows"
        )

    con.close()

    print()
    print(
        f"Database saved to: {DB_PATH}"
    )


if __name__ == "__main__":
    load_database()