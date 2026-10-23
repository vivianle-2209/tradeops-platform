"""Identifiers, validated tabular contracts, and explicit DuckDB column types."""
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from uuid import uuid4

import numpy as np
import pandas as pd


def utc_now():
    return pd.Timestamp.now(tz="UTC").floor("s")


def utc(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError("Timestamp must not be null")
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def stable_id(prefix, *parts):
    # JSON encoding makes component boundaries unambiguous.
    encoded = json.dumps([str(p) for p in parts], separators=(",", ":"), ensure_ascii=True)
    return prefix + "-" + hashlib.sha256(encoded.encode()).hexdigest()


def trade_identity(source, symbol, market_trade_id, execution_timestamp, venue):
    """Scope source IDs by feed, symbol, UTC trading date, and exchange."""
    return stable_id("TRD", source, symbol, utc(execution_timestamp).date(), venue, market_trade_id)


class RunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    SUCCESS_NO_DATA = "SUCCESS_NO_DATA"
    PARTIAL_INGESTION = "PARTIAL_INGESTION"
    INGESTION_FAILED = "INGESTION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    DATABASE_FAILED = "DATABASE_FAILED"
    DISPATCH_PARTIAL_FAILURE = "DISPATCH_PARTIAL_FAILURE"
    DISPATCH_FAILED = "DISPATCH_FAILED"


@dataclass(frozen=True)
class RunContext:
    run_id: str = field(default_factory=lambda: "RUN-" + str(uuid4()))
    started_at: pd.Timestamp = field(default_factory=utc_now)

    @property
    def snapshot_id(self):
        return stable_id("SNP", self.run_id)


EXECUTION = {
    "trade_id": "VARCHAR", "source": "VARCHAR", "market_trade_id": "VARCHAR",
    "record_source": "VARCHAR", "order_id": "VARCHAR", "symbol": "VARCHAR",
    "side": "VARCHAR", "quantity": "DOUBLE", "price": "DOUBLE",
    "execution_notional": "DOUBLE", "currency": "VARCHAR", "account": "VARCHAR",
    "venue": "VARCHAR", "execution_timestamp": "TIMESTAMPTZ", "trader_id": "VARCHAR",
    "trade_conditions": "VARCHAR", "tape": "VARCHAR",
}
CLEARING = {
    "clearing_id": "VARCHAR", "trade_id": "VARCHAR", "source": "VARCHAR",
    "record_source": "VARCHAR", "symbol": "VARCHAR", "side": "VARCHAR",
    "quantity": "DOUBLE", "price": "DOUBLE", "currency": "VARCHAR", "account": "VARCHAR",
    "venue": "VARCHAR", "clearing_timestamp": "TIMESTAMPTZ", "clearing_status": "VARCHAR",
}
RECONCILIATION = {
    "trade_id": "VARCHAR", "symbol": "VARCHAR", "source_exec": "VARCHAR", "source_clear": "VARCHAR",
    **{f"{name}_{side}": dtype for side in ("exec", "clear") for name, dtype in {
        "symbol": "VARCHAR", "side": "VARCHAR", "quantity": "DOUBLE", "price": "DOUBLE",
        "currency": "VARCHAR", "account": "VARCHAR", "venue": "VARCHAR"}.items()},
    "market_trade_id": "VARCHAR", "order_id": "VARCHAR", "trader_id": "VARCHAR",
    "venue": "VARCHAR", "clearing_id": "VARCHAR", "execution_timestamp": "TIMESTAMPTZ",
    "clearing_timestamp": "TIMESTAMPTZ", "clearing_status": "VARCHAR", "clearing_record_count": "BIGINT",
    "execution_notional": "DOUBLE", "clearing_notional": "DOUBLE", "trade_exposure": "DOUBLE",
    "quantity_difference": "DOUBLE", "price_difference": "DOUBLE", "affected_notional": "DOUBLE",
    "clearing_latency_seconds": "DOUBLE", "break_count": "BIGINT", "reconciliation_status": "VARCHAR",
    "exception_types": "VARCHAR", "execution_present": "BOOLEAN", "clearing_present": "BOOLEAN",
}
BREAK = {**RECONCILIATION, "break_id": "VARCHAR", "dedup_key": "VARCHAR", "exception_type": "VARCHAR",
         "exception_impact": "DOUBLE", "break_status": "VARCHAR", "severity_score": "BIGINT",
         "severity": "VARCHAR", "priority_rank": "BIGINT"}
INCIDENT = {**BREAK, "incident_id": "VARCHAR", "first_seen_at": "TIMESTAMPTZ",
            "last_seen_at": "TIMESTAMPTZ", "resolved_at": "TIMESTAMPTZ", "detected_at": "TIMESTAMPTZ",
            "episode_started_at": "TIMESTAMPTZ", "episode": "BIGINT", "resolution_reason": "VARCHAR",
            "age_minutes": "DOUBLE", "sla_minutes": "DOUBLE", "sla_remaining_minutes": "DOUBLE",
            "sla_consumed_pct": "DOUBLE", "sla_status": "VARCHAR", "sla_priority": "BIGINT",
            "is_observed": "BOOLEAN", "last_observed_run_id": "VARCHAR", "escalated": "BOOLEAN",
            "event_version": "BIGINT", "state_fingerprint": "VARCHAR"}
OUTBOX = {
    "event_id": "VARCHAR", "incident_id": "VARCHAR", "dedup_key": "VARCHAR", "trade_id": "VARCHAR",
    "break_id": "VARCHAR", "event_type": "VARCHAR", "event_version": "BIGINT", "payload": "JSON",
    "created_at": "TIMESTAMPTZ", "delivery_status": "VARCHAR", "delivered_at": "TIMESTAMPTZ",
    "retry_count": "BIGINT", "last_error": "VARCHAR", "next_retry_at": "TIMESTAMPTZ",
}
PIPELINE_RUN = {
    "run_id": "VARCHAR", "started_at": "TIMESTAMPTZ", "finished_at": "TIMESTAMPTZ",
    "status": "VARCHAR", "ingestion_status": "VARCHAR", "state_committed": "BOOLEAN", "error": "VARCHAR", "symbol_errors": "JSON",
    "snapshot_id": "VARCHAR", "snapshot_number": "BIGINT", "snapshot_at": "TIMESTAMPTZ",
    "total_trades": "BIGINT", "matched_trades": "BIGINT", "broken_trades": "BIGINT",
    "break_rate": "DOUBLE", "affected_notional": "DOUBLE", "symbol_count": "BIGINT",
    "break_observations": "BIGINT", "dispatch_sent": "BIGINT", "dispatch_failed": "BIGINT",
    "dispatch_pending": "BIGINT",
}
HISTORY_META = {"run_id": "VARCHAR", "snapshot_id": "VARCHAR", "snapshot_at": "TIMESTAMPTZ"}


def normalize_frame(frame, schema, *, required=(), key=()):
    """Validate, coerce explicitly, and order a frame at a stage boundary."""
    frame = frame.copy()
    if not frame.empty:
        missing = set(required) - set(frame.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
    for name, dtype in schema.items():
        if name not in frame:
            frame[name] = pd.Series(index=frame.index, dtype="object")
        if dtype == "TIMESTAMPTZ":
            frame[name] = pd.to_datetime(frame[name], utc=True, errors="raise", format="mixed")
        elif dtype in ("DOUBLE", "BIGINT"):
            frame[name] = pd.to_numeric(frame[name], errors="raise")
            if np.isinf(frame[name].dropna().astype(float)).any():
                raise ValueError(f"Nonfinite {name}")
            frame[name] = frame[name].astype("Int64" if dtype == "BIGINT" else "float64")
        elif dtype == "BOOLEAN":
            frame[name] = frame[name].astype("boolean")
        else:
            frame[name] = frame[name].map(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x).astype("string")
    for name in required:
        if frame[name].isna().any() or (schema[name] == "VARCHAR" and frame[name].str.strip().eq("").any()):
            raise ValueError(f"Null/empty required field: {name}")
    if key and frame.duplicated(list(key)).any():
        raise ValueError(f"Duplicate key: {key}")
    for name in ("price", "quantity"):
        if name in schema and frame[name].dropna().le(0).any():
            raise ValueError(f"{name} must be positive")
    return frame[list(schema)]


def execution_frame(frame):
    return normalize_frame(frame, EXECUTION, required=("trade_id", "source", "symbol", "market_trade_id",
                           "quantity", "price", "execution_timestamp"), key=("trade_id",))


def clearing_frame(frame):
    return normalize_frame(frame, CLEARING, required=("clearing_id", "trade_id", "symbol", "quantity",
                           "price", "clearing_timestamp", "clearing_status"), key=("clearing_id",))


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value.item() if hasattr(value, "item") else value
