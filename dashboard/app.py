"""
TradeOps — Trading Operations Analytics &
Exception Management Platform.

Main Streamlit entrypoint.

Run from project root:

    python -m streamlit run dashboard/app.py
"""

import pandas as pd
import streamlit as st

from streamlit_autorefresh import (
    st_autorefresh,
)

from tradeops_ui import (
    data as db,
)

from tradeops_ui.components import (
    render_header,
    render_sidebar_status,
)

from tradeops_ui.sidebar import (
    render_filters,
    render_monitoring_controls,
)

from tradeops_ui.theme import (
    APP_CSS,
)


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title=(
        "TradeOps"
    ),
    page_icon=(
        ":material/monitoring:"
    ),
    layout="wide",
    initial_sidebar_state=(
        "expanded"
    ),
)


st.html(
    APP_CSS
)


# --------------------------------------------------
# Navigation
# --------------------------------------------------

navigation = st.navigation(
    [
        st.Page(
            "app_pages/overview.py",
            title="Overview",
            icon=(
                ":material/space_dashboard:"
            ),
            default=True,
        ),

        st.Page(
            "app_pages/exception_queue.py",
            title=(
                "Exception Queue"
            ),
            icon=(
                ":material/format_list_numbered:"
            ),
        ),

        st.Page(
            "app_pages/sla_risk.py",
            title=(
                "SLA & Risk"
            ),
            icon=(
                ":material/timer:"
            ),
        ),

        st.Page(
            "app_pages/trade_investigation.py",
            title=(
                "Trade Investigation"
            ),
            icon=(
                ":material/manage_search:"
            ),
        ),

        st.Page(
            "app_pages/jira_incidents.py",
            title=(
                "Jira Incidents"
            ),
            icon=(
                ":material/confirmation_number:"
            ),
        ),
    ],

    position="top",
)


# --------------------------------------------------
# Sidebar monitoring controls
# --------------------------------------------------

with st.sidebar:

    status_slot = (
        st.container()
    )


    monitoring = (
        render_monitoring_controls()
    )


    if monitoring[
        "auto_refresh"
    ]:

        st_autorefresh(
            interval=(
                monitoring[
                    "refresh_seconds"
                ]
                * 1000
            ),
            key=(
                "tradeops_autorefresh"
            ),
        )


# --------------------------------------------------
# Load TradeOps data
# --------------------------------------------------

data, db_status, db_error = (
    db.load_data()
)


now = pd.Timestamp.now(
    tz="UTC"
)


# --------------------------------------------------
# Sidebar system status
# --------------------------------------------------

with status_slot:

    render_sidebar_status(
        db_status,
        monitoring[
            "auto_refresh"
        ],
        monitoring[
            "refresh_seconds"
        ],
        data,
        monitoring[
            "live_sla"
        ],
    )


# --------------------------------------------------
# Database unavailable
# --------------------------------------------------

if data is None:

    render_header(
        {},
        db_status,
        monitoring[
            "auto_refresh"
        ],
        now,
    )


    st.error(
        (
            f"Could not read `{db.DB_PATH}`. "
            "Run the TradeOps pipeline and "
            "refresh the dashboard.\n\n"
            f"{db_error}"
        ),
        icon=(
            ":material/database_off:"
        ),
    )


    st.stop()


# --------------------------------------------------
# Break snapshot / live SLA
# --------------------------------------------------

if monitoring[
    "live_sla"
]:

    breaks = (
        db.apply_live_sla(
            data[
                "breaks"
            ],
            now,
        )
    )

else:

    breaks = (
        data[
            "breaks"
        ]
        .copy()
    )


# --------------------------------------------------
# Determine available market symbols
# --------------------------------------------------

symbol_sources = []


if (
    "symbol_exec"
    in data[
        "reconciliation"
    ].columns
):

    symbol_sources.extend(
        data[
            "reconciliation"
        ][
            "symbol_exec"
        ]
        .dropna()
        .astype(str)
        .tolist()
    )


if (
    "symbol_exec"
    in breaks.columns
):

    symbol_sources.extend(
        breaks[
            "symbol_exec"
        ]
        .dropna()
        .astype(str)
        .tolist()
    )


available_symbols = sorted(
    set(
        symbol_sources
    )
)


# --------------------------------------------------
# Shared header
#
# Header initially uses unscoped basic KPIs.
# Current-scope KPIs are calculated below.
# --------------------------------------------------

initial_kpis = (
    db.compute_kpis(
        data[
            "reconciliation"
        ],
        breaks,
    )
)


render_header(
    initial_kpis,
    db_status,
    monitoring[
        "auto_refresh"
    ],
    now,
)


# --------------------------------------------------
# Market Scope
# --------------------------------------------------

st.markdown(
    """
    <div style="
        margin-top: 0.25rem;
        margin-bottom: 0.65rem;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        opacity: 0.62;
    ">
        Market Scope
    </div>
    """,
    unsafe_allow_html=True,
)


selected_symbols = st.pills(
    "Market Scope",
    available_symbols,
    selection_mode="multi",
    key="f_symbol",
    label_visibility="collapsed",
)


selected_symbols = (
    selected_symbols
    or []
)


# --------------------------------------------------
# Apply global symbol scope
# --------------------------------------------------

scoped_reconciliation = (
    db.apply_reconciliation_scope(
        data[
            "reconciliation"
        ],
        selected_symbols,
    )
)


scoped_breaks = (
    db.apply_break_scope(
        breaks,
        selected_symbols,
    )
)


# --------------------------------------------------
# Sidebar operational filters
# --------------------------------------------------

with st.sidebar:

    st.divider()


    filters = (
        render_filters(
            scoped_breaks
        )
    )


# Store symbol scope alongside filter dictionary.
# Some page-level logic uses this explicitly.
filters[
    "symbol_exec"
] = selected_symbols


# --------------------------------------------------
# Apply operational filters
# --------------------------------------------------

filtered_breaks = (
    db.apply_filters(
        scoped_breaks,
        filters,
    )
)


# --------------------------------------------------
# Current-scope KPIs
# --------------------------------------------------

kpis = (
    db.compute_kpis(
        scoped_reconciliation,
        filtered_breaks,
    )
)


# --------------------------------------------------
# Shared dashboard context
# --------------------------------------------------

db.set_context(
    db.DashboardContext(

        reconciliation=(
            scoped_reconciliation
        ),

        breaks=(
            scoped_breaks
        ),

        filtered=(
            filtered_breaks
        ),

        kpis=kpis,

        version=(
            data[
                "version"
            ]
        ),

        now=now,
    )
)


# --------------------------------------------------
# Database stale warning
# --------------------------------------------------

if (
    db_status
    == "STALE"
):

    st.warning(
        (
            "Database is currently busy, "
            "most likely because a pipeline run "
            "is updating it. Showing the last "
            "successfully loaded snapshot."
        ),
        icon=(
            ":material/sync_problem:"
        ),
    )


# --------------------------------------------------
# Run selected dashboard page
# --------------------------------------------------

navigation.run()