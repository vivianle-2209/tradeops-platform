import streamlit as st

from tradeops_ui.components import (
    empty_state,
    page_title,
)

from tradeops_ui.data import (
    get_context,
)

from tradeops_ui.tables import (
    breaks_table,
)


# --------------------------------------------------
# Queue schema
# --------------------------------------------------

QUEUE_COLUMNS = [
    "priority_rank",
    "break_id",
    "trade_id",
    "symbol_exec",
    "exception_type",
    "severity",
    "severity_score",
    "sla_status",
    "age_minutes",
    "sla_remaining_minutes",
    "affected_notional",
    "break_status",
    "detected_at",
]


QUEUE_SORTS = {

    "Priority": (
        [
            "priority_rank"
        ],
        [
            True
        ],
    ),

    "SLA remaining": (
        [
            "sla_remaining_minutes",
            "priority_rank",
        ],
        [
            True,
            True,
        ],
    ),

    "Notional": (
        [
            "affected_notional",
            "priority_rank",
        ],
        [
            False,
            True,
        ],
    ),

    "Age": (
        [
            "age_minutes",
            "priority_rank",
        ],
        [
            False,
            True,
        ],
    ),
}


# --------------------------------------------------
# Context
# --------------------------------------------------

ctx = get_context()

filtered = (
    ctx.filtered.copy()
)


# --------------------------------------------------
# Page heading
# --------------------------------------------------

page_title(
    "Exception Queue",
    (
        "Prioritised reconciliation exceptions. "
        "Use Market Scope and the operational "
        "filters to narrow the queue."
    ),
)


# --------------------------------------------------
# Summary
# --------------------------------------------------

critical = int(
    filtered[
        "severity"
    ]
    .eq(
        "CRITICAL"
    )
    .sum()
)


breached = int(
    filtered[
        "sla_status"
    ]
    .eq(
        "BREACHED"
    )
    .sum()
)


at_risk = int(
    filtered[
        "sla_status"
    ]
    .eq(
        "AT_RISK"
    )
    .sum()
)


with st.container(
    horizontal=True,
    vertical_alignment="center",
):

    st.markdown(
        (
            f"Showing **{len(filtered):,}** "
            f"of **{len(ctx.breaks):,}** "
            "breaks"
        )
    )


    st.badge(
        f"{critical} critical",
        color=(
            "primary"
            if critical
            else "gray"
        ),
    )


    st.badge(
        f"{breached} breached",
        color=(
            "primary"
            if breached
            else "gray"
        ),
    )


    st.badge(
        f"{at_risk} at risk",
        color="gray",
    )


    st.space(
        "stretch"
    )


    sort_by = (
        st.segmented_control(
            "Sort by",
            list(
                QUEUE_SORTS
            ),
            default="Priority",
            required=True,
            key="queue_sort",
            label_visibility=(
                "collapsed"
            ),
        )
    )


    st.download_button(
        "Export CSV",
        data=(
            filtered
            .to_csv(
                index=False
            )
            .encode(
                "utf-8"
            )
        ),
        file_name=(
            "tradeops_exception_queue.csv"
        ),
        mime="text/csv",
        icon=(
            ":material/download:"
        ),
        key=(
            "queue_export"
        ),
    )


# --------------------------------------------------
# Empty queue
# --------------------------------------------------

if filtered.empty:

    empty_state(
        (
            "No breaks match the current "
            "Market Scope and operational filters."
        )
    )

    st.stop()


# --------------------------------------------------
# Sort
# --------------------------------------------------

by, ascending = (
    QUEUE_SORTS[
        sort_by
        or "Priority"
    ]
)


queue = (
    filtered
    .sort_values(
        by,
        ascending=ascending,
        na_position="last",
    )
    .reset_index(
        drop=True
    )
)


# --------------------------------------------------
# Queue table
# --------------------------------------------------

event = breaks_table(
    queue,
    QUEUE_COLUMNS,
    alt=(
        "TradeOps exception queue"
    ),
    key=(
        "queue_table"
    ),
    selectable=True,
    max_height=680,
)


# --------------------------------------------------
# Selected incident
# --------------------------------------------------

selected_rows = (
    event.selection.rows
    if event is not None
    else []
)


if selected_rows:

    row = (
        queue.iloc[
            selected_rows[
                0
            ]
        ]
    )


    trade_id = str(
        row[
            "trade_id"
        ]
    )


    symbol = str(
        row.get(
            "symbol_exec",
            "",
        )
    )


    break_id = str(
        row[
            "break_id"
        ]
    )


    with st.container(
        horizontal=True,
        vertical_alignment="center",
    ):

        st.caption(
            (
                f"Selected {break_id} "
                f"· {symbol} "
                f"· {trade_id}"
            )
        )


        if st.button(
            f"Investigate {trade_id}",
            icon=(
                ":material/manage_search:"
            ),
            type="primary",
            key=(
                "queue_investigate"
            ),
        ):

            st.session_state[
                "focus_trade"
            ] = trade_id


            st.switch_page(
                "app_pages/"
                "trade_investigation.py"
            )


else:

    st.caption(
        (
            "Select a row to open the trade "
            "in Trade Investigation."
        )
    )