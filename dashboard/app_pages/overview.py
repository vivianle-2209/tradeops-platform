"""Overview: firm-wide KPIs, break mix, exposure and top risks."""

import streamlit as st

from tradeops_ui.charts import (
    chart_card, fig_age_histogram, fig_breaks_by_type, fig_breaks_by_venue,
    fig_exposure_by_group, fig_severity_donut,
)
from tradeops_ui.components import badge, empty_state, kpi_card, kpi_row, section_label, stat_strip
from tradeops_ui.data import get_context
from tradeops_ui.formatting import esc, fmt_duration, fmt_int, fmt_money, fmt_money_compact

ctx = get_context()
kpis, filtered = ctx.kpis, ctx.filtered

# ---- Firm-wide KPIs ------------------------------------------------------

section_label("Trading health", "firm-wide")
kpi_row([
    kpi_card("Total trades", f"{kpis['total']:,}", "Ingested executions"),
    kpi_card("Matched trades", f"{kpis['matched']:,}", f"{kpis['match_rate']:.1f}% match rate",
             progress=kpis["match_rate"] / 100),
    kpi_card("Broken trades", f"{kpis['broken']:,}", f"{kpis['break_count']:,} exceptions raised"),
    kpi_card("Break rate", f"{kpis['break_rate']:.2f}%", "Broken / total", progress=kpis["break_rate"] / 100),
    kpi_card("Critical breaks", f"{kpis['critical']:,}", "Severity critical", alert=kpis["critical"] > 0),
    kpi_card("Affected notional", fmt_money_compact(kpis["affected"]), fmt_money(kpis["affected"])),
])

section_label("SLA & operations")
kpi_row([
    kpi_card("SLA breached", f"{kpis['breached']:,}", "Escalate now" if kpis["breached"] else "None breached",
             alert=kpis["breached"] > 0),
    kpi_card("At risk", f"{kpis['at_risk']:,}", "≥75% of SLA consumed", alert=kpis["at_risk"] > 0),
    kpi_card("Avg break age", f"{kpis['avg_age']:,.1f} min", "Open breaks"),
    kpi_card("Avg clearing latency", fmt_duration(kpis["avg_latency"]), "Execution → clearing"),
    kpi_card("Open breaks", f"{kpis['open']:,}", f"of {kpis['break_count']:,} total breaks",
             progress=kpis["open"] / kpis["break_count"] if kpis["break_count"] else 0),
])

# ---- Filtered scope summary ------------------------------------------------

total_trades = kpis["total"]
scope_rate = filtered["trade_id"].nunique() / total_trades * 100 if total_trades else 0.0
scope_critical = int(filtered["severity"].eq("CRITICAL").sum())

section_label("Operational summary", "current filter scope")
stat_strip([
    ("Break rate", f"{scope_rate:.2f}%", False),
    ("Critical incidents", f"{scope_critical:,}", scope_critical > 0),
    ("Avg clearing latency", fmt_duration(filtered["clearing_latency_seconds"].mean()), False),
    ("Affected notional", fmt_money(filtered["affected_notional"].fillna(0).sum()), False),
])

# ---- Charts ------------------------------------------------------------------

left, right = st.columns([3, 2])
with left:
    chart_card("Breaks by exception type", fig_breaks_by_type(filtered), key="ov_by_type")
with right:
    chart_card("Severity distribution", fig_severity_donut(filtered), key="ov_severity")

left, right = st.columns(2)
with left:
    chart_card("Breaks by venue", fig_breaks_by_venue(filtered), key="ov_venue", caption="Stacked by severity")
with right:
    chart_card("Break age distribution", fig_age_histogram(filtered), key="ov_age")

left, right = st.columns([3, 2])
with left:
    chart_card("Financial exposure by exception type", fig_exposure_by_group(filtered, "exception_type"),
               key="ov_exposure", caption="Affected notional and share of total; types with no exposure omitted",
               empty_message="No affected notional in the current scope.")
with right:
    with st.container(border=True):
        st.markdown("**Top 5 highest-risk breaks**")
        st.caption("By priority rank")
        if filtered.empty:
            empty_state("No breaks match the current filters.")
        else:
            top = filtered.sort_values(["priority_rank", "severity_score"], ascending=[True, False]).head(5)
            rows = "".join(
                '<div class="risk-row">'
                f'<div class="risk-rank">{esc(fmt_int(row["priority_rank"]))}</div>'
                f'<div class="risk-main"><b>{esc(row["trade_id"])}</b>'
                f'<div>{esc(str(row["exception_type"]).replace("_", " "))} · {esc(row["break_id"])}</div></div>'
                f'<div class="risk-side">{esc(fmt_money(row["affected_notional"]))}'
                f'<div>{badge(row["severity"])}{badge(row["sla_status"])}</div></div>'
                "</div>"
                for _, row in top.iterrows()
            )
            st.html(f'<div class="risk-list">{rows}</div>')
