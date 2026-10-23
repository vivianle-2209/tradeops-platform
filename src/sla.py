"""Pure incident lifecycle and SLA rules. DuckDB owns persistence, never CSV."""

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from src.config import SLA_MINUTES, SLA_AT_RISK_FRACTION
from src.contracts import utc, utc_now, stable_id
from src.reconciliation import correction_proven

SLA_PRIORITY = {'BREACHED': 1, 'AT_RISK': 2, 'WITHIN_SLA': 3, 'UNKNOWN': 4, 'CLOSED': 5}


def classify_sla(row):
    if row.get('break_status') != 'OPEN':
        return 'CLOSED'
    if pd.isna(row.get('sla_minutes')) or pd.isna(row.get('age_minutes')):
        return 'UNKNOWN'
    if row['age_minutes'] >= row['sla_minutes']:
        return 'BREACHED'
    if row['age_minutes'] >= row['sla_minutes'] * SLA_AT_RISK_FRACTION:
        return 'AT_RISK'
    return 'WITHIN_SLA'


def age_incident(row, now):
    row = dict(row)
    # Lifetime first_seen is retained on reopening. Episode start is separately auditable.
    end = now if row['break_status'] == 'OPEN' else row['resolved_at']
    row['age_minutes'] = max((utc(end) - utc(row['first_seen_at'])).total_seconds() / 60, 0)
    row['sla_minutes'] = SLA_MINUTES.get(row['severity'])
    row['sla_remaining_minutes'] = row['sla_minutes'] - row['age_minutes']
    row['sla_consumed_pct'] = row['age_minutes'] / row['sla_minutes'] * 100
    row['sla_status'] = classify_sla(row)
    row['sla_priority'] = SLA_PRIORITY[row['sla_status']]
    return row


def merge_incidents(previous, observed, reconciliation, observed_trade_ids, run_id, now):
    """Return persistent incidents, including issues outside this ingestion batch."""
    now = utc(now)
    old = {row['dedup_key']: row for row in previous.to_dict('records')}
    fresh = {row['dedup_key']: row for row in observed.to_dict('records')}
    results = {row['trade_id']: row for row in reconciliation.to_dict('records')}
    merged = []
    for key in sorted(set(old) | set(fresh)):
        before, observation = old.get(key), fresh.get(key)
        is_observed = observation is not None and observation['trade_id'] in observed_trade_ids
        if before is None:
            row = dict(observation, incident_id=stable_id('INC', key), first_seen_at=now,
                       last_seen_at=now, detected_at=now, resolved_at=None, episode_started_at=now,
                       episode=1, escalated=False, event_version=0, state_fingerprint=None,
                       last_observed_run_id=run_id, resolution_reason=None)
        else:
            row = dict(before)
            if is_observed:
                row.update(observation)
                if before['break_status'] == 'RESOLVED':
                    row.update(episode=int(before['episode'])+1, episode_started_at=now)
                row.update(last_seen_at=now, last_observed_run_id=run_id, resolved_at=None,
                           break_status='OPEN', resolution_reason=None)
            elif row['trade_id'] in observed_trade_ids and correction_proven(
                    results.get(row['trade_id']), row['exception_type']):
                if row['break_status'] == 'OPEN':
                    row.update(results[row['trade_id']])
                    row['exception_impact'] = 0.
                    row.update(break_status='RESOLVED', resolved_at=now,
                               resolution_reason='RECONCILIATION_CORRECTION')
        row['is_observed'] = is_observed
        merged.append(age_incident(row, now))
    return pd.DataFrame(merged)
