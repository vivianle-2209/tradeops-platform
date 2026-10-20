import duckdb


DB_PATH = "data/tradeops.duckdb"


con = duckdb.connect(DB_PATH)

print("\nTables:")
print(con.execute("SHOW TABLES").fetchdf())

print("\nTrade break summary:")
print(
    con.execute(
        """
        SELECT
            exception_type,
            severity,
            COUNT(*) AS break_count
        FROM trade_breaks
        GROUP BY
            exception_type,
            severity
        ORDER BY
            break_count DESC
        """
    ).fetchdf()
)

print("\nTop priority breaks:")
print(
    con.execute(
        """
        SELECT
            priority_rank,
            break_id,
            trade_id,
            exception_type,
            severity_score,
            severity,
            execution_notional,
            affected_notional
        FROM trade_breaks
        ORDER BY priority_rank
        LIMIT 10
        """
    ).fetchdf()
)

con.close()