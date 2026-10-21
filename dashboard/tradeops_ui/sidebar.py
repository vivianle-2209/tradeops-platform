"""
TradeOps sidebar controls.

Market Scope is rendered in dashboard/app.py.

This module handles:
- monitoring
- refresh
- SLA clock
- operational exception filters
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tradeops_ui.data import (
    clear_caches,
)

from tradeops_ui.formatting import (
    ordered,
)

from tradeops_ui.theme import (
    SEVERITY_ORDER,
    SLA_ORDER,
)


# --------------------------------------------------
# Monitoring
# --------------------------------------------------

REFRESH_INTERVALS = [
    5,
    10,
    15,
    30,
    60,
]


# --------------------------------------------------
# Session-state filter keys
# --------------------------------------------------

FILTER_KEYS = [
    "f_symbol",
    "f_severity",
    "f_exception",
    "f_sla",
    "f_status",
    "f_venue",
    "f_trade",
]


# --------------------------------------------------
# Monitoring controls
# --------------------------------------------------

def render_monitoring_controls() -> dict:

    st.markdown(
        "**Monitoring**"
    )


    auto_refresh = st.toggle(
        "Auto refresh",
        value=True,
        key="auto_refresh",
    )


    refresh_seconds = (
        st.select_slider(
            "Refresh interval",
            options=(
                REFRESH_INTERVALS
            ),
            value=15,
            format_func=lambda seconds: (
                f"{seconds}s"
            ),
            key="refresh_seconds",
            disabled=(
                not auto_refresh
            ),
        )
    )


    live_sla = st.toggle(
        "Live SLA clock",
        value=False,
        key="live_sla",
        help=(
            "Re-age open breaks against the "
            "current time using TradeOps SLA "
            "rules. Off displays the snapshot "
            "stored by the most recent pipeline "
            "run."
        ),
    )


    if st.button(
        "Refresh now",
        icon=(
            ":material/refresh:"
        ),
        width="stretch",
        key="refresh_now",
    ):

        clear_caches()


    return {
        "auto_refresh": (
            auto_refresh
        ),
        "refresh_seconds": (
            refresh_seconds
        ),
        "live_sla": (
            live_sla
        ),
    }


# --------------------------------------------------
# Reset
# --------------------------------------------------

def _reset_filters() -> None:

    for key in FILTER_KEYS:

        st.session_state.pop(
            key,
            None,
        )


# --------------------------------------------------
# Operational filters
# --------------------------------------------------

def render_filters(
    breaks: pd.DataFrame,
) -> dict:
    """
    Render exception filters.

    The dataframe supplied here has already been
    globally scoped by symbol.
    """

    with st.container(
        horizontal=True,
        vertical_alignment="center",
    ):

        st.markdown(
            "**Operational filters**"
        )

        st.space(
            "stretch"
        )

        st.button(
            "Reset",
            icon=(
                ":material/restart_alt:"
            ),
            type="tertiary",
            on_click=(
                _reset_filters
            ),
            key="reset_filters",
        )


    # --------------------------------------------------
    # Severity
    # --------------------------------------------------

    severity = st.pills(
        "Severity",
        ordered(
            breaks[
                "severity"
            ],
            SEVERITY_ORDER,
        ),
        selection_mode="multi",
        key="f_severity",
    )


    # --------------------------------------------------
    # SLA
    # --------------------------------------------------

    sla = st.pills(
        "SLA status",
        ordered(
            breaks[
                "sla_status"
            ],
            SLA_ORDER,
        ),
        selection_mode="multi",
        key="f_sla",
        format_func=lambda value: (
            str(value)
            .replace(
                "_",
                " ",
            )
        ),
    )


    # --------------------------------------------------
    # Lifecycle
    # --------------------------------------------------

    status = st.pills(
        "Break status",
        ordered(
            breaks[
                "break_status"
            ],
            [
                "OPEN",
                "RESOLVED",
                "CLOSED",
            ],
        ),
        selection_mode="multi",
        key="f_status",
    )


    # --------------------------------------------------
    # Exception type
    # --------------------------------------------------

    exception = (
        st.multiselect(
            "Exception type",
            ordered(
                breaks[
                    "exception_type"
                ],
                [],
            ),
            key="f_exception",
            placeholder=(
                "All exception types"
            ),
            format_func=lambda value: (
                str(value)
                .replace(
                    "_",
                    " ",
                )
            ),
        )
    )


    # --------------------------------------------------
    # Venue
    # --------------------------------------------------

    venue = (
        st.multiselect(
            "Venue",
            ordered(
                breaks[
                    "venue"
                ],
                [],
            ),
            key="f_venue",
            placeholder=(
                "All venues"
            ),
        )
    )


    # --------------------------------------------------
    # Trade ID
    # --------------------------------------------------

    trade_ids = (
        breaks[
            "trade_id"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )


    trade_ids = sorted(
        trade_ids
    )


    trade = st.selectbox(
        "Trade ID",
        trade_ids,
        index=None,
        key="f_trade",
        placeholder=(
            "Type to search"
        ),
        accept_new_options=True,
        filter_mode="contains",
    )


    return {
        "severity": severity,
        "sla_status": sla,
        "break_status": status,
        "exception_type": (
            exception
        ),
        "venue": venue,
        "trade": (
            trade or ""
        ).strip(),
    }