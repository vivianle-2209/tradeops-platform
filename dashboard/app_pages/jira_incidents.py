from html import escape

import pandas as pd
import streamlit as st

from tradeops_ui import data as db


# ==================================================
# Helpers
# ==================================================

def safe_display(value) -> str:
    """
    Convert missing values into clean UI text.
    """

    if value is None:
        return "—"

    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass

    text = str(value).strip()

    if text.lower() in {
        "",
        "none",
        "nan",
        "<na>",
        "nat",
    }:
        return "—"

    return text


def safe_html(value) -> str:
    """
    HTML-safe display representation.
    """

    return escape(
        safe_display(value)
    )


def format_timestamp(value) -> str:
    """
    Format timestamps for dashboard display.

    Example:
    21/10/2026 15:46:43 UTC
    """

    if value is None:
        return "—"

    try:
        ts = pd.to_datetime(
            value,
            errors="coerce",
            utc=True,
        )

        if pd.isna(ts):
            return "—"

        return ts.strftime(
            "%d/%m/%Y %H:%M:%S UTC"
        )

    except Exception:
        return "—"


def clean_text_columns(
    frame: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """
    Replace textual versions of null values with pd.NA.
    """

    frame = frame.copy()

    for column in columns:

        if column not in frame.columns:
            continue

        frame[column] = (
            frame[column]
            .replace(
                {
                    "None": pd.NA,
                    "none": pd.NA,
                    "nan": pd.NA,
                    "NaN": pd.NA,
                    "<NA>": pd.NA,
                    "": pd.NA,
                }
            )
        )

    return frame


# ==================================================
# Context
# ==================================================

ctx = db.get_context()

selected_symbols = (
    st.session_state.get(
        "f_symbol",
        [],
    )
    or []
)


# ==================================================
# Header
# ==================================================

header_left, header_right = st.columns(
    [4, 1],
    vertical_alignment="center",
)


with header_left:

    st.markdown(
        "## Jira Incidents"
    )

    st.caption(
        (
            "Incidents created and synchronised "
            "between TradeOps, n8n and Jira."
        )
    )


with header_right:

    try:
        jira_board_url = st.secrets[
            "JIRA_BOARD_URL"
        ]

        if str(
            jira_board_url
        ).strip():

            st.link_button(
                "Open Jira Board ↗",
                jira_board_url,
                width="stretch",
            )

        else:

            raise ValueError(
                "Empty Jira board URL"
            )

    except Exception:

        st.button(
            "Jira Board URL unavailable",
            disabled=True,
            width="stretch",
        )


# ==================================================
# Load incident registry
# ==================================================

incidents = db.load_jira_incidents()


if incidents.empty:

    st.info(
        (
            "No Jira incidents are currently "
            "available."
        ),
        icon=":material/info:",
    )

    st.stop()


incidents = incidents.copy()


# ==================================================
# Guarantee schema
# ==================================================

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
    "jira_status",
    "jira_priority",
    "jira_assignee",
    "first_seen_at",
    "last_seen_at",
    "jira_first_seen_at",
    "jira_last_seen_at",
    "jira_created_at",
    "jira_updated_at",
    "last_workflow_run_id",
]


for column in expected_columns:

    if column not in incidents.columns:
        incidents[column] = pd.NA


# ==================================================
# Clean text nulls
# ==================================================

incidents = clean_text_columns(
    incidents,
    [
        "dedup_key",
        "break_id",
        "trade_id",
        "symbol",
        "break_type",
        "severity",
        "status",
        "jira_issue_key",
        "jira_issue_url",
        "jira_status",
        "jira_priority",
        "jira_assignee",
    ],
)


# ==================================================
# Parse timestamps
# ==================================================

timestamp_columns = [
    "first_seen_at",
    "last_seen_at",
    "jira_first_seen_at",
    "jira_last_seen_at",
    "jira_created_at",
    "jira_updated_at",
]


for column in timestamp_columns:

    incidents[column] = pd.to_datetime(
        incidents[column],
        errors="coerce",
        utc=True,
    )


# ==================================================
# Lifecycle compatibility
# ==================================================

incidents["jira_first_seen_at"] = (
    incidents["jira_first_seen_at"]
    .fillna(
        incidents["first_seen_at"]
    )
)


incidents["jira_last_seen_at"] = (
    incidents["jira_last_seen_at"]
    .fillna(
        incidents["last_seen_at"]
    )
)


# ==================================================
# Symbol enrichment
# ==================================================

if (
    not ctx.breaks.empty
    and "trade_id" in ctx.breaks.columns
    and "symbol_exec" in ctx.breaks.columns
):

    trade_symbol_map = (
        ctx.breaks[
            [
                "trade_id",
                "symbol_exec",
            ]
        ]
        .dropna(
            subset=[
                "trade_id"
            ]
        )
        .drop_duplicates(
            subset=[
                "trade_id"
            ]
        )
        .set_index(
            "trade_id"
        )[
            "symbol_exec"
        ]
    )


    incidents["symbol"] = (
        incidents["symbol"]
        .fillna(
            incidents["trade_id"]
            .map(
                trade_symbol_map
            )
        )
    )


# ==================================================
# Apply global Market Scope
# ==================================================

if selected_symbols:

    incidents = (
        incidents[
            incidents["symbol"]
            .astype(str)
            .isin(
                selected_symbols
            )
        ]
        .copy()
    )


if incidents.empty:

    scope_text = ", ".join(
        selected_symbols
    )

    st.info(
        (
            "No Jira incidents are currently "
            f"available for {scope_text}."
        ),
        icon=":material/info:",
    )

    st.stop()


# ==================================================
# KPI calculations
# ==================================================

total_incidents = len(
    incidents
)


tradeops_open = int(
    incidents["status"]
    .astype(str)
    .str.upper()
    .eq("OPEN")
    .sum()
)


critical_incidents = int(
    incidents["severity"]
    .astype(str)
    .str.upper()
    .eq("CRITICAL")
    .sum()
)


jira_status_upper = (
    incidents["jira_status"]
    .astype(str)
    .str.upper()
)


jira_active_mask = (
    ~jira_status_upper.isin(
        [
            "DONE",
            "CLOSED",
            "RESOLVED",
            "UNKNOWN",
            "<NA>",
            "NAN",
            "NONE",
            "",
        ]
    )
)


jira_active = int(
    jira_active_mask.sum()
)


# ==================================================
# KPI row
# ==================================================

k1, k2, k3, k4 = st.columns(
    4
)


with k1:

    st.metric(
        "Total incidents",
        f"{total_incidents:,}",
    )


with k2:

    st.metric(
        "TradeOps open",
        f"{tradeops_open:,}",
    )


with k3:

    st.metric(
        "Jira active",
        f"{jira_active:,}",
    )


with k4:

    st.metric(
        "Critical",
        f"{critical_incidents:,}",
    )


st.divider()


# ==================================================
# Filters
# ==================================================

f1, f2, f3, f4 = st.columns(
    [
        1,
        1,
        1,
        2,
    ]
)


# --------------------------------------------------
# Severity
# --------------------------------------------------

with f1:

    severity_values = sorted(
        incidents["severity"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_severity = st.multiselect(
        "Severity",
        severity_values,
        key="jira_filter_severity",
    )


# --------------------------------------------------
# TradeOps status
# --------------------------------------------------

with f2:

    tradeops_status_values = sorted(
        incidents["status"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_tradeops_status = st.multiselect(
        "TradeOps Status",
        tradeops_status_values,
        key="jira_filter_tradeops_status",
    )


# --------------------------------------------------
# Jira status
# --------------------------------------------------

with f3:

    jira_status_values = sorted(
        incidents["jira_status"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_jira_status = st.multiselect(
        "Jira Status",
        jira_status_values,
        key="jira_filter_status",
    )


# --------------------------------------------------
# Search
# --------------------------------------------------

with f4:

    search = st.text_input(
        "Search",
        placeholder=(
            "Trade, symbol, Jira ticket, assignee..."
        ),
        key="jira_search",
    )


# ==================================================
# Apply local filters
# ==================================================

filtered = incidents.copy()


if selected_severity:

    filtered = (
        filtered[
            filtered["severity"]
            .astype(str)
            .isin(
                selected_severity
            )
        ]
    )


if selected_tradeops_status:

    filtered = (
        filtered[
            filtered["status"]
            .astype(str)
            .isin(
                selected_tradeops_status
            )
        ]
    )


if selected_jira_status:

    filtered = (
        filtered[
            filtered["jira_status"]
            .astype(str)
            .isin(
                selected_jira_status
            )
        ]
    )


if search.strip():

    term = search.strip()

    searchable_columns = [
        column
        for column in [
            "trade_id",
            "symbol",
            "break_type",
            "jira_issue_key",
            "jira_assignee",
            "jira_priority",
            "dedup_key",
        ]
        if column in filtered.columns
    ]

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


# ==================================================
# Incident Registry
# ==================================================

st.markdown(
    "### Incident Registry"
)

st.caption(
    (
        f"Showing {len(filtered):,} "
        f"of {len(incidents):,} incidents"
    )
)


if filtered.empty:

    st.info(
        (
            "No incidents match the current "
            "Jira filters."
        ),
        icon=":material/search_off:",
    )

    st.stop()


# --------------------------------------------------
# Table dataframe
# --------------------------------------------------

registry = (
    filtered
    .reset_index(
        drop=True
    )
    .copy()
)


display_columns = [
    "jira_issue_key",
    "trade_id",
    "symbol",
    "break_type",
    "severity",
    "status",
    "jira_status",
    "jira_priority",
    "jira_assignee",
    "jira_first_seen_at",
    "jira_last_seen_at",
    "jira_updated_at",
    "jira_issue_url",
]


display_columns = [
    column
    for column in display_columns
    if column in registry.columns
]


# --------------------------------------------------
# Selectable table
# --------------------------------------------------

table_event = st.dataframe(
    registry[
        display_columns
    ],
    width="stretch",
    hide_index=True,

    on_select="rerun",

    selection_mode="single-row",

    key="jira_registry_table",

    column_config={

        "jira_issue_key":
            st.column_config.TextColumn(
                "Jira Ticket",
                width="small",
            ),

        "trade_id":
            st.column_config.TextColumn(
                "Trade ID",
                width="small",
            ),

        "symbol":
            st.column_config.TextColumn(
                "Symbol",
                width="small",
            ),

        "break_type":
            st.column_config.TextColumn(
                "Break Type",
                width="medium",
            ),

        "severity":
            st.column_config.TextColumn(
                "Severity",
                width="small",
            ),

        "status":
            st.column_config.TextColumn(
                "TradeOps Status",
                width="small",
            ),

        "jira_status":
            st.column_config.TextColumn(
                "Jira Status",
                width="small",
            ),

        "jira_priority":
            st.column_config.TextColumn(
                "Jira Priority",
                width="small",
            ),

        "jira_assignee":
            st.column_config.TextColumn(
                "Jira Assignee",
                width="medium",
            ),

        "jira_first_seen_at":
            st.column_config.DatetimeColumn(
                "First Seen",
                format="DD/MM/YYYY HH:mm:ss",
                width="medium",
            ),

        "jira_last_seen_at":
            st.column_config.DatetimeColumn(
                "Last Seen",
                format="DD/MM/YYYY HH:mm:ss",
                width="medium",
            ),

        "jira_updated_at":
            st.column_config.DatetimeColumn(
                "Jira Updated",
                format="DD/MM/YYYY HH:mm:ss",
                width="medium",
            ),

        "jira_issue_url":
            st.column_config.LinkColumn(
                "Ticket",
                display_text="Open ↗",
                width="small",
            ),
    },
)


# ==================================================
# Determine selected incident
# ==================================================

selected_rows = (
    table_event.selection.rows
    if table_event is not None
    else []
)


if selected_rows:

    selected_row_index = (
        selected_rows[0]
    )


    if (
        0
        <= selected_row_index
        < len(registry)
    ):

        selected_row = (
            registry.iloc[
                selected_row_index
            ]
        )


        selected_key = safe_display(
            selected_row.get(
                "jira_issue_key"
            )
        )


        st.session_state[
            "jira_selected_issue"
        ] = selected_key


# --------------------------------------------------
# Restore previous selected incident
# --------------------------------------------------

selected_issue = (
    st.session_state.get(
        "jira_selected_issue"
    )
)


valid_issue_keys = (
    registry[
        "jira_issue_key"
    ]
    .dropna()
    .astype(str)
    .tolist()
)


if (
    selected_issue
    not in valid_issue_keys
):

    selected_issue = None

    st.session_state.pop(
        "jira_selected_issue",
        None,
    )


# ==================================================
# Incident Detail anchor / section
# ==================================================

st.html(
    """
<div
    id="incident-detail-anchor"
    style="
        height: 1px;
        margin-top: 18px;
    "
></div>
"""
)


st.markdown(
    "### Incident Detail"
)


# --------------------------------------------------
# No row selected
# --------------------------------------------------

if selected_issue is None:

    st.info(
        (
            "Select an incident row above to "
            "open its TradeOps and Jira details."
        ),
        icon=":material/touch_app:",
    )

    st.stop()


# ==================================================
# Selected record
# ==================================================

selected_matches = (
    registry[
        registry[
            "jira_issue_key"
        ]
        .astype(str)
        .eq(
            selected_issue
        )
    ]
)


if selected_matches.empty:

    st.warning(
        (
            "The selected Jira incident is no "
            "longer available in the current scope."
        )
    )

    st.stop()


selected = (
    selected_matches.iloc[0]
)


# ==================================================
# Display values
# ==================================================

jira_ticket = safe_display(
    selected.get(
        "jira_issue_key"
    )
)


trade_id = safe_display(
    selected.get(
        "trade_id"
    )
)


symbol = safe_display(
    selected.get(
        "symbol"
    )
)


severity = safe_display(
    selected.get(
        "severity"
    )
)


tradeops_status = safe_display(
    selected.get(
        "status"
    )
)


jira_status = safe_display(
    selected.get(
        "jira_status"
    )
)


jira_priority = safe_display(
    selected.get(
        "jira_priority"
    )
)


jira_assignee = safe_display(
    selected.get(
        "jira_assignee"
    )
)


break_type = (
    safe_display(
        selected.get(
            "break_type"
        )
    )
    .replace(
        "_",
        " ",
    )
)


first_seen = format_timestamp(
    selected.get(
        "jira_first_seen_at"
    )
)


last_seen = format_timestamp(
    selected.get(
        "jira_last_seen_at"
    )
)


jira_updated = format_timestamp(
    selected.get(
        "jira_updated_at"
    )
)


# ==================================================
# HTML-safe values
# ==================================================

jira_ticket_html = safe_html(
    jira_ticket
)

trade_id_html = safe_html(
    trade_id
)

symbol_html = safe_html(
    symbol
)

severity_html = safe_html(
    severity
)

tradeops_status_html = safe_html(
    tradeops_status
)

jira_status_html = safe_html(
    jira_status
)

jira_priority_html = safe_html(
    jira_priority
)

jira_assignee_html = safe_html(
    jira_assignee
)

break_type_html = safe_html(
    break_type
)

first_seen_html = safe_html(
    first_seen
)

last_seen_html = safe_html(
    last_seen
)

jira_updated_html = safe_html(
    jira_updated
)


# ==================================================
# Incident card styles
# ==================================================

st.html(
    """
<style>

.incident-shell {
    border: 1px solid #e7e7e7;
    border-radius: 16px;
    overflow: hidden;
    background: #ffffff;
    margin-top: 0.65rem;
    margin-bottom: 1rem;
}

.incident-top {
    background: #171717;
    color: #ffffff;

    padding:
        20px
        24px;

    display: flex;

    align-items:
        center;

    justify-content:
        space-between;

    gap: 20px;
}

.incident-ticket-wrap {
    display: flex;

    flex-direction:
        column;

    gap: 4px;
}

.incident-eyebrow {
    font-size: 0.68rem;

    letter-spacing:
        0.12em;

    text-transform:
        uppercase;

    font-weight: 700;

    color:
        #9c9c9c;
}

.incident-ticket {
    font-size: 1.5rem;

    font-weight:
        750;

    line-height:
        1.1;
}

.incident-badges {
    display: flex;

    flex-wrap:
        wrap;

    justify-content:
        flex-end;

    gap: 8px;
}

.incident-pill {
    display:
        inline-flex;

    align-items:
        center;

    border-radius:
        999px;

    padding:
        6px 11px;

    font-size:
        0.72rem;

    font-weight:
        700;

    white-space:
        nowrap;
}

.incident-pill-pink {
    background:
        #ff4da6;

    color:
        #ffffff;
}

.incident-pill-light {
    background:
        #ffffff;

    color:
        #171717;
}

.incident-pill-muted {
    background:
        #303030;

    color:
        #d0d0d0;

    border:
        1px solid #474747;
}

.incident-body {
    padding:
        22px 24px 24px 24px;
}

.incident-section-label {
    font-size:
        0.68rem;

    font-weight:
        700;

    letter-spacing:
        0.10em;

    color:
        #8a8a8a;

    text-transform:
        uppercase;

    margin-bottom:
        13px;
}

.incident-grid {
    display:
        grid;

    grid-template-columns:
        repeat(
            4,
            minmax(0, 1fr)
        );

    gap:
        20px 30px;
}

.incident-field {
    min-width:
        0;
}

.incident-field-label {
    color:
        #929292;

    font-size:
        0.74rem;

    margin-bottom:
        5px;
}

.incident-field-value {
    color:
        #171717;

    font-size:
        0.95rem;

    font-weight:
        650;

    line-height:
        1.4;

    overflow-wrap:
        anywhere;
}

.incident-field-value.mono {
    font-family:
        ui-monospace,
        SFMono-Regular,
        Menlo,
        Monaco,
        Consolas,
        monospace;

    font-size:
        0.88rem;
}

.incident-divider {
    height:
        1px;

    background:
        #eeeeee;

    margin:
        22px 0;
}

.incident-lifecycle {
    display:
        grid;

    grid-template-columns:
        repeat(3, 1fr);

    border:
        1px solid #eeeeee;

    border-radius:
        12px;

    overflow:
        hidden;
}

.incident-time {
    padding:
        15px 18px;

    background:
        #fafafa;

    border-right:
        1px solid #eeeeee;
}

.incident-time:last-child {
    border-right:
        none;
}

.incident-time-label {
    color:
        #929292;

    font-size:
        0.72rem;

    margin-bottom:
        6px;
}

.incident-time-value {
    color:
        #222222;

    font-size:
        0.86rem;

    font-weight:
        600;

    overflow-wrap:
        anywhere;
}

@media (
    max-width:
        1000px
) {

    .incident-grid {
        grid-template-columns:
            repeat(
                2,
                minmax(0, 1fr)
            );
    }

    .incident-top {
        align-items:
            flex-start;

        flex-direction:
            column;
    }

    .incident-badges {
        justify-content:
            flex-start;
    }
}

</style>
"""
)


# ==================================================
# Badge styles
# ==================================================

severity_class = (
    "incident-pill-pink"
    if severity.upper()
    in [
        "CRITICAL",
        "HIGH",
    ]
    else "incident-pill-light"
)


jira_status_class = (
    "incident-pill-light"
    if jira_status.upper()
    not in [
        "—",
        "UNKNOWN",
    ]
    else "incident-pill-muted"
)


# ==================================================
# Incident detail card
# ==================================================

st.html(
    f"""
<div class="incident-shell">

    <div class="incident-top">

        <div class="incident-ticket-wrap">

            <div class="incident-eyebrow">
                Jira Incident
            </div>

            <div class="incident-ticket">
                {jira_ticket_html}
            </div>

        </div>


        <div class="incident-badges">

            <span
                class="
                    incident-pill
                    {severity_class}
                "
            >
                {severity_html}
            </span>

            <span
                class="
                    incident-pill
                    incident-pill-muted
                "
            >
                TradeOps ·
                {tradeops_status_html}
            </span>

            <span
                class="
                    incident-pill
                    {jira_status_class}
                "
            >
                Jira ·
                {jira_status_html}
            </span>

        </div>

    </div>


    <div class="incident-body">

        <div class="incident-section-label">
            Trade Context
        </div>


        <div class="incident-grid">

            <div class="incident-field">

                <div class="incident-field-label">
                    Trade ID
                </div>

                <div
                    class="
                        incident-field-value
                        mono
                    "
                >
                    {trade_id_html}
                </div>

            </div>


            <div class="incident-field">

                <div class="incident-field-label">
                    Symbol
                </div>

                <div class="incident-field-value">
                    {symbol_html}
                </div>

            </div>


            <div class="incident-field">

                <div class="incident-field-label">
                    Break Type
                </div>

                <div class="incident-field-value">
                    {break_type_html}
                </div>

            </div>


            <div class="incident-field">

                <div class="incident-field-label">
                    Severity
                </div>

                <div class="incident-field-value">
                    {severity_html}
                </div>

            </div>

        </div>


        <div class="incident-divider"></div>


        <div class="incident-section-label">
            Jira Workflow
        </div>


        <div class="incident-grid">

            <div class="incident-field">

                <div class="incident-field-label">
                    Jira Status
                </div>

                <div class="incident-field-value">
                    {jira_status_html}
                </div>

            </div>


            <div class="incident-field">

                <div class="incident-field-label">
                    Jira Priority
                </div>

                <div class="incident-field-value">
                    {jira_priority_html}
                </div>

            </div>


            <div class="incident-field">

                <div class="incident-field-label">
                    Assignee
                </div>

                <div class="incident-field-value">
                    {jira_assignee_html}
                </div>

            </div>


            <div class="incident-field">

                <div class="incident-field-label">
                    TradeOps Status
                </div>

                <div class="incident-field-value">
                    {tradeops_status_html}
                </div>

            </div>

        </div>


        <div class="incident-divider"></div>


        <div class="incident-section-label">
            Incident Lifecycle
        </div>


        <div class="incident-lifecycle">

            <div class="incident-time">

                <div class="incident-time-label">
                    First Seen
                </div>

                <div class="incident-time-value">
                    {first_seen_html}
                </div>

            </div>


            <div class="incident-time">

                <div class="incident-time-label">
                    Last Seen
                </div>

                <div class="incident-time-value">
                    {last_seen_html}
                </div>

            </div>


            <div class="incident-time">

                <div class="incident-time-label">
                    Jira Updated
                </div>

                <div class="incident-time-value">
                    {jira_updated_html}
                </div>

            </div>

        </div>

    </div>

</div>
"""
)


# ==================================================
# Jira action
# ==================================================

jira_url = selected.get(
    "jira_issue_url"
)


if (
    pd.notna(
        jira_url
    )
    and str(
        jira_url
    ).strip()
):

    action_left, _ = st.columns(
        [
            1,
            4,
        ]
    )

    with action_left:

        st.link_button(
            (
                f"Open "
                f"{jira_ticket} "
                "in Jira ↗"
            ),
            str(
                jira_url
            ),
            width="stretch",
        )