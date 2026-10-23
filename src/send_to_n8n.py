"""Deliver committed DuckDB outbox events, with stable IDs and bounded retries.

Delivery is at least once: an HTTP accept followed by a crash can replay the same
stable event_id. Receiver-side event_id idempotency is necessary for exactly-once
business effects. This module never creates or reconstructs events during retry.
"""

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import pandas as pd
import requests
from src.config import Settings
from src.contracts import utc, utc_now
from src.events import build_payload, validate_payload
from src.storage import transaction


def dispatch_breaks(settings=None, *, client=None, now=None):
    settings = settings or Settings.from_env()
    client = client or requests
    now = utc(now) if now is not None else utc_now()
    sent = failed = attempted = 0
    while attempted < settings.dispatch_batch_size:
        with transaction(settings.db_path) as con:
            row = con.execute("""SELECT event_id, payload, retry_count FROM incident_outbox AS e
                WHERE delivery_status != 'DELIVERED' AND next_retry_at <= ?
                AND NOT EXISTS (SELECT 1 FROM incident_outbox AS earlier
                    WHERE earlier.incident_id=e.incident_id AND earlier.event_version<e.event_version
                    AND earlier.delivery_status!='DELIVERED')
                ORDER BY created_at, event_id LIMIT 1""", [now]).fetchone()
        if row is None:
            break
        event_id, encoded, retries = row
        attempted += 1
        try:
            payload = json.loads(encoded)
            validate_payload(payload)
            if not settings.webhook_url:
                raise ValueError('N8N_WEBHOOK_URL is not configured')
            response = client.post(settings.webhook_url, json=payload,
                                   headers={'Idempotency-Key': event_id}, timeout=settings.request_timeout)
            response.raise_for_status()
        except Exception as exc:
            failed += 1
            delay = min(settings.retry_base_seconds * 2 ** min(int(retries), 20), settings.retry_max_seconds)
            with transaction(settings.db_path) as con:
                con.execute("""UPDATE incident_outbox SET delivery_status='RETRY', retry_count=retry_count+1,
                    last_error=?, next_retry_at=? WHERE event_id=?""",
                    [type(exc).__name__, now + pd.Timedelta(seconds=delay), event_id])
        else:
            sent += 1
            with transaction(settings.db_path) as con:
                con.execute("""UPDATE incident_outbox SET delivery_status='DELIVERED', delivered_at=?,
                    last_error=NULL WHERE event_id=?""", [now, event_id])
    with transaction(settings.db_path) as con:
        pending = con.execute("SELECT COUNT(*) FROM incident_outbox WHERE delivery_status!='DELIVERED'").fetchone()[0]
    return dict(sent=sent, failed=failed, pending=pending)


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    result = dispatch_breaks()
    print(result)
    raise SystemExit(1 if result['failed'] or result['pending'] else 0)
