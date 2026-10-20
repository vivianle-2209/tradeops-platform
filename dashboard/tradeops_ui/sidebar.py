"""Sidebar widgets: monitoring controls and break filters."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tradeops_ui.data import clear_caches
from tradeops_ui.formatting import ordered
from tradeops_ui.theme import SEVERITY_ORDER, SLA_ORDER

REFRESH_INTERVALS = [5, 10, 15, 30, 60]
FILTER_KEYS = ["f_severity", "f_exception", "f_sla", "f_status", "f_venue", "f_trade"]


def render_monitoring_controls() -> dict:
    """Auto refresh, interval, live SLA clock and manual refresh."""
    st.markdown("**Monitoring**")
    auto_refresh = st.toggle("Auto refresh", value=True, key="auto_refresh")
    refresh_seconds = st.select_slider(
        "Refresh interval", REFRESH_INTERVALS, value=15, format_func=lambda s: f"{s}s",
        key="refresh_seconds", disabled=not auto_refresh,
    )
    live_sla = st.toggle(
        "Live SLA clock", value=False, key="live_sla",
        help="Re-age open breaks against the current time using the pipeline's SLA rules. "
             "Off shows the SLA snapshot stored by the last pipeline run.",
    )
    if st.button("Refresh now", icon=":material/refresh:", width="stretch", key="refresh_now"):
        clear_caches()
    return {"auto_refresh": auto_refresh, "refresh_seconds": refresh_seconds, "live_sla": live_sla}


def _reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def render_filters(breaks: pd.DataFrame) -> dict:
    """Break filters. Empty selections mean 'all'."""
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown("**Filters**")
        st.space("stretch")
        st.button("Reset", icon=":material/restart_alt:", type="tertiary",
                  on_click=_reset_filters, key="reset_filters")

    severity = st.pills("Severity", ordered(breaks["severity"], SEVERITY_ORDER),
                        selection_mode="multi", key="f_severity")
    sla = st.pills("SLA status", ordered(breaks["sla_status"], SLA_ORDER), selection_mode="multi",
                   key="f_sla", format_func=lambda v: v.replace("_", " "))
    status = st.pills("Break status", ordered(breaks["break_status"], ["OPEN", "RESOLVED", "CLOSED"]),
                      selection_mode="multi", key="f_status")
    exception = st.multiselect("Exception type", ordered(breaks["exception_type"], []),
                               key="f_exception", placeholder="All exception types",
                               format_func=lambda v: v.replace("_", " "))
    venue = st.multiselect("Venue", ordered(breaks["venue"], []), key="f_venue", placeholder="All venues")
    # Type-ahead: matching trade IDs are suggested as you type. Free text that
    # isn't an exact ID is still accepted and applied as a substring search.
    trade = st.selectbox(
        "Trade ID", sorted(breaks["trade_id"].dropna().astype(str).unique()), index=None,
        key="f_trade", placeholder="Type to search, e.g. 000026",
        accept_new_options=True, filter_mode="contains",
    )
    return {
        "severity": severity,
        "sla_status": sla,
        "break_status": status,
        "exception_type": exception,
        "venue": venue,
        "trade": (trade or "").strip(),
    }
