"""SLA & risk: ageing, severity/SLA matrix, escalation queues, concentration."""

import streamlit as st

from tradeops_ui.charts import (
    PLOTLY_CONFIG, chart_card, fig_age_vs_severity, fig_exposure_by_group,
    fig_notional_by_sla, fig_severity_sla_matrix, fig_sla_distribution,
)
from tradeops_ui.components import empty_state, page_title
from tradeops_ui.data import get_context
from tradeops_ui.formatting import fmt_money
from tradeops_ui.tables import breaks_table
from tradeops_ui.theme import BLACK, PINK

SLA_TABLE_COLUMNS = [
    "break_id", "trade_id", "exception_type", "severity", "severity_score", "sla_status", "age_minutes",
    "sla_minutes", "sla_remaining_minutes", "affected_notional", "detected_at",
]
CONCENTRATION_DIMENSIONS = {
    "Exception type": "exception_type",
    "Venue": "venue",
    "Account": "account_exec",
    "Symbol": "symbol_exec",
}

ctx = get_context()
filtered = ctx.filtered

page_title("SLA & risk", "SLA ageing, escalation queues and exposure concentration for the current filter scope.")

# ---- SLA charts --------------------------------------------------------------

left, right = st.columns(2)
with left:
    chart_card("SLA status distribution", fig_sla_distribution(filtered), key="sla_dist")
with right:
    chart_card("Affected notional by SLA status", fig_notional_by_sla(filtered), key="sla_notional")

left, right = st.columns(2)
with left:
    chart_card("Severity × SLA matrix", fig_severity_sla_matrix(filtered), key="sla_matrix",
               caption="Break count per cell")
with right:
    chart_card("Break age vs severity", fig_age_vs_severity(filtered), key="sla_scatter",
               caption="Bubble size = affected notional")

# ---- Escalation queues -------------------------------------------------------

with st.container(border=True):
    breached = filtered[filtered["sla_status"].eq("BREACHED")].sort_values(
        ["severity_score", "age_minutes"], ascending=[False, False])
    st.markdown(f"**SLA breach queue** · {len(breached):,}")
    st.caption("Escalation candidates, highest severity and oldest first")
    if breached.empty:
        empty_state("No SLA breaches in the current scope.")
    else:
        breaks_table(breached, SLA_TABLE_COLUMNS, alt="SLA breach queue", key="sla_breach_table")

with st.container(border=True):
    severe = filtered[filtered["severity"].isin(["CRITICAL", "HIGH"])].sort_values("priority_rank")
    st.markdown(f"**Critical and high severity incidents** · {len(severe):,}")
    if severe.empty:
        empty_state("No critical or high severity breaks in the current scope.")
    else:
        breaks_table(severe, SLA_TABLE_COLUMNS, alt="Critical and high severity incidents", key="severe_table")

# ---- Exposure concentration --------------------------------------------------

with st.container(border=True):
    dims = {label: col for label, col in CONCENTRATION_DIMENSIONS.items() if col in filtered.columns}
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown("**Exposure concentration**")
        st.space("stretch")
        dim_label = st.segmented_control("Group by", list(dims), default="Exception type", required=True,
                                         key="conc_dim", label_visibility="collapsed") or "Exception type"
        measure_label = st.segmented_control(
            "Measure", ["Affected", "Gross"], default="Affected", required=True, key="conc_measure",
            label_visibility="collapsed", help="Affected = mismatched notional; Gross = full execution notional",
        )

    gross = measure_label == "Gross"
    column = dims[dim_label]
    measure = "execution_notional" if gross else "affected_notional"
    total = filtered[measure].fillna(0).sum()
    if total <= 0:
        empty_state("No exposure for this measure in the current scope.")
    else:
        grouped = filtered.groupby(filtered[column].fillna("UNKNOWN"))[measure].sum().sort_values(ascending=False)
        top3 = grouped.head(3).sum() / total
        st.caption(f"Top 3 of {len(grouped):,} {dim_label.lower()} groups hold {top3:.0%} of {fmt_money(total)}")
        st.plotly_chart(
            fig_exposure_by_group(filtered, column, measure, color=BLACK if gross else PINK, top=12),
            theme=None, config=PLOTLY_CONFIG, width="stretch", key="sla_concentration",
            alt=f"Exposure concentration by {dim_label}",
        )
