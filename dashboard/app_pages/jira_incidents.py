"""
Jira Incidents

Dedicated operational view of Jira incidents created by the
TradeOps n8n triage workflow.
"""

import pandas as pd
import streamlit as st

from tradeops_ui import data as db


# --------------------------------------------------
# Header
# --------------------------------------------------

header_left, header_right = st.columns(
    [4, 1]
)

with header_left:
    st.markdown(
        "## Jira Incidents"
    )

    st.caption(
        "Incidents created and updated by the "
        "TradeOps automated triage workflow."
    )


with header_right:

    try:
        jira_board_url = st.secrets[
            "JIRA_BOARD_URL"
        ]

        st.link_button(
            "Open Jira Board ↗",
            jira_board_url,
            width="stretch",
        )

    except Exception:
        st.button(
            "Jira Board URL unavailable",
            disabled=True,
            width="stretch",
        )


# --------------------------------------------------
# Load incidents
# --------------------------------------------------

incidents = db.load_jira_incidents()


if incidents.empty:

    st.info(
        "No Jira incidents are currently available.",
        icon=":material/info:",
    )

    st.stop()


# --------------------------------------------------
# Clean data
# --------------------------------------------------

incidents = incidents.copy()


for column in [
    "first_seen_at",
    "last_seen_at",
]:
    if column in incidents.columns:

        incidents[column] = pd.to_datetime(
            incidents[column],
            errors="coerce",
            utc=True,
        )


# --------------------------------------------------
# KPI calculations
# --------------------------------------------------

total_incidents = len(
    incidents
)

open_incidents = (
    incidents["status"]
    .astype(str)
    .str.upper()
    .eq("OPEN")
    .sum()
    if "status" in incidents.columns
    else 0
)

critical_incidents = (
    incidents["severity"]
    .astype(str)
    .str.upper()
    .eq("CRITICAL")
    .sum()
    if "severity" in incidents.columns
    else 0
)

high_incidents = (
    incidents["severity"]
    .astype(str)
    .str.upper()
    .eq("HIGH")
    .sum()
    if "severity" in incidents.columns
    else 0
)


# --------------------------------------------------
# KPI row
# --------------------------------------------------

k1, k2, k3, k4 = st.columns(4)


with k1:
    st.metric(
        "Total incidents",
        f"{total_incidents:,}",
    )


with k2:
    st.metric(
        "Open",
        f"{open_incidents:,}",
    )


with k3:
    st.metric(
        "Critical",
        f"{critical_incidents:,}",
    )


with k4:
    st.metric(
        "High",
        f"{high_incidents:,}",
    )


st.divider()


# --------------------------------------------------
# Filters
# --------------------------------------------------

filter_col1, filter_col2, filter_col3 = st.columns(
    [1, 1, 2]
)


with filter_col1:

    severity_values = (
        sorted(
            incidents["severity"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if "severity" in incidents.columns
        else []
    )

    selected_severity = st.multiselect(
        "Severity",
        severity_values,
    )


with filter_col2:

    status_values = (
        sorted(
            incidents["status"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if "status" in incidents.columns
        else []
    )

    selected_status = st.multiselect(
        "Status",
        status_values,
    )


with filter_col3:

    search = st.text_input(
        "Search",
        placeholder=(
            "Trade ID, break type, Jira ticket..."
        ),
    )


# --------------------------------------------------
# Apply filters
# --------------------------------------------------

filtered = incidents.copy()


if selected_severity:

    filtered = filtered[
        filtered["severity"]
        .astype(str)
        .isin(selected_severity)
    ]


if selected_status:

    filtered = filtered[
        filtered["status"]
        .astype(str)
        .isin(selected_status)
    ]


if search.strip():

    term = search.strip()

    searchable_columns = [
        column
        for column in [
            "trade_id",
            "break_type",
            "jira_issue_key",
            "dedup_key",
        ]
        if column in filtered.columns
    ]

    if searchable_columns:

        search_mask = pd.Series(
            False,
            index=filtered.index,
        )

        for column in searchable_columns:

            search_mask |= (
                filtered[column]
                .astype(str)
                .str.contains(
                    term,
                    case=False,
                    na=False,
                    regex=False,
                )
            )

        filtered = filtered[
            search_mask
        ]


# --------------------------------------------------
# Incident queue
# --------------------------------------------------

st.markdown(
    "### Incident Registry"
)

st.caption(
    f"Showing {len(filtered)} of "
    f"{len(incidents)} incidents"
)


display_columns = [
    "jira_issue_key",
    "trade_id",
    "break_type",
    "severity",
    "status",
    "jira_issue_url",
    "first_seen_at",
    "last_seen_at",
]


display_columns = [
    column
    for column in display_columns
    if column in filtered.columns
]


st.dataframe(
    filtered[
        display_columns
    ],
    width="stretch",
    hide_index=True,
    column_config={

        "jira_issue_key":
            st.column_config.TextColumn(
                "Jira Ticket",
            ),

        "trade_id":
            st.column_config.TextColumn(
                "Trade ID",
            ),

        "break_type":
            st.column_config.TextColumn(
                "Break Type",
            ),

        "severity":
            st.column_config.TextColumn(
                "Severity",
            ),

        "status":
            st.column_config.TextColumn(
                "Status",
            ),

        "jira_issue_url":
            st.column_config.LinkColumn(
                "Open Ticket",
                display_text="Open ↗",
            ),

        "first_seen_at":
            st.column_config.DatetimeColumn(
                "First Seen",
                format="DD/MM/YYYY HH:mm:ss",
            ),

        "last_seen_at":
            st.column_config.DatetimeColumn(
                "Last Seen",
                format="DD/MM/YYYY HH:mm:ss",
            ),

    },
)


# --------------------------------------------------
# Selected incident
# --------------------------------------------------

valid_issue_keys = (
    filtered[
        "jira_issue_key"
    ]
    .dropna()
    .astype(str)
    .tolist()
    if "jira_issue_key"
    in filtered.columns
    else []
)


if valid_issue_keys:

    st.divider()

    st.markdown(
        "### Incident Detail"
    )

    selected_issue = st.selectbox(
        "Select Jira incident",
        valid_issue_keys,
    )


    selected = filtered[
        filtered[
            "jira_issue_key"
        ].astype(str)
        == selected_issue
    ].iloc[0]


    d1, d2, d3, d4 = st.columns(4)


    with d1:
        st.metric(
            "Jira Ticket",
            selected_issue,
        )


    with d2:
        st.metric(
            "Trade",
            selected.get(
                "trade_id",
                "—",
            ),
        )


    with d3:
        st.metric(
            "Severity",
            selected.get(
                "severity",
                "—",
            ),
        )


    with d4:
        st.metric(
            "Status",
            selected.get(
                "status",
                "—",
            ),
        )


    jira_url = selected.get(
        "jira_issue_url"
    )


    if (
        pd.notna(jira_url)
        and str(jira_url).strip()
    ):

        st.link_button(
            f"Open {selected_issue} in Jira ↗",
            str(jira_url),
        )