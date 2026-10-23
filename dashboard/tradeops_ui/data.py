"""
TradeOps dashboard data layer.

Responsibilities:
- Read DuckDB safely
- Parse / normalise TradeOps data
- Apply live SLA ageing
- Apply global symbol scope
- Apply operational filters
- Calculate scope-aware KPIs
- Load n8n / Jira incident registry
- Provide the shared DashboardContext used by pages
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


# --------------------------------------------------
# Project paths
# --------------------------------------------------

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "tradeops.duckdb"
)


# --------------------------------------------------
# SLA behaviour
# --------------------------------------------------

# Streamlit launches from dashboard/ in some deployments.
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.metrics import total_exposure, exposure_by_group
from src.config import SLA_AT_RISK_FRACTION


# --------------------------------------------------
# Schema helpers
# --------------------------------------------------

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
    "exception_impact",
    "trade_exposure",
    "clearing_notional",
    "clearing_latency_seconds",
    "quantity_exec",
    "quantity_clear",
    "quantity_difference",
    "price_exec",
    "price_clear",
    "price_difference",
]


TEXT_BREAK_COLUMNS = [
    "severity",
    "exception_type",
    "sla_status",
    "break_status",
    "venue",
    "trade_id",
    "break_id",
    "dedup_key",
    "account_exec",
    "symbol",
    "symbol_exec",
    "symbol_clear",
    "side_exec",
    "side_clear",
    "currency_exec",
    "currency_clear",
    "clearing_status",
]


# --------------------------------------------------
# Database
# --------------------------------------------------

def db_version() -> float:
    """
    Use the database modification time as the
    Streamlit cache version.
    """

    if not DB_PATH.exists():
        return 0.0

    return (
        DB_PATH
        .stat()
        .st_mtime
    )


def run_query(
    sql: str,
    params: list | None = None,
) -> pd.DataFrame:
    """
    Open a short-lived read-only DuckDB connection.

    This avoids the dashboard keeping a permanent
    lock while the pipeline needs to update the DB.
    """

    with duckdb.connect(
        str(DB_PATH),
        read_only=True,
    ) as con:

        return (
            con.execute(
                sql,
                params or [],
            )
            .fetchdf()
        )


# --------------------------------------------------
# Parsing
# --------------------------------------------------

def parse_timestamps(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:

    df = df.copy()

    for column in columns:

        if column in df.columns:

            df[column] = (
                pd.to_datetime(
                    df[column],
                    errors="coerce",
                    utc=True,
                )
            )

    return df


def prepare_breaks(
    breaks: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalise the trade-break table and guarantee
    columns required by the dashboard.
    """

    breaks = parse_timestamps(
        breaks,
        TIMESTAMP_COLUMNS,
    )


    for column in (
        NUMERIC_BREAK_COLUMNS
    ):

        if column not in breaks.columns:

            breaks[column] = np.nan

        breaks[column] = (
            pd.to_numeric(
                breaks[column],
                errors="coerce",
            )
        )


    for column in (
        TEXT_BREAK_COLUMNS
    ):

        if column not in breaks.columns:

            breaks[column] = pd.NA


    breaks["venue"] = (
        breaks["venue"]
        .fillna("UNKNOWN")
    )


    return breaks


# --------------------------------------------------
# Main table loading
# --------------------------------------------------

@st.cache_data(ttl=60, max_entries=8, show_spinner=False)
def load_tables(version: float) -> dict:
    # Read related tables under one database snapshot.
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        con.execute('BEGIN TRANSACTION')
        reconciliation = con.execute('SELECT * FROM reconciliation_results').fetchdf()
        breaks = con.execute('SELECT * FROM trade_breaks ORDER BY priority_rank').fetchdf()
        names = {row[0] for row in con.execute('SHOW TABLES').fetchall()}
        latest_run = con.execute('SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1').fetchdf() if 'pipeline_runs' in names else pd.DataFrame()
        con.execute('COMMIT')
    return dict(reconciliation=parse_timestamps(reconciliation, ['execution_timestamp', 'clearing_timestamp']),
                breaks=prepare_breaks(breaks), latest_run=latest_run,
                loaded_at=datetime.now(timezone.utc), version=version)



# --------------------------------------------------
# Trade source records
# --------------------------------------------------

