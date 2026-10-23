"""Versioned n8n contract and meaningful incident-change events."""
from __future__ import annotations
import json
from src.config import ESCALATION_SEVERITIES
from src.contracts import json_safe, stable_id

def build_payload(
    row: pd.Series,
) -> dict:
    """
    Build the TradeOps -> n8n event.

    TradeOps remains authoritative for:
    exception_type, severity, lifecycle and SLA.
    """

    payload = {

        "source": (
            "TRADEOPS"
        ),


        # ------------------------------------------
        # Identity
        # ------------------------------------------

        "break_id": (
            row.get(
                "break_id"
            )
        ),

        "dedup_key": (
            row.get(
                "dedup_key"
            )
        ),

        "trade_id": (
            row.get(
                "trade_id"
            )
        ),

        "exception_type": (
            row.get(
                "exception_type"
            )
        ),


        # ------------------------------------------
        # Trade
        # ------------------------------------------

        "trade": {

            "symbol": (
                row.get("symbol")
            ),

            "side": (
                row.get(
                    "side_exec"
                )
            ),

            "venue": (
                row.get(
                    "venue"
                )
            ),

            "account": (
                row.get(
                    "account_exec"
                )
            ),

            "currency": (
                row.get(
                    "currency_exec"
                )
            ),
        },


        # ------------------------------------------
        # Reconciliation evidence
        # ------------------------------------------

        "reconciliation": {

            "execution_quantity": (
                row.get(
                    "quantity_exec"
                )
            ),

            "clearing_quantity": (
                row.get(
                    "quantity_clear"
                )
            ),

            "quantity_difference": (
                row.get(
                    "quantity_difference"
                )
            ),

            "execution_price": (
                row.get(
                    "price_exec"
                )
            ),

            "clearing_price": (
                row.get(
                    "price_clear"
                )
            ),

            "price_difference": (
                row.get(
                    "price_difference"
                )
            ),

            "execution_side": (
                row.get(
                    "side_exec"
                )
            ),

            "clearing_side": (
                row.get(
                    "side_clear"
                )
            ),

            "execution_account": (
                row.get(
                    "account_exec"
                )
            ),

            "clearing_account": (
                row.get(
                    "account_clear"
                )
            ),

            "execution_currency": (
                row.get(
                    "currency_exec"
                )
            ),

            "clearing_currency": (
                row.get(
                    "currency_clear"
                )
            ),
        },


        # ------------------------------------------
        # Exposure
        # ------------------------------------------

        "exposure": {

            "execution_notional": (
                row.get(
                    "execution_notional"
                )
            ),

            "affected_notional": (
                row.get(
                    "affected_notional"
                )
            ),
        },


        # ------------------------------------------
        # Clearing
        # ------------------------------------------

        "clearing": {

            "status": (
                row.get(
                    "clearing_status"
                )
            ),

            "latency_seconds": (
                row.get(
                    "clearing_latency_seconds"
                )
            ),

            "record_count": (
                row.get(
                    "clearing_record_count"
                )
            ),

            "timestamp": (
                row.get(
                    "clearing_timestamp"
                )
            ),
        },


        # ------------------------------------------
        # Risk
        # ------------------------------------------

        "risk": {

            "severity_score": (
                row.get(
                    "severity_score"
                )
            ),

            "severity": (
                row.get(
                    "severity"
                )
            ),

            "priority_rank": (
                row.get(
                    "priority_rank"
                )
            ),
        },


        # ------------------------------------------
        # SLA
        # ------------------------------------------

        "sla": {

            "age_minutes": (
                row.get(
                    "age_minutes"
                )
            ),

            "sla_minutes": (
                row.get(
                    "sla_minutes"
                )
            ),

            "remaining_minutes": (
                row.get(
                    "sla_remaining_minutes"
                )
            ),

            "consumed_pct": (
                row.get(
                    "sla_consumed_pct"
                )
            ),

            "status": (
                row.get(
                    "sla_status"
                )
            ),
        },


        # ------------------------------------------
        # Lifecycle
        # ------------------------------------------

        "lifecycle": {

            "detected_at": (
                row.get(
                    "detected_at"
                )
            ),

            "first_seen_at": (
                row.get(
                    "first_seen_at"
                )
            ),

            "last_seen_at": (
                row.get(
                    "last_seen_at"
                )
            ),

            "resolved_at": (
                row.get(
                    "resolved_at"
                )
            ),

            "break_status": (
                row.get(
                    "break_status"
                )
            ),
        },
    }


    return json_safe(
        payload
    )


def state_fingerprint(row):
    fields = ['severity', 'sla_status', 'break_status', 'episode', 'exception_impact',
              'clearing_status', 'clearing_record_count', 'symbol_exec', 'symbol_clear',
              'account_exec', 'account_clear', 'currency_exec', 'currency_clear',
              'side_exec', 'side_clear', 'quantity_exec', 'quantity_clear', 'price_exec',
              'price_clear', 'venue_exec', 'venue_clear', 'clearing_timestamp']
    return stable_id('STATE', json.dumps(json_safe({key: row.get(key) for key in fields}), sort_keys=True))


def event_for_incident(row, now):
    row = dict(row)
    fingerprint = state_fingerprint(row)
    escalated = bool(row.get('escalated', False))
    should_escalate = row['break_status'] == 'OPEN' and row['severity'] in ESCALATION_SEVERITIES
    event_type = None
    if not escalated and should_escalate:
        event_type = 'ESCALATE'
    elif escalated and fingerprint != row.get('state_fingerprint'):
        event_type = 'RESOLVED' if row['break_status'] == 'RESOLVED' else 'UPDATE'
    row['state_fingerprint'] = fingerprint
    if event_type is None:
        return row, None
    row['event_version'] = int(row.get('event_version', 0)) + 1
    row['escalated'] = True  # Escalation intent is durable even before delivery.
    event_id = stable_id('EVT', row['incident_id'], row['event_version'])
    payload = build_payload(row)
    payload.update(schema_version=1, event_id=event_id, incident_id=row['incident_id'],
                   event_type=event_type, event_version=row['event_version'])
    payload['exposure'].update(trade_exposure=row.get('trade_exposure'),
                               exception_impact=row.get('exception_impact'))
    payload['evidence'] = {side: {field: row.get(f'{field}_{side}') for field in
                            ['symbol', 'account', 'quantity', 'price', 'currency', 'side', 'venue', 'source']}
                           for side in ['exec', 'clear']}
    payload = json_safe(payload)
    validate_payload(payload)
    return row, dict(event_id=event_id, incident_id=row['incident_id'], dedup_key=row['dedup_key'],
                     trade_id=row['trade_id'], break_id=row['break_id'], event_type=event_type,
                     event_version=row['event_version'], payload=json.dumps(payload, allow_nan=False),
                     created_at=now, delivery_status='PENDING', delivered_at=None, retry_count=0,
                     last_error=None, next_retry_at=now)


def validate_payload(payload):
    for key in ['event_id', 'incident_id', 'dedup_key', 'trade_id', 'break_id', 'event_type', 'event_version']:
        if not payload.get(key):
            raise ValueError(f'Missing n8n payload field: {key}')
    for key in ['trade', 'reconciliation', 'exposure', 'clearing', 'risk', 'sla', 'lifecycle', 'evidence']:
        if not isinstance(payload.get(key), dict):
            raise ValueError(f'Missing n8n payload section: {key}')
    json.dumps(payload, allow_nan=False)
