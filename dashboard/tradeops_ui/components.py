"""Custom HTML components, always rendered with st.html (never as Markdown)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from tradeops_ui.formatting import esc, is_missing


def badge(text) -> str:
    """Status badge; CSS class is derived from the value (e.g. bdg-critical)."""
    if is_missing(text):
        return ""
    label = str(text)
    css = "bdg-" + label.lower().replace(" ", "_")
    return f'<span class="bdg {esc(css)}">{esc(label.replace("_", " "))}</span>'


def page_title(title: str, subtitle: str) -> None:
    st.html(f'<div class="page-title">{esc(title)}<span>{esc(subtitle)}</span></div>')


def section_label(title: str, note: str | None = None) -> None:
    extra = f"<span>{esc(note)}</span>" if note else ""
    st.html(f'<div class="section-label">{esc(title)}{extra}</div>')


def empty_state(message: str) -> None:
    st.html(f'<div class="empty">{esc(message)}</div>')


def kpi_card(label: str, value: str, foot: str = "", alert: bool = False,
             progress: float | None = None) -> str:
    bar = ""
    if progress is not None:
        width = max(0.0, min(progress, 1.0)) * 100
        bar = f'<div class="kpi-bar"><span style="width:{width:.1f}%"></span></div>'
    return (
        f'<div class="kpi{" alert" if alert else ""}">'
        f'<div class="kpi-label">{esc(label)}</div>'
        f'<div class="kpi-value">{esc(value)}</div>'
        f'<div><div class="kpi-foot">{esc(foot)}</div>{bar}</div>'
        "</div>"
    )


def kpi_row(cards: list[str]) -> None:
    st.html(f'<div class="kpi-grid" style="--cols:{len(cards)}">{"".join(cards)}</div>')


def stat_strip(items: list[tuple[str, str, bool]]) -> None:
    """Light summary strip: (label, value, highlight)."""
    cells = "".join(
        f'<div class="stat"><div class="stat-label">{esc(label)}</div>'
        f'<div class="stat-value{" hot" if hot else ""}">{esc(value)}</div></div>'
        for label, value, hot in items
    )
    st.html(f'<div class="stat-strip">{cells}</div>')


def render_header(kpis: dict, db_status: str, live: bool, now: pd.Timestamp) -> None:
    live_chip = (
        '<span class="chip live"><span class="dot pulse"></span>LIVE</span>'
        if live else '<span class="chip"><span class="dot idle"></span>PAUSED</span>'
    )
    db_ok = db_status == "CONNECTED"
    open_class = "chip warn" if kpis.get("breached") else "chip"
    st.html(
        '<div class="to-header">'
        '<div class="to-brand"><div class="to-logo">TO</div><div>'
        '<div class="to-title">TradeOps</div>'
        '<div class="to-sub">Trading Operations Analytics &amp; Exception Management Platform</div>'
        "</div></div>"
        '<div class="to-meta">'
        f"{live_chip}"
        f'<span class="chip">{esc(now.strftime("%d/%m/%Y %H:%M:%S"))} UTC</span>'
        f'<span class="{open_class}">Open breaks <b>{kpis.get("open", 0):,}</b></span>'
        f'<span class="{"chip" if db_ok else "chip warn"}"><span class="dot {"ok" if db_ok else ""}"></span>'
        f"DB {esc(db_status.title())}</span>"
        "</div></div>"
    )


def render_sidebar_status(db_status: str, live: bool, interval: int, data: dict | None,
                          live_sla: bool) -> None:
    loaded_at = data["loaded_at"].strftime("%H:%M:%S") if data else "—"
    db_modified = (
        datetime.fromtimestamp(data["version"], timezone.utc).strftime("%d/%m %H:%M:%S")
        if data and data["version"] else "—"
    )
    monitor = (f'<span class="dot pulse"></span>Live · {interval}s' if live
               else '<span class="dot idle"></span>Paused')
    rows = [
        ("System", '<span class="dot ok" style="background:#F2F2F2"></span>Operational', ""),
        ("Monitoring", monitor, ""),
        ("Database", esc(db_status.title()), "" if db_status == "CONNECTED" else " hot"),
        ("Last DB read", f"{loaded_at} UTC", ""),
        ("DB modified", f"{db_modified} UTC", ""),
        ("SLA clock", "Live" if live_sla else "Pipeline snapshot", ""),
    ]
    body = "".join(
        f'<div class="sb-row"><span class="k">{esc(k)}</span><span class="v{hot}">{v}</span></div>'
        for k, v, hot in rows
    )
    st.html(
        '<div class="sb-brand"><div class="to-logo">TO</div><div>'
        '<div class="sb-name">TradeOps</div><div class="sb-tag">Ops control</div></div></div>'
        f'<div class="sb-status">{body}</div>'
    )
