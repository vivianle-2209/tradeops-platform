"""Building blocks for the trade investigation page."""

from __future__ import annotations

import math

import pandas as pd

from tradeops_ui.components import badge
from tradeops_ui.data import load_trade_records
from tradeops_ui.formatting import (
    esc, fmt_duration, fmt_int, fmt_minutes, fmt_money, fmt_ts, fmt_value, is_missing, to_utc, worst,
)
from tradeops_ui.theme import BLACK, GREY_MID, PINK, SEVERITY_ORDER, SLA_ORDER

# (label, execution field, clearing field, kind)
COMPARISON_FIELDS = [
    ("Symbol", "symbol", "symbol", "text"),
    ("Side", "side", "side", "text"),
    ("Quantity", "quantity", "quantity", "qty"),
    ("Price", "price", "price", "price"),
    ("Notional", "notional", "notional", "money"),
    ("Currency", "currency", "currency", "text"),
    ("Account", "account", "account", "text"),
]


# --------------------------------------------------
# Records
# --------------------------------------------------

def trade_options(filtered: pd.DataFrame) -> pd.DataFrame:
    """One row per trade in scope, ordered by its most urgent break."""
    return (
        filtered.groupby("trade_id")
        .agg(rank=("priority_rank", "min"),
             severity=("severity", lambda s: worst(s, SEVERITY_ORDER)),
             types=("exception_type", lambda s: ", ".join(sorted(s.dropna().astype(str).unique()))))
        .sort_values("rank")
    )


def _record_from_breaks(trade_breaks: pd.DataFrame, suffix: str) -> dict:
    """Fallback record built from trade_breaks' *_exec / *_clear columns."""
    row = trade_breaks.iloc[0]
    record = {f: row.get(f"{f}_{suffix}") for f in ["symbol", "side", "quantity", "price", "currency", "account"]}
    record["timestamp"] = row.get("execution_timestamp" if suffix == "exec" else "clearing_timestamp")
    return record


def _with_notional(record: dict) -> dict:
    qty, price = record.get("quantity"), record.get("price")
    record["notional"] = None if is_missing(qty) or is_missing(price) else float(qty) * float(price)
    return record


def resolve_records(trade_id: str, trade_breaks: pd.DataFrame, version: float):
    """
    Execution record and list of clearing records for a trade, preferring the
    source tables and falling back to reconciled values on the break rows.
    Returns (execution, clearing_records, exec_df, clear_df, error).
    """
    error = None
    try:
        exec_df, clear_df = load_trade_records(trade_id, version)
    except Exception as exc:
        exec_df, clear_df, error = pd.DataFrame(), pd.DataFrame(), str(exc)

    if not exec_df.empty:
        execution = exec_df.iloc[0].to_dict()
        execution["timestamp"] = execution.get("execution_timestamp")
    else:
        execution = _record_from_breaks(trade_breaks, "exec")
        execution["venue"] = trade_breaks["venue"].iloc[0]
    execution = _with_notional(execution)

    # There may be no clearing record (missing) or several (duplicates).
    clearing_records = []
    for _, row in clear_df.iterrows():
        record = row.to_dict()
        record["timestamp"] = record.get("clearing_timestamp")
        clearing_records.append(_with_notional(record))
    reconciled_count = pd.to_numeric(trade_breaks.get("clearing_record_count", pd.Series(dtype=float)),
                                     errors="coerce")
    if clear_df.empty and reconciled_count.max() > 0:
        clearing_records.append(_with_notional(_record_from_breaks(trade_breaks, "clear")))

    return execution, clearing_records, exec_df, clear_df, error


# --------------------------------------------------
# Comparison
# --------------------------------------------------

def _compare(exec_value, clear_value, kind: str) -> tuple[str, str]:
    """Returns (status, difference_text) for one field."""
    if is_missing(clear_value) and not is_missing(exec_value):
        return "MISSING", "—"
    if is_missing(exec_value) or is_missing(clear_value):
        return "MATCH", "—"
    if kind == "text":
        same = str(exec_value).strip().upper() == str(clear_value).strip().upper()
        return ("MATCH", "—") if same else ("MISMATCH", "differs")
    diff = float(clear_value) - float(exec_value)
    if math.isclose(diff, 0.0, abs_tol=1e-9):
        return "MATCH", "—"
    if kind == "qty":
        text = f"{diff:+,.0f}"
    elif kind == "money":
        text = ("+" if diff > 0 else "-") + fmt_money(abs(diff))
    else:
        text = f"{diff:+,.4f}".rstrip("0").rstrip(".")
    return "MISMATCH", text


def _fmt_field(value, kind: str) -> str:
    if is_missing(value):
        return "—"
    if kind == "qty":
        return f"{float(value):,.0f}"
    if kind == "money":
        return fmt_money(value)
    if kind == "price":
        return f"{float(value):,.4f}".rstrip("0").rstrip(".")
    return str(value)


def comparison_table(execution: dict, clearing: dict | None) -> tuple[str, int]:
    """HTML field-by-field comparison; returns (html, mismatch_count)."""
    rows, mismatches = [], 0
    for label, exec_field, clear_field, kind in COMPARISON_FIELDS:
        exec_value = execution.get(exec_field)
        clear_value = clearing.get(clear_field) if clearing else None
        status, diff = _compare(exec_value, clear_value, kind)
        mismatches += status == "MISMATCH"
        rows.append(
            f'<tr class="{"diff" if status != "MATCH" else ""}">'
            f'<td class="f">{esc(label)}</td>'
            f"<td>{esc(_fmt_field(exec_value, kind))}</td>"
            f"<td>{esc(_fmt_field(clear_value, kind))}</td>"
            f'<td class="d">{esc(diff)}</td>'
            f"<td>{badge(status)}</td></tr>"
        )
    table = (
        '<table class="cmp"><thead><tr><th>Field</th><th>Execution</th><th>Clearing</th>'
        f'<th>Difference</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )
    return table, mismatches


# --------------------------------------------------
# Panels
# --------------------------------------------------

def kv_panel(items: list[tuple[str, object]]) -> str:
    return '<div class="kv">' + "".join(
        f'<span class="k">{esc(k)}</span><span class="v">{esc(fmt_value(v))}</span>' for k, v in items
    ) + "</div>"


def trade_summary_card(trade_id: str, execution: dict, trade_breaks: pd.DataFrame) -> str:
    severity = worst(trade_breaks["severity"], SEVERITY_ORDER)
    sla = worst(trade_breaks["sla_status"], SLA_ORDER)
    affected = trade_breaks["affected_notional"].max()
    fields = [
        ("Symbol", execution.get("symbol"), False),
        ("Side", execution.get("side"), False),
        ("Venue", execution.get("venue") or trade_breaks["venue"].iloc[0], False),
        ("Account", execution.get("account"), False),
        ("Execution notional", fmt_money(trade_breaks["execution_notional"].max()), False),
        ("Affected notional", fmt_money(affected), bool(not is_missing(affected) and affected > 0)),
        ("Open breaks", f'{int(trade_breaks["break_status"].eq("OPEN").sum())} / {len(trade_breaks)}', False),
    ]
    grid = "".join(
        f'<div><div class="k">{esc(k)}</div><div class="v{" hot" if hot else ""}">{esc(fmt_value(v))}</div></div>'
        for k, v, hot in fields
    )
    return (
        '<div class="trade-card"><div class="trade-top">'
        f'<div class="trade-id"><span>TRADE</span>{esc(trade_id)}</div>'
        f'<div class="trade-badges">{badge(severity)}{badge(sla)}</div></div>'
        f'<div class="trade-grid">{grid}</div></div>'
    )


def break_cards(trade_breaks: pd.DataFrame) -> str:
    cards = []
    for _, row in trade_breaks.sort_values("priority_rank").iterrows():
        consumed = row.get("sla_consumed_pct")
        width = 0 if is_missing(consumed) else max(0.0, min(float(consumed), 100.0))
        bar_color = {"BREACHED": BLACK, "AT_RISK": PINK}.get(row["sla_status"], GREY_MID)
        sev_class = f"sev-{str(row['severity']).lower()}"
        cards.append(
            f'<div class="brk {esc(sev_class)}">'
            f'<div class="brk-head"><span class="brk-id">{esc(row["break_id"])}</span>'
            f'<span>{badge(row["severity"])} {badge(row["sla_status"])}</span></div>'
            f'<div class="brk-type">{esc(str(row["exception_type"]).replace("_", " "))}</div>'
            + kv_panel([
                ("Severity score", fmt_int(row["severity_score"])),
                ("Status", row["break_status"]),
                ("Age", fmt_minutes(row["age_minutes"])),
                ("SLA remaining", fmt_minutes(row["sla_remaining_minutes"])),
                ("Affected notional", fmt_money(row["affected_notional"])),
                ("Dedup key", row["dedup_key"]),
            ])
            + f'<div class="sla-bar" title="SLA consumed {width:.0f}%">'
              f'<span style="width:{width:.1f}%;background:{bar_color}"></span></div>'
            "</div>"
        )
    return f'<div class="brk-grid">{"".join(cards)}</div>'


def timeline(execution: dict, clearing: dict | None, trade_breaks: pd.DataFrame) -> str:
    """Chronological operational timeline; missing events render as pending."""
    exec_ts = to_utc(execution.get("timestamp"))
    resolved = trade_breaks["resolved_at"]
    events = [
        ("Executed", exec_ts, ""),
        ("Cleared", to_utc(clearing.get("timestamp")) if clearing else None, ""),
        ("Break detected", to_utc(trade_breaks["detected_at"].min()), "accent"),
        ("First seen", to_utc(trade_breaks["first_seen_at"].min()), ""),
        ("Last seen", to_utc(trade_breaks["last_seen_at"].max()), ""),
        ("Resolved", to_utc(resolved.max()) if resolved.notna().all() else None, ""),
    ]
    items = []
    for label, ts, css in sorted((e for e in events if e[1] is not None), key=lambda e: e[1]):
        delta = ""
        if exec_ts is not None and ts != exec_ts:
            delta = f"<span>T+{esc(fmt_duration((ts - exec_ts).total_seconds()))}</span>"
        items.append(f'<div class="tl-item {css}"><div class="tl-dot"></div>'
                     f'<div class="tl-label">{esc(label)}</div><div class="tl-time">{esc(fmt_ts(ts))}{delta}</div></div>')
    for label, ts, _ in events:
        if ts is None:
            note = "No clearing record" if label == "Cleared" else "Pending"
            items.append(f'<div class="tl-item pending"><div class="tl-dot"></div>'
                         f'<div class="tl-label">{esc(label)}</div><div class="tl-time">{esc(note)}</div></div>')
    return f'<div class="tl">{"".join(items)}</div>'
