"""
Data layer: DuckDB loading, live SLA ageing, filtering, KPIs and the
per-run context shared between the entrypoint and pages.

A short-lived read-only connection is opened per query so the dashboard
never holds a file lock that would block the pipeline from writing. The DB
file's mtime is part of every cache key, so a pipeline run invalidates
cached data on the next refresh.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "tradeops.duckdb"

# Same rule as src/sla.py: a break is AT_RISK once 75% of its window is used.
SLA_AT_RISK_FRACTION = 0.75

TIMESTAMP_COLUMNS = [
    "execution_timestamp",
    "clearing_timestamp",
    "detected_at",
    "first_seen_at",
    "last_seen_at",
    "resolved_at",
]
NUMERIC_BREAK_COLUMNS = [
    "priority_rank",
    "severity_score",
    "age_minutes",
    "sla_minutes",
    "sla_remaining_minutes",
    "sla_consumed_pct",
    "execution_notional",
    "affected_notional",
    "clearing_latency_seconds",
]
TEXT_BREAK_COLUMNS = [
    "severity", "exception_type", "sla_status", "break_status", "venue",
    "trade_id", "break_id", "dedup_key", "account_exec", "symbol_exec",
]


# --------------------------------------------------
# Loading
# --------------------------------------------------

def db_version() -> float:
    return DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0


def run_query(sql: str, params: list | None = None) -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.execute(sql, params or []).fetchdf()


def parse_timestamps(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce", utc=True)
    return df


def prepare_breaks(breaks: pd.DataFrame) -> pd.DataFrame:
    """Type-coerce trade_breaks and guarantee the columns the UI relies on."""
    breaks = parse_timestamps(breaks, TIMESTAMP_COLUMNS)
    for column in NUMERIC_BREAK_COLUMNS:
        if column not in breaks.columns:
            breaks[column] = np.nan
        breaks[column] = pd.to_numeric(breaks[column], errors="coerce")
    for column in TEXT_BREAK_COLUMNS:
        if column not in breaks.columns:
            breaks[column] = pd.NA
    breaks["venue"] = breaks["venue"].fillna("UNKNOWN")
    return breaks


@st.cache_data(ttl=60, show_spinner=False)
def load_tables(version: float) -> dict:
    """Load reconciliation results and trade breaks (cached per DB version)."""
    reconciliation = run_query("SELECT * FROM reconciliation_results")
    breaks = run_query("SELECT * FROM trade_breaks ORDER BY priority_rank")
    return {
        "reconciliation": parse_timestamps(reconciliation, ["execution_timestamp", "clearing_timestamp"]),
        "breaks": prepare_breaks(breaks),
        "loaded_at": datetime.now(timezone.utc),
        "version": version,
    }


@st.cache_data(ttl=60, show_spinner=False, max_entries=256)
def load_trade_records(
    trade_id: str,
    version: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Execution and clearing source records for one trade."""

    execution = run_query(
        "SELECT * FROM executions WHERE trade_id = ?",
        [trade_id],
    )

    clearing = run_query(
        "SELECT * FROM clearing_records WHERE trade_id = ?",
        [trade_id],
    )

    return (
        parse_timestamps(
            execution,
            ["execution_timestamp"],
        ),
        parse_timestamps(
            clearing,
            ["clearing_timestamp"],
        ),
    )


# --------------------------------------------------
# Jira / n8n incident API
# --------------------------------------------------

@st.cache_data(ttl=15, show_spinner=False)
def load_jira_incidents() -> pd.DataFrame:
    try:
        url = st.secrets["N8N_INCIDENT_API_URL"]

        response = requests.get(
            url,
            timeout=10,
        )

        response.raise_for_status()

        payload = response.json()

        if not payload:
            return pd.DataFrame()

        incidents = pd.DataFrame(payload)

        expected_columns = [
            "dedup_key",
            "break_id",
            "trade_id",
            "break_type",
            "severity",
            "status",
            "jira_issue_key",
            "jira_issue_url",
            "first_seen_at",
            "last_seen_at",
        ]

        for column in expected_columns:
            if column not in incidents.columns:
                incidents[column] = pd.NA

        incidents = parse_timestamps(
            incidents,
            [
                "first_seen_at",
                "last_seen_at",
            ],
        )

        return incidents

    except Exception:
        return pd.DataFrame()


def attach_jira_incidents(
    breaks: pd.DataFrame,
    incidents: pd.DataFrame,
) -> pd.DataFrame:
    """
    Attach Jira incident metadata to TradeOps
    breaks using dedup_key.
    """

    result = breaks.copy()

    jira_columns = [
        "jira_issue_key",
        "jira_issue_url",
        "jira_status",
        "jira_first_seen_at",
        "jira_last_seen_at",
    ]

    if incidents.empty:
        for column in jira_columns:
            if column not in result.columns:
                result[column] = pd.NA

        return result

    incident_view = incidents[
        [
            "dedup_key",
            "jira_issue_key",
            "jira_issue_url",
            "status",
            "first_seen_at",
            "last_seen_at",
        ]
    ].copy()

    incident_view = incident_view.rename(
        columns={
            "status": "jira_status",
            "first_seen_at": "jira_first_seen_at",
            "last_seen_at": "jira_last_seen_at",
        }
    )

    incident_view = (
        incident_view
        .sort_values(
            "jira_last_seen_at",
            ascending=False,
            na_position="last",
        )
        .drop_duplicates(
            subset=["dedup_key"],
            keep="first",
        )
    )

    result = result.merge(
        incident_view,
        on="dedup_key",
        how="left",
        validate="many_to_one",
    )

    return result


