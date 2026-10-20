"""Exception queue: prioritised, filterable incident queue."""

import streamlit as st

from tradeops_ui.components import empty_state, page_title
from tradeops_ui.data import get_context
from tradeops_ui.tables import breaks_table

QUEUE_COLUMNS = [
    "priority_rank", "break_id", "trade_id", "exception_type", "severity", "severity_score",
    "sla_status", "age_minutes", "sla_remaining_minutes", "affected_notional", "break_status", "detected_at",
]
QUEUE_SORTS = {
    "Priority": (["priority_rank"], [True]),
    "SLA remaining": (["sla_remaining_minutes", "priority_rank"], [True, True]),
    "Notional": (["affected_notional", "priority_rank"], [False, True]),
    "Age": (["age_minutes", "priority_rank"], [False, True]),
}

ctx = get_context()
filtered = ctx.filtered

page_title("Exception queue", "Open and historical breaks, most urgent first. Use the sidebar to filter.")

breached = int(filtered["sla_status"].eq("BREACHED").sum())
at_risk = int(filtered["sla_status"].eq("AT_RISK").sum())
critical = int(filtered["severity"].eq("CRITICAL").sum())

with st.container(horizontal=True, vertical_alignment="center"):
    st.markdown(f"Showing **{len(filtered):,}** of **{len(ctx.breaks):,}** breaks")
    st.badge(f"{critical} critical", color="primary" if critical else "gray")
    st.badge(f"{breached} breached", color="primary" if breached else "gray")
    st.badge(f"{at_risk} at risk", color="gray")
    st.space("stretch")
    sort_by = st.segmented_control("Sort by", list(QUEUE_SORTS), default="Priority", required=True,
                                   key="queue_sort", label_visibility="collapsed")
    st.download_button("Export CSV", data=filtered.to_csv(index=False).encode("utf-8"),
                       file_name="tradeops_exception_queue.csv", mime="text/csv",
                       icon=":material/download:", key="queue_export")

if filtered.empty:
    empty_state("No breaks match the current filters. Adjust or reset the sidebar filters.")
    st.stop()

by, ascending = QUEUE_SORTS[sort_by or "Priority"]
queue = filtered.sort_values(by, ascending=ascending, na_position="last").reset_index(drop=True)
event = breaks_table(queue, QUEUE_COLUMNS, alt="Exception queue", key="queue_table",
                     selectable=True, max_height=680)

selected_rows = event.selection.rows if event is not None else []
if selected_rows:
    row = queue.iloc[selected_rows[0]]
    trade_id = str(row["trade_id"])
    with st.container(horizontal=True, vertical_alignment="center"):
        st.caption(f"Selected {row['break_id']} on {trade_id}")
        if st.button(f"Investigate {trade_id}", icon=":material/manage_search:", type="primary",
                     key="queue_investigate"):
            st.session_state["focus_trade"] = trade_id
            st.switch_page("app_pages/trade_investigation.py")
else:
    st.caption("Select a row to open the trade in Trade Investigation.")
