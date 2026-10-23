"""Explicit, versioned DuckDB schema and small transaction helpers.

Schema initialization is lazy: importing or testing never opens the real database.
Migration 1 accepts a fresh DB or the user's empty legacy baseline, never data loss.
"""
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd

from src.contracts import (EXECUTION, CLEARING, RECONCILIATION, INCIDENT, OUTBOX,
                           PIPELINE_RUN, HISTORY_META, normalize_frame)

SCHEMA_VERSION = 1
TABLES = {
    "executions": (EXECUTION, "PRIMARY KEY (trade_id)"),
    "clearing_records": (CLEARING, "PRIMARY KEY (clearing_id)"),
    "reconciliation_results": (RECONCILIATION, "PRIMARY KEY (trade_id)"),
    "incidents": (INCIDENT, "PRIMARY KEY (dedup_key), UNIQUE (incident_id), UNIQUE (break_id)"),
    "incident_outbox": (OUTBOX, "PRIMARY KEY (event_id), UNIQUE (incident_id, event_version)"),
    "pipeline_runs": (PIPELINE_RUN, "PRIMARY KEY (run_id), UNIQUE (snapshot_id), UNIQUE (snapshot_number)"),
    "reconciliation_history": ({**HISTORY_META, **RECONCILIATION}, "PRIMARY KEY (snapshot_id, trade_id)"),
    "trade_breaks_history": ({**HISTORY_META, **INCIDENT}, "PRIMARY KEY (snapshot_id, dedup_key)"),
    "ingestion_checkpoints": ({"source": "VARCHAR", "symbol": "VARCHAR", "position": "TIMESTAMPTZ",
                               "run_id": "VARCHAR", "updated_at": "TIMESTAMPTZ"}, "PRIMARY KEY (source, symbol)"),
}


def table_names(con):
    return {row[0] for row in con.execute("SHOW TABLES").fetchall()}


def ensure_schema(con):
    names = table_names(con)
    if "schema_migrations" in names:
        version = con.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"Database schema {version} is newer than this worker")
        if version == SCHEMA_VERSION:
            return
    else:
        # Only these known, empty reset tables may be replaced. Archives/backups
        # and every unrelated table remain untouched.
        legacy = names & {"executions", "clearing_records", "reconciliation_results", "trade_breaks",
                          "pipeline_runs", "reconciliation_history", "trade_breaks_history"}
        if any(con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in legacy):
            raise RuntimeError("Legacy data requires an explicit migration; refusing to replace it")
        for name in sorted(legacy):
            con.execute(f'DROP TABLE "{name}"')
    con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ)")
    for table, (schema, constraint) in TABLES.items():
        columns = ", ".join(f'"{name}" {dtype}' for name, dtype in schema.items())
        con.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({columns}, {constraint})')
    con.execute("CREATE OR REPLACE VIEW trade_breaks AS SELECT * FROM incidents")
    con.execute("INSERT INTO schema_migrations VALUES (?, CURRENT_TIMESTAMP)", [SCHEMA_VERSION])


@contextmanager
def transaction(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path)) as con:
        con.execute("BEGIN TRANSACTION")
        try:
            ensure_schema(con)
            yield con
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise


def read_frame(con, table, schema):
    if table not in table_names(con):
        return normalize_frame(pd.DataFrame(), schema)
    return normalize_frame(con.execute(f'SELECT * FROM "{table}"').fetchdf(), schema)


def write_frame(con, table, frame, *, replace_keys=()):
    schema = TABLES[table][0]
    frame = normalize_frame(frame, schema, key=replace_keys)
    if frame.empty:
        return
    con.register("stage_frame", frame)
    try:
        if replace_keys:
            condition = " AND ".join(f't."{key}" = s."{key}"' for key in replace_keys)
            con.execute(f'DELETE FROM "{table}" AS t USING stage_frame AS s WHERE {condition}')
        columns = ", ".join(f'"{name}"' for name in schema)
        con.execute(f'INSERT INTO "{table}" ({columns}) SELECT {columns} FROM stage_frame')
    finally:
        con.unregister("stage_frame")
