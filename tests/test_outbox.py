import json
import pandas as pd
import requests
from src.contracts import RunContext
from src.load_database import persist_run
from src.send_to_n8n import dispatch_breaks
from conftest import query, Client, Response


def save(settings, execution, clearing, run, now):
    return persist_run(execution, clearing, settings=settings, run=run, now=now)


def test_high_emits_once_and_payload_preserves_evidence(settings, execution, high, run, now):
    save(settings, execution, high, run, now)
    save(settings, execution, high, RunContext('repeat', now), now)
    rows = query(settings, 'SELECT event_id,event_type,event_version,payload FROM incident_outbox')
    assert len(rows) == 1 and rows[0][1:3] == ('ESCALATE', 1)
    payload = json.loads(rows[0][3])
    assert payload['event_id'] == rows[0][0]
    assert payload['evidence']['clear']['quantity'] == 20
    assert payload['reconciliation']['clearing_account'] == high.account.iloc[0]


def test_failure_retry_preserves_event_and_survives_window(settings, execution, high, run, now):
    save(settings, execution, high, run, now)
    original = query(settings, 'SELECT event_id,payload FROM incident_outbox')
    failed = dispatch_breaks(settings, client=Client([requests.Timeout('offline')]), now=now)
    assert failed == dict(sent=0, failed=1, pending=1)
    assert query(settings, 'SELECT delivery_status,retry_count FROM incident_outbox') == [('RETRY', 1)]
    save(settings, execution.iloc[:0], high.iloc[:0], RunContext('empty', now), now+pd.Timedelta(seconds=30))
    client = Client([Response()])
    delivered = dispatch_breaks(settings, client=client, now=now+pd.Timedelta(seconds=60))
    assert delivered == dict(sent=1, failed=0, pending=0)
    assert query(settings, 'SELECT event_id,payload FROM incident_outbox') == original
    assert client.calls[0][1]['headers']['Idempotency-Key'] == original[0][0]


def test_retry_backoff_is_respected(settings, execution, high, run, now):
    save(settings, execution, high, run, now)
    dispatch_breaks(settings, client=Client([requests.Timeout()]), now=now)
    client = Client([])
    assert dispatch_breaks(settings, client=client, now=now+pd.Timedelta(seconds=1))['pending'] == 1
    assert not client.calls


def test_resolution_and_medium_downgrade_update_existing_escalation(settings, execution, high, clearing, run, now):
    save(settings, execution, high, run, now)
    save(settings, execution, clearing.assign(quantity=11), RunContext('downgrade', now), now+pd.Timedelta(minutes=1))
    save(settings, execution, clearing, RunContext('resolved', now), now+pd.Timedelta(minutes=2))
    rows = query(settings, 'SELECT event_type,payload FROM incident_outbox ORDER BY event_version')
    assert [r[0] for r in rows] == ['ESCALATE', 'UPDATE', 'RESOLVED']
    assert json.loads(rows[1][1])['risk']['severity'] == 'MEDIUM'
    assert json.loads(rows[2][1])['lifecycle']['break_status'] == 'RESOLVED'
    assert json.loads(rows[2][1])['reconciliation']['clearing_quantity'] == 10


def test_unrelated_medium_does_not_escalate(settings, execution, clearing, run, now):
    save(settings, execution, clearing.assign(quantity=11), run, now)
    assert query(settings, 'SELECT severity,escalated FROM incidents') == [('MEDIUM', False)]
    assert query(settings, 'SELECT COUNT(*) FROM incident_outbox') == [(0,)]


def test_events_deliver_in_version_order_even_if_old_event_failed(settings, execution, high, clearing, run, now):
    save(settings, execution, high, run, now)
    save(settings, execution, clearing, RunContext('resolved', now), now+pd.Timedelta(seconds=1))
    client = Client([requests.Timeout()])
    result = dispatch_breaks(settings, client=client, now=now+pd.Timedelta(seconds=2))
    assert len(client.calls) == 1 and result['pending'] == 2
    client = Client([Response(), Response()])
    assert dispatch_breaks(settings, client=client, now=now+pd.Timedelta(seconds=120))['sent'] == 2
    assert [call[1]['json']['event_type'] for call in client.calls] == ['ESCALATE', 'RESOLVED']


def test_delivered_event_is_never_sent_again(settings, execution, high, run, now):
    save(settings, execution, high, run, now)
    dispatch_breaks(settings, client=Client([Response()]), now=now)
    assert dispatch_breaks(settings, client=Client([]), now=now)['sent'] == 0
