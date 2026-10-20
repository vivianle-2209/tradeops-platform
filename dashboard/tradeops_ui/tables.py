"""Formatted, colour-coded break tables built on st.dataframe + pandas Styler."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tradeops_ui.data import TIMESTAMP_COLUMNS
from tradeops_ui.formatting import fmt_int, fmt_money, fmt_ts, is_missing
from tradeops_ui.theme import BLACK, PINK, PINK_LIGHT

MONEY_COLUMNS = ["execution_notional", "affected_notional"]
MINUTE_COLUMNS = ["age_minutes", "sla_minutes", "sla_remaining_minutes"]

SEVERITY_CELL = {
    "CRITICAL": f"background-color:{BLACK};color:#FFFFFF;font-weight:700",
    "HIGH": f"background-color:{PINK};color:#FFFFFF;font-weight:600",
    "MEDIUM": f"background-color:{PINK_LIGHT};color:#7A1048",
    "LOW": "color:#555555",
}
SLA_CELL = {
    "BREACHED": f"background-color:{BLACK};color:{PINK};font-weight:700",
    "AT_RISK": f"background-color:{PINK_LIGHT};color:#7A1048;font-weight:600",
    "WITHIN_SLA": "color:#555555",
}
COLUMN_LABELS = {
    "priority_rank": "Rank",
    "break_id": "Break ID",
    "trade_id": "Trade ID",
    "exception_type": "Exception",
    "severity": "Severity",
    "severity_score": "Score",
    "sla_status": "SLA",
    "age_minutes": "Age (min)",
    "sla_minutes": "SLA (min)",
    "sla_remaining_minutes": "SLA left (min)",
    "affected_notional": "Affected notional",
    "execution_notional": "Execution notional",
    "break_status": "Status",
    "detected_at": "Detected (UTC)",
    "first_seen_at": "First seen (UTC)",
    "venue": "Venue",
    "account_exec": "Account",
    "symbol_exec": "Symbol",
}


def _fmt_minutes_cell(value) -> str:
    return "—" if is_missing(value) else f"{value:,.1f}"


def styled_breaks(df: pd.DataFrame, columns: list[str]):
    """Pandas Styler with ops formatting and severity/SLA highlighting."""
    view = df[columns].reset_index(drop=True)
    formats = {c: fmt_money for c in MONEY_COLUMNS if c in columns}
    formats.update({c: _fmt_minutes_cell for c in MINUTE_COLUMNS if c in columns})
    formats.update({c: fmt_ts for c in TIMESTAMP_COLUMNS if c in columns})
    formats.update({c: fmt_int for c in ["priority_rank", "severity_score"] if c in columns})
    styler = view.style.format(formats, na_rep="—")
    if "severity" in columns:
        styler = styler.map(lambda v: SEVERITY_CELL.get(v, ""), subset=["severity"])
    if "sla_status" in columns:
        styler = styler.map(lambda v: SLA_CELL.get(v, ""), subset=["sla_status"])
    if "sla_remaining_minutes" in columns:
        styler = styler.map(lambda v: "color:#D81B7A;font-weight:700" if not is_missing(v) and v < 0 else "",
                            subset=["sla_remaining_minutes"])
    return styler


def breaks_table(df: pd.DataFrame, columns: list[str], alt: str, key: str,
                 selectable: bool = False, max_height: int = 560):
    """Render a formatted break table. Returns the selection state when selectable."""
    columns = [c for c in columns if c in df.columns]
    height = min(36 * (len(df) + 1) + 4, max_height)
    return st.dataframe(
        styled_breaks(df, columns),
        hide_index=True,
        width="stretch",
        height=height,
        column_config={c: st.column_config.Column(COLUMN_LABELS.get(c, c)) for c in columns},
        key=key,
        on_select="rerun" if selectable else "ignore",
        selection_mode="single-row",
        alt=alt,
    )