def clear_caches() -> None:
    load_tables.clear()
    load_trade_records.clear()
    load_jira_incidents.clear()


def load_data() -> tuple[dict | None, str, str | None]:
    """
    Returns (data, db_status, error). If the database is momentarily locked
    by a pipeline run, the last successful snapshot is served as STALE.
    """
    try:
        data = load_tables(db_version())
        st.session_state["_last_good_data"] = data
        return data, "CONNECTED", None
    except Exception as exc:  # duckdb.IOException, missing file, missing table…
        cached = st.session_state.get("_last_good_data")
        if cached is not None:
            return cached, "STALE", str(exc)
        return None, "UNAVAILABLE", str(exc)


# --------------------------------------------------
# Business views
# --------------------------------------------------

def apply_live_sla(breaks: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """
    Re-age OPEN breaks against the wall clock using the same thresholds and
    classification as src/sla.py. Stored sla_minutes are reused unchanged.
    """
    df = breaks.copy()
    is_open = df["break_status"].eq("OPEN")
    live_age = ((now - df["first_seen_at"]).dt.total_seconds() / 60).clip(lower=0)
    df.loc[is_open, "age_minutes"] = live_age[is_open]
    df["sla_remaining_minutes"] = df["sla_minutes"] - df["age_minutes"]
    df["sla_consumed_pct"] = df["age_minutes"] / df["sla_minutes"] * 100
    df["sla_status"] = np.select(
        [
            ~is_open,
            df["sla_minutes"].isna(),
            df["age_minutes"] > df["sla_minutes"],
            df["age_minutes"] >= df["sla_minutes"] * SLA_AT_RISK_FRACTION,
        ],
        ["CLOSED", "UNKNOWN", "BREACHED", "AT_RISK"],
        default="WITHIN_SLA",
    )
    return df


def apply_filters(breaks: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Empty selections mean 'all'; trade search is a case-insensitive substring."""
    mask = pd.Series(True, index=breaks.index)
    for column in ["severity", "sla_status", "break_status", "exception_type", "venue"]:
        if filters.get(column):
            mask &= breaks[column].astype(str).isin(filters[column])
    if filters.get("trade"):
        mask &= breaks["trade_id"].astype(str).str.contains(filters["trade"], case=False, na=False, regex=False)
    return breaks[mask]


def compute_kpis(reconciliation: pd.DataFrame, breaks: pd.DataFrame) -> dict:
    status = reconciliation.get("reconciliation_status", pd.Series(dtype=str))
    total = len(reconciliation)
    matched = int(status.eq("MATCHED").sum())
    broken = int(status.eq("BREAK").sum())
    open_breaks = breaks[breaks["break_status"].eq("OPEN")]
    latency = pd.to_numeric(reconciliation.get("clearing_latency_seconds", pd.Series(dtype=float)), errors="coerce")
    return {
        "total": total,
        "matched": matched,
        "broken": broken,
        "match_rate": matched / total * 100 if total else 0.0,
        "break_rate": broken / total * 100 if total else 0.0,
        "critical": int(breaks["severity"].eq("CRITICAL").sum()),
        "affected": float(breaks["affected_notional"].fillna(0).sum()),
        "break_count": len(breaks),
        "breached": int(breaks["sla_status"].eq("BREACHED").sum()),
        "at_risk": int(breaks["sla_status"].eq("AT_RISK").sum()),
        "avg_age": float(open_breaks["age_minutes"].mean()) if len(open_breaks) else 0.0,
        "avg_latency": float(latency.mean()) if latency.notna().any() else float("nan"),
        "open": len(open_breaks),
    }


# --------------------------------------------------
# Per-run context shared with pages
# --------------------------------------------------

@dataclass
class DashboardContext:
    reconciliation: pd.DataFrame
    breaks: pd.DataFrame       # all breaks (live-aged if the SLA clock is on)
    filtered: pd.DataFrame     # breaks after sidebar filters
    kpis: dict                 # firm-wide KPIs (unfiltered)
    version: float             # DB mtime, used as a cache key
    now: pd.Timestamp


def set_context(ctx: DashboardContext) -> None:
    st.session_state["_ctx"] = ctx


def get_context() -> DashboardContext:
    """Context built by the entrypoint (dashboard/app.py) on this run."""
    ctx = st.session_state.get("_ctx")
    if ctx is None:
        st.error("Dashboard context missing. Start the app with `streamlit run dashboard/app.py`.")
        st.stop()
    return ctx
