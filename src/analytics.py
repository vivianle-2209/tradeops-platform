"""Parameterized historical SQL; Streamlit owns caching, not business aggregation."""
from zoneinfo import ZoneInfo
import pandas as pd

METRICS = {"Trades": "total_trades", "Breaks": "broken_trades", "Break Rate": "break_rate",
           "Affected Notional": "affected_notional"}
GRANULARITIES = {"Daily": "date_trunc('day', snapshot_local)",
                 "Hourly": "date_trunc('hour', snapshot_local)",
                 "30-minute": "date_trunc('hour', snapshot_local) + INTERVAL '30 minutes' * FLOOR(EXTRACT(minute FROM snapshot_local)/30)",
                 "Intraday": "strftime(snapshot_local, '%H:') || CASE WHEN EXTRACT(minute FROM snapshot_local)<30 THEN '00' ELSE '30' END"}


def _scope(start=None, end=None, symbols=(), timezone_name="UTC", alias="h"):
    ZoneInfo(timezone_name)
    clauses, params = [], []
    if start is not None:
        clauses.append(f"CAST(timezone(?, {alias}.snapshot_at) AS DATE) >= CAST(? AS DATE)")
        params += [timezone_name, start]
    if end is not None:
        clauses.append(f"CAST(timezone(?, {alias}.snapshot_at) AS DATE) <= CAST(? AS DATE)")
        params += [timezone_name, end]
    if symbols:
        clauses.append(f"{alias}.symbol IN ({','.join('?' for _ in symbols)})")
        params += list(symbols)
    return " AND ".join(clauses) or "TRUE", params


def history_runs(con, start=None, end=None, symbols=(), timezone_name="UTC"):
    where, params = _scope(start, end, symbols, timezone_name)
    # Exposure is grouped at trade grain before summing, independently of exception count.
    return con.execute(f"""WITH scoped AS (
        SELECT h.* FROM reconciliation_history h WHERE {where}
    ), exposure AS (
        SELECT b.snapshot_id, b.trade_id, MAX(b.affected_notional) AS amount
        FROM trade_breaks_history b JOIN scoped s USING (snapshot_id, trade_id)
        WHERE b.break_status='OPEN' GROUP BY b.snapshot_id, b.trade_id
    ), totals AS (
        SELECT snapshot_id, SUM(amount) AS affected_notional FROM exposure GROUP BY snapshot_id
    ) SELECT h.snapshot_id, h.run_id, MAX(h.snapshot_at) AS snapshot_at,
        COUNT(*) AS total_trades, COUNT(*) FILTER (WHERE reconciliation_status='MATCHED') AS matched_trades,
        COUNT(*) FILTER (WHERE reconciliation_status='BREAK') AS broken_trades,
        100.0*COUNT(*) FILTER (WHERE reconciliation_status='BREAK')/COUNT(*) AS break_rate,
        COALESCE(MAX(t.affected_notional),0) AS affected_notional, COUNT(DISTINCT symbol) AS symbol_count,
        MAX(p.snapshot_number) AS snapshot_number, MAX(p.status) AS status
        FROM scoped h LEFT JOIN totals t USING (snapshot_id)
        JOIN pipeline_runs p ON p.run_id=h.run_id
        GROUP BY h.snapshot_id, h.run_id ORDER BY snapshot_at""", params).fetchdf()


def history_trend(con, start=None, end=None, symbols=(), metric="Trades", granularity="Daily", timezone_name="UTC"):
    column = METRICS[metric]
    bucket = GRANULARITIES[granularity]
    # Register only scoped per-snapshot summaries, not raw historical observations.
    runs = history_runs(con, start, end, symbols, timezone_name)
    con.register("history_scope", runs)
    try:
        expression = ("100.0*SUM(broken_trades)/NULLIF(SUM(total_trades),0)" if metric == "Break Rate"
                      else f"SUM({column})")
        name = "time_of_day" if granularity == "Intraday" else "time_bucket"
        return con.execute(f"""WITH local AS (SELECT *, timezone(?, snapshot_at) AS snapshot_local FROM history_scope)
            SELECT {bucket} AS {name}, {expression} AS {column}
            FROM local GROUP BY {name} ORDER BY {name}""", [timezone_name]).fetchdf()
    finally:
        con.unregister("history_scope")


def history_symbols(con, start=None, end=None, timezone_name="UTC"):
    where, params = _scope(start, end, (), timezone_name)
    return [row[0] for row in con.execute(
        f"SELECT DISTINCT symbol FROM reconciliation_history h WHERE {where} ORDER BY symbol", params).fetchall()]


def history_observations(con, snapshot_id, symbols=()):
    condition = "snapshot_id=?"
    params = [snapshot_id]
    if symbols:
        condition += f" AND symbol IN ({','.join('?' for _ in symbols)})"
        params += list(symbols)
    return tuple(con.execute(f'SELECT * FROM {table} WHERE {condition}', params).fetchdf()
                 for table in ["reconciliation_history", "trade_breaks_history"])


def history_severity(con, start=None, end=None, symbols=(), timezone_name="UTC"):
    where, params = _scope(start, end, symbols, timezone_name)
    return con.execute(f"""SELECT date_trunc('day', timezone(?, snapshot_at)) AS date, severity,
        COUNT(*) AS breaks FROM trade_breaks_history h WHERE {where} AND break_status='OPEN'
        GROUP BY date, severity ORDER BY date""", [timezone_name, *params]).fetchdf()


def aggregate_break_rate(frame, bucket_column):
    grouped = frame.groupby(bucket_column, as_index=False).agg(
        matched_trades=("matched_trades", "sum"), broken_trades=("broken_trades", "sum"))
    denominator = grouped.matched_trades + grouped.broken_trades
    grouped["break_rate"] = (grouped.broken_trades / denominator.replace(0, float("nan")) * 100).fillna(0)
    return grouped


def aggregate_metric(frame, bucket_column, metric):
    if frame.empty:
        return pd.DataFrame()
    column = METRICS[metric]
    return (aggregate_break_rate(frame, bucket_column)[[bucket_column, column]] if metric == "Break Rate"
            else frame.groupby(bucket_column, as_index=False)[column].sum())