@st.cache_data(
    ttl=60,
    show_spinner=False,
    max_entries=256,
)
def load_trade_records(
    trade_id: str,
    version: float,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Return execution and clearing records for
    one TradeOps trade.
    """

    execution = run_query(
        """
        SELECT *
        FROM executions
        WHERE trade_id = ?
        """,
        [
            trade_id
        ],
    )


    clearing = run_query(
        """
        SELECT *
        FROM clearing_records
        WHERE trade_id = ?
        """,
        [
            trade_id
        ],
    )


    execution = parse_timestamps(
        execution,
        [
            "execution_timestamp"
        ],
    )


    clearing = parse_timestamps(
        clearing,
        [
            "clearing_timestamp"
        ],
    )


    return (
        execution,
        clearing,
    )


# --------------------------------------------------
# Jira / n8n incident API
# --------------------------------------------------

@st.cache_data(
    ttl=15,
    show_spinner=False,
)
def load_jira_incidents() -> pd.DataFrame:
    """
    Load incidents from the TradeOps n8n Incident
    API.

    This is intentionally independent from DuckDB.
    """

    try:

        url = (
            st.secrets[
                "N8N_INCIDENT_API_URL"
            ]
        )


        response = requests.get(
            url,
            timeout=10,
        )

        response.raise_for_status()


        payload = (
            response.json()
        )


        if not payload:

            return pd.DataFrame()


        incidents = (
            pd.DataFrame(
                payload
            )
        )


        expected_columns = [
            "dedup_key",
            "break_id",
            "trade_id",
            "symbol",
            "break_type",
            "severity",
            "status",
            "jira_issue_key",
            "jira_issue_url",
            "first_seen_at",
            "last_seen_at",
        ]


        for column in (
            expected_columns
        ):

            if column not in incidents.columns:

                incidents[column] = (
                    pd.NA
                )


        incidents = (
            parse_timestamps(
                incidents,
                [
                    "first_seen_at",
                    "last_seen_at",
                ],
            )
        )


        return incidents


    except Exception as exc:
        raise RuntimeError(f"Incident registry is unavailable ({type(exc).__name__})") from exc


# --------------------------------------------------
# Attach Jira metadata to breaks
# --------------------------------------------------

def attach_jira_incidents(
    breaks: pd.DataFrame,
    incidents: pd.DataFrame,
) -> pd.DataFrame:

    result = (
        breaks.copy()
    )


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

                result[column] = (
                    pd.NA
                )

        return result


    incident_view = (
        incidents[
            [
                "dedup_key",
                "jira_issue_key",
                "jira_issue_url",
                "status",
                "first_seen_at",
                "last_seen_at",
            ]
        ]
        .copy()
    )


    incident_view = (
        incident_view.rename(
            columns={
                "status": (
                    "jira_status"
                ),
                "first_seen_at": (
                    "jira_first_seen_at"
                ),
                "last_seen_at": (
                    "jira_last_seen_at"
                ),
            }
        )
    )


    incident_view = (
        incident_view
        .sort_values(
            "jira_last_seen_at",
            ascending=False,
            na_position="last",
        )
        .drop_duplicates(
            subset=[
                "dedup_key"
            ],
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


# --------------------------------------------------
# Cache controls
# --------------------------------------------------

def clear_caches() -> None:

    load_tables.clear()
    load_trade_records.clear()
    load_jira_incidents.clear()
    load_history_runs.clear()
    load_history_observations.clear()
    load_history_trend.clear()
    load_history_symbols.clear()
    load_history_severity.clear()


# --------------------------------------------------
# App-level load
# --------------------------------------------------

def load_data() -> tuple[
    dict | None,
    str,
    str | None,
]:
    """
    Return:
        data
        database status
        optional error

    If DuckDB is briefly locked while the pipeline
    writes, serve the previous good snapshot.
    """

    try:

        data = load_tables(
            db_version()
        )


        st.session_state[
            "_last_good_data"
        ] = data


        return (
            data,
            "CONNECTED",
            None,
        )


    except Exception as exc:

        cached = (
            st.session_state.get(
                "_last_good_data"
            )
        )


        if cached is not None:

            return (
                cached,
                "STALE",
                str(exc),
            )


        return (
            None,
            "UNAVAILABLE",
            str(exc),
        )


# --------------------------------------------------
# Live SLA clock
# --------------------------------------------------

def apply_live_sla(breaks: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    from src.sla import age_incident
    if breaks.empty:
        return breaks.copy()
    return pd.DataFrame([age_incident(row, now) for row in breaks.to_dict('records')])



# --------------------------------------------------
# Global market scope
# --------------------------------------------------

def apply_reconciliation_scope(
    reconciliation: pd.DataFrame,
    selected_symbols: list[str],
) -> pd.DataFrame:
    """
    Restrict reconciliation data to the globally
    selected market symbols.

    Empty selection means all symbols.
    """

    if reconciliation.empty:

        return (
            reconciliation.copy()
        )


    if not selected_symbols:

        return (
            reconciliation.copy()
        )


    if (
        "symbol"
        not in reconciliation.columns
    ):

        return (
            reconciliation.copy()
        )


    return (
        reconciliation[
            reconciliation[
                "symbol"
            ]
            .astype(str)
            .isin(
                selected_symbols
            )
        ]
        .copy()
    )


def apply_break_scope(
    breaks: pd.DataFrame,
    selected_symbols: list[str],
) -> pd.DataFrame:
    """
    Apply global symbol scope to trade breaks.

    Empty selection means all symbols.
    """

    if breaks.empty:

        return breaks.copy()


    if not selected_symbols:

        return breaks.copy()


    if (
        "symbol"
        not in breaks.columns
    ):

        return breaks.copy()


    return (
        breaks[
            breaks[
                "symbol"
            ]
            .astype(str)
            .isin(
                selected_symbols
            )
        ]
        .copy()
    )


# --------------------------------------------------
# Operational filters
# --------------------------------------------------

def apply_filters(
    breaks: pd.DataFrame,
    filters: dict,
) -> pd.DataFrame:
    """
    Apply sidebar operational filters.

    Empty selections mean ALL.
    """

    if breaks.empty:

        return (
            breaks.copy()
        )


    mask = pd.Series(
        True,
        index=breaks.index,
    )


    filter_columns = [
        "severity",
        "sla_status",
        "break_status",
        "exception_type",
        "venue",
    ]


    for column in (
        filter_columns
    ):

        selected = (
            filters.get(
                column
            )
        )


        if selected:

            mask &= (
                breaks[column]
                .astype(str)
                .isin(
                    selected
                )
            )


    # Optional support if symbol is passed through
    # filters elsewhere.
    selected_symbols = (
        filters.get(
            "symbol"
        )
    )


    if (
        selected_symbols
        and
        "symbol"
        in breaks.columns
    ):

        mask &= (
            breaks[
                "symbol"
            ]
            .astype(str)
            .isin(
                selected_symbols
            )
        )


    trade_search = (
        filters.get(
            "trade",
            "",
        )
    )


    if trade_search:

        mask &= (
            breaks[
                "trade_id"
            ]
            .astype(str)
            .str.contains(
                trade_search,
                case=False,
                na=False,
                regex=False,
            )
        )


    return (
        breaks[
            mask
        ]
        .copy()
    )


# --------------------------------------------------
# KPI calculation
# --------------------------------------------------

def compute_kpis(
    reconciliation: pd.DataFrame,
    breaks: pd.DataFrame,
) -> dict:
    """
    Calculate dashboard KPIs for the supplied scope.

    IMPORTANT:
    reconciliation should already have the global
    symbol scope applied.

    breaks should already have both the global
    symbol scope and operational filters applied.
    """

    # --------------------------------------------------
    # Trading reconciliation
    # --------------------------------------------------

    total = (
        len(
            reconciliation
        )
    )


    if (
        "reconciliation_status"
        in reconciliation.columns
    ):

        status = (
            reconciliation[
                "reconciliation_status"
            ]
            .astype(str)
        )

    else:

        status = pd.Series(
            dtype=str
        )


    matched = int(
        status
        .eq("MATCHED")
        .sum()
    )


    broken = int(
        status
        .eq("BREAK")
        .sum()
    )


    match_rate = (
        matched
        / total
        * 100
        if total
        else 0.0
    )


    break_rate = (
        broken
        / total
        * 100
        if total
        else 0.0
    )


    # --------------------------------------------------
    # Exception population
    # --------------------------------------------------

    if breaks.empty:

        open_breaks = (
            breaks.copy()
        )

    else:

        open_breaks = (
            breaks[
                breaks[
                    "break_status"
                ]
                .eq("OPEN")
            ]
        )


    critical = (
        int(
            open_breaks[
                "severity"
            ]
            .eq("CRITICAL")
            .sum()
        )
        if (
            "severity"
            in breaks.columns
        )
        else 0
    )


    breached = (
        int(
            breaks[
                "sla_status"
            ]
            .eq("BREACHED")
            .sum()
        )
        if (
            "sla_status"
            in breaks.columns
        )
        else 0
    )


    at_risk = (
        int(
            breaks[
                "sla_status"
            ]
            .eq("AT_RISK")
            .sum()
        )
        if (
            "sla_status"
            in breaks.columns
        )
        else 0
    )


    # --------------------------------------------------
    # Exposure
    # --------------------------------------------------

    affected = total_exposure(breaks)


    # --------------------------------------------------
    # Average age
    # --------------------------------------------------

    if (
        not open_breaks.empty
        and
        "age_minutes"
        in open_breaks.columns
    ):

        avg_age_value = (
            pd.to_numeric(
                open_breaks[
                    "age_minutes"
                ],
                errors="coerce",
            )
            .mean()
        )


        avg_age = (
            float(
                avg_age_value
            )
            if pd.notna(
                avg_age_value
            )
            else 0.0
        )

    else:

        avg_age = 0.0


    # --------------------------------------------------
    # Clearing latency
    # --------------------------------------------------

    if (
        "clearing_latency_seconds"
        in reconciliation.columns
    ):

        latency = (
            pd.to_numeric(
                reconciliation[
                    "clearing_latency_seconds"
                ],
                errors="coerce",
            )
        )


        avg_latency = (
            float(
                latency.mean()
            )
            if latency.notna().any()
            else float("nan")
        )

    else:

        avg_latency = (
            float("nan")
        )


    return {
        "total": total,
        "matched": matched,
        "broken": broken,
        "match_rate": match_rate,
        "break_rate": break_rate,
        "critical": critical,
        "affected": affected,
        "break_count": int(
            len(
                breaks
            )
        ),
        "breached": breached,
        "at_risk": at_risk,
        "avg_age": avg_age,
        "avg_latency": (
            avg_latency
        ),
        "open": int(
            len(
                open_breaks
            )
        ),
    }


# --------------------------------------------------
# Dashboard context
# --------------------------------------------------

@dataclass
class DashboardContext:

    # Globally symbol-scoped reconciliation data
    reconciliation: pd.DataFrame

    # Globally symbol-scoped breaks
    breaks: pd.DataFrame

    # Breaks after global symbol scope + sidebar
    # operational filters
    filtered: pd.DataFrame

    # KPIs for the current dashboard scope
    kpis: dict

    # DuckDB modification timestamp
    version: float

    # Current UTC time used this Streamlit run
    now: pd.Timestamp


def set_context(
    ctx: DashboardContext,
) -> None:

    st.session_state[
        "_ctx"
    ] = ctx


def get_context() -> DashboardContext:
    """
    Retrieve context prepared by dashboard/app.py.
    """

    ctx = (
        st.session_state.get(
            "_ctx"
        )
    )


    if ctx is None:

        st.error(
            "Dashboard context missing. "
            "Start the application with "
            "`python -m streamlit run dashboard/app.py`."
        )

        st.stop()


    return ctx

# History reads are scoped, bounded in cache, and share a consistent DB transaction.
def _history_query(function, *args):
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        tables = {row[0] for row in con.execute('SHOW TABLES').fetchall()}
        if 'reconciliation_history' not in tables:
            return None  # Expected before the first successful run; other errors propagate.
        con.execute('BEGIN TRANSACTION')
        result = function(con, *args)
        con.execute('COMMIT')
        return result


@st.cache_data(ttl=60, max_entries=32, show_spinner=False)
def load_history_runs(version, start=None, end=None, symbols=(), timezone_name='UTC'):
    from src.analytics import history_runs
    result = _history_query(history_runs, start, end, symbols, timezone_name)
    return pd.DataFrame() if result is None else result


@st.cache_data(ttl=60, max_entries=64, show_spinner=False)
def load_history_trend(version, start=None, end=None, symbols=(), metric='Trades', granularity='Daily', timezone_name='UTC'):
    from src.analytics import history_trend
    result = _history_query(history_trend, start, end, symbols, metric, granularity, timezone_name)
    return pd.DataFrame() if result is None else result


@st.cache_data(ttl=60, max_entries=32, show_spinner=False)
def load_history_symbols(version, start=None, end=None, timezone_name='UTC'):
    from src.analytics import history_symbols
    result = _history_query(history_symbols, start, end, timezone_name)
    return [] if result is None else result


@st.cache_data(ttl=60, max_entries=32, show_spinner=False)
def load_history_observations(version, snapshot_id, symbols=()):
    from src.analytics import history_observations
    result = _history_query(history_observations, snapshot_id, symbols)
    return (pd.DataFrame(), pd.DataFrame()) if result is None else result


@st.cache_data(ttl=60, max_entries=32, show_spinner=False)
def load_history_severity(version, start=None, end=None, symbols=(), timezone_name='UTC'):
    from src.analytics import history_severity
    result = _history_query(history_severity, start, end, symbols, timezone_name)
    return pd.DataFrame() if result is None else result


from src.analytics import aggregate_break_rate, aggregate_metric
