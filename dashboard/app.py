"""
TradeOps — Trading Operations Analytics & Exception Management Platform.

Entrypoint. Builds the shared shell (sidebar, data load, header) on every
run, then hands off to the selected page via top navigation:

    app_pages/overview.py
    app_pages/exception_queue.py
    app_pages/sla_risk.py
    app_pages/trade_investigation.py
    app_pages/jira_incidents.py

Shared logic lives in tradeops_ui/.

Run from the project root:

    streamlit run dashboard/app.py
"""

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from tradeops_ui import data as db
from tradeops_ui.components import (
    render_header,
    render_sidebar_status,
)
from tradeops_ui.sidebar import (
    render_filters,
    render_monitoring_controls,
)
from tradeops_ui.theme import APP_CSS


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="TradeOps",
    page_icon=":material/monitoring:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html(APP_CSS)


# --------------------------------------------------
# Top navigation
# --------------------------------------------------

navigation = st.navigation(
    [
        st.Page(
            "app_pages/overview.py",
            title="Overview",
            icon=":material/space_dashboard:",
            default=True,
        ),
        st.Page(
            "app_pages/exception_queue.py",
            title="Exception Queue",
            icon=":material/format_list_numbered:",
        ),
        st.Page(
            "app_pages/sla_risk.py",
            title="SLA & Risk",
            icon=":material/timer:",
        ),
        st.Page(
            "app_pages/trade_investigation.py",
            title="Trade Investigation",
            icon=":material/manage_search:",
        ),
        st.Page(
            "app_pages/jira_incidents.py",
            title="Jira Incidents",
            icon=":material/confirmation_number:",
        ),
    ],
    position="top",
)


# --------------------------------------------------
# Sidebar monitoring controls
# --------------------------------------------------

with st.sidebar:

    status_slot = st.container()

    monitoring = render_monitoring_controls()

    if monitoring["auto_refresh"]:

        st_autorefresh(
            interval=(
                monitoring["refresh_seconds"]
                * 1000
            ),
            key="tradeops_autorefresh",
        )


# --------------------------------------------------
# Core TradeOps data
# --------------------------------------------------

data, db_status, db_error = db.load_data()

now = pd.Timestamp.now(
    tz="UTC"
)


# --------------------------------------------------
# Sidebar system status
# --------------------------------------------------

with status_slot:

    render_sidebar_status(
        db_status,
        monitoring["auto_refresh"],
        monitoring["refresh_seconds"],
        data,
        monitoring["live_sla"],
    )


# --------------------------------------------------
# Stop if DuckDB unavailable
# --------------------------------------------------

if data is None:

    render_header(
        {},
        db_status,
        monitoring["auto_refresh"],
        now,
    )

    st.error(
        (
            f"Could not read `{db.DB_PATH}`. "
            "Run the pipeline to build the database, "
            "then refresh.\n\n"
            f"{db_error}"
        ),
        icon=":material/database_off:",
    )

    st.stop()


# --------------------------------------------------
# Break data
# --------------------------------------------------

breaks = (
    db.apply_live_sla(
        data["breaks"],
        now,
    )
    if monitoring["live_sla"]
    else data["breaks"].copy()
)


# --------------------------------------------------
# Sidebar filters
# --------------------------------------------------

with st.sidebar:

    st.divider()

    filters = render_filters(
        breaks
    )


# --------------------------------------------------
# KPIs
# --------------------------------------------------

kpis = db.compute_kpis(
    data["reconciliation"],
    breaks,
)


# --------------------------------------------------
# Shared context for core TradeOps pages
#
# Jira data is intentionally NOT loaded here.
# The Jira Incidents page loads it independently
# from the n8n Incident API.
# --------------------------------------------------

db.set_context(
    db.DashboardContext(

        reconciliation=(
            data["reconciliation"]
        ),

        breaks=breaks,

        filtered=db.apply_filters(
            breaks,
            filters,
        ),

        kpis=kpis,

        version=(
            data["version"]
        ),

        now=now,
    )
)


# --------------------------------------------------
# Shared header
# --------------------------------------------------

render_header(
    kpis,
    db_status,
    monitoring["auto_refresh"],
    now,
)


# --------------------------------------------------
# Database stale warning
# --------------------------------------------------

if db_status == "STALE":

    st.warning(
        (
            "Database is busy "
            "(likely a pipeline run). "
            "Showing the last good snapshot."
        ),
        icon=":material/sync_problem:",
    )


# --------------------------------------------------
# Run selected page
# --------------------------------------------------

navigation.run()