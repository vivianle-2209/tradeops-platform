"""Explainable exposure measures. Totals are always deduplicated by trade."""
import pandas as pd


def exposure_by_group(frame, column=None, measure="affected_notional"):
    if frame.empty or measure not in frame:
        return pd.Series(dtype=float)
    working = frame.copy()
    if "break_status" in working:
        working = working[working.break_status.eq("OPEN")]
    working[measure] = pd.to_numeric(working[measure], errors="coerce").fillna(0)
    if column:
        working[column] = working[column].fillna("UNKNOWN")
    # Attribute the full trade proxy to its largest-impact exception, then severity,
    # then stable incident key. Group totals therefore also sum to the grand total.
    sorts = [measure] + [name for name in ("exception_impact", "severity_score", "dedup_key")
                         if name in working and name != measure]
    working = working.sort_values(sorts, ascending=[False] * len(sorts), na_position="last")
    working = working.drop_duplicates("trade_id")
    return (working.groupby(column, dropna=False)[measure].sum() if column
            else working.set_index("trade_id")[measure])


def total_exposure(frame, measure="affected_notional"):
    return float(exposure_by_group(frame, measure=measure).sum())
