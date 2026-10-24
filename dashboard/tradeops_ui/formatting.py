"""Display formatting for money, durations, timestamps and categorical values."""

from __future__ import annotations

import html
from datetime import datetime

import numpy as np
import pandas as pd


def esc(value) -> str:
    """HTML-escape any value for safe interpolation into custom markup."""
    return html.escape("" if value is None else str(value))


def is_missing(value) -> bool:
    try:
        return value is None or bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def fmt_money(value) -> str:
    """$1,234,567.89"""
    if is_missing(value):
        return "—"
    value = float(value)
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def fmt_trade_id(value) -> str:
    """Compact display label; the permanent ID stays unchanged for lookups."""
    text = "" if is_missing(value) else str(value)
    return text if len(text) <= 26 else f"{text[:14]}\N{HORIZONTAL ELLIPSIS}{text[-6:]}"


def fmt_money_compact(value) -> str:
    """$1.2M / $350.4K — for KPI cards and chart labels."""
    if is_missing(value):
        return "—"
    value = float(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    for threshold, suffix in [(1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if value >= threshold:
            return f"{sign}${value / threshold:,.1f}{suffix}"
    return f"{sign}${value:,.0f}"


def fmt_int(value) -> str:
    return "—" if is_missing(value) else f"{int(value):,}"


def fmt_minutes(value) -> str:
    return "—" if is_missing(value) else f"{float(value):,.1f} min"


def fmt_duration(seconds) -> str:
    """Human duration: 45s, 3m 42s, 2h 05m."""
    if is_missing(seconds):
        return "—"
    seconds = float(seconds)
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    if seconds < 60:
        return f"{sign}{seconds:.0f}s"
    if seconds < 3600:
        return f"{sign}{int(seconds // 60)}m {int(seconds % 60):02d}s"
    return f"{sign}{int(seconds // 3600)}h {int(seconds % 3600 // 60):02d}m"


def to_utc(value) -> pd.Timestamp | None:
    if is_missing(value):
        return None
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    return None if pd.isna(ts) else ts


def fmt_ts(value) -> str:
    """DD/MM/YYYY HH:MM:SS (UTC)."""
    ts = to_utc(value)
    return "—" if ts is None else ts.strftime("%d/%m/%Y %H:%M:%S")


def fmt_value(value) -> str:
    """Generic display value for field/value panels."""
    if is_missing(value):
        return "—"
    if isinstance(value, (pd.Timestamp, datetime)):
        return fmt_ts(value)
    if isinstance(value, (float, np.floating)):
        return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.4f}".rstrip("0")
    if isinstance(value, (int, np.integer)):
        return f"{value:,}"
    return str(value)


def ordered(values, canonical: list[str]) -> list[str]:
    """Canonical values first (in order), then any extras found in the data."""
    present = list(pd.Series(values).dropna().astype(str).unique())
    return [v for v in canonical if v in present] + sorted(v for v in present if v not in canonical)


def worst(values, canonical: list[str]):
    """Most severe value from a series according to a canonical ordering."""
    present = set(pd.Series(values).dropna().astype(str))
    for value in canonical:
        if value in present:
            return value
    return next(iter(sorted(present)), None)
