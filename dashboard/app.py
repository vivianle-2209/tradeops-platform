"""
TradeOps — Trading Operations Analytics & Exception Management Platform.

Entrypoint. Builds the shared shell (sidebar, data load, header) on every
run, then hands off to the selected page via top navigation:

    app_pages/overview.py             firm-wide KPIs, break mix, exposure
    app_pages/exception_queue.py      prioritised incident queue
    app_pages/sla_risk.py             SLA ageing, matrix, concentration
    app_pages/trade_investigation.py  execution vs clearing for one trade

Shared logic lives in tradeops_ui/. Run from the project root:

    streamlit run dashboard/app.py
"""

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from tradeops_ui import data as db
from tradeops_ui.components import render_header, render_sidebar_status
from tradeops_ui.sidebar import render_filters, render_monitoring_controls
from tradeops_ui.theme import APP_CSS

st.set_page_config(
    page_title="TradeOps",
    page_icon=":material/monitoring:",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.html(APP_CSS)

navigation = st.navigation(
    [
        st.Page("app_pages/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
        st.Page("app_pages/exception_queue.py", title="Exception Queue", icon=":material/format_list_numbered:"),
        st.Page("app_pages/sla_risk.py", title="SLA & Risk", icon=":material/timer:"),
        st.Page("app_pages/trade_investigation.py", title="Trade Investigation", icon=":material/manage_search:"),
    ],
    position="top",
)

# ---- Sidebar: status slot first, then monitoring controls ------------------

with st.sidebar:
    status_slot = st.container()
    monitoring = render_monitoring_controls()
    if monitoring["auto_refresh"]:
        st_autorefresh(interval=monitoring["refresh_seconds"] * 1000, key="tradeops_autorefresh")

# ---- Data ----------------------------------------------------------------------

data, db_status, db_error = db.load_data()
now = pd.Timestamp.now(tz="UTC")

with status_slot:
    render_sidebar_status(db_status, monitoring["auto_refresh"], monitoring["refresh_seconds"],
                          data, monitoring["live_sla"])

if data is None:
    render_header({}, db_status, monitoring["auto_refresh"], now)
    st.error(f"Could not read `{db.DB_PATH}`. Run the pipeline to build the database, then refresh.\n\n{db_error}",
             icon=":material/database_off:")
    st.stop()

breaks = db.apply_live_sla(data["breaks"], now) if monitoring["live_sla"] else data["breaks"]

with st.sidebar:
    st.divider()
    filters = render_filters(breaks)

kpis = db.compute_kpis(data["reconciliation"], breaks)
db.set_context(db.DashboardContext(
    reconciliation=data["reconciliation"],
    breaks=breaks,
    filtered=db.apply_filters(breaks, filters),
    kpis=kpis,
    version=data["version"],
    now=now,
))

# ---- Shell header, then the selected page --------------------------------------

render_header(kpis, db_status, monitoring["auto_refresh"], now)
if db_status == "STALE":
    st.warning("Database is busy (likely a pipeline run). Showing the last good snapshot.",
               icon=":material/sync_problem:")

navigation.run()
