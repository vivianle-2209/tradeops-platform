import duckdb
import pandas as pd
import pytest
from src.contracts import RunContext, RunStatus
from src.load_database import persist_run, resolve_incident
from conftest import query


def persist(settings, execution, clearing, run, now, **kwargs):
    return persist_run(execution, clearing, settings=settings, run=run, now=now, **kwargs)


def test_first_clean_run_is_snapshot_one(settings, execution, high, run, now):
    persist(settings, execution, high, run, now)
    assert query(settings, 'SELECT snapshot_number FROM pipeline_runs') == [(1,)]
    assert query(settings, 'SELECT COUNT(*) FROM reconciliation_history') == [(1,)]
    assert query(settings, 'SELECT COUNT(*) FROM schema_migrations') == [(1,)]


def test_empty_legacy_baseline_migrates_without_touching_archives(settings, execution, high, run, now):
    with duckdb.connect(str(settings.db_path)) as con:
        for table in ['executions', 'clearing_records', 'reconciliation_results', 'trade_breaks']:
            con.execute(f'CREATE TABLE {table} (legacy VARCHAR)')
        con.execute('CREATE TABLE historical_archive AS SELECT 42 AS value')
    persist(settings, execution, high, run, now)
    assert query(settings, 'SELECT * FROM historical_archive') == [(42,)]
    assert query(settings, 'SELECT snapshot_number FROM pipeline_runs') == [(1,)]


def test_nonempty_legacy_database_is_never_destroyed(settings, execution, high, run, now):
    with duckdb.connect(str(settings.db_path)) as con:
        con.execute('CREATE TABLE executions AS SELECT 42 AS legacy')
    with pytest.raises(RuntimeError, match='explicit migration'):
        persist(settings, execution, high, run, now)
    assert query(settings, 'SELECT legacy FROM executions') == [(42,)]


def test_run_replay_is_idempotent_and_new_run_appends(settings, execution, high, run, now):
    first = persist(settings, execution, high, run, now)
    assert persist(settings, execution, high, run, now + pd.Timedelta(minutes=1)) == first
    assert query(settings, 'SELECT COUNT(*) FROM reconciliation_history') == [(1,)]
    persist(settings, execution, high, RunContext('second', now), now + pd.Timedelta(minutes=1))
    assert query(settings, 'SELECT snapshot_number FROM pipeline_runs ORDER BY snapshot_number') == [(1,), (2,)]


def test_transaction_failure_rolls_back_every_state_table(settings, execution, high, run, now):
    persist(settings, execution, high, run, now, checkpoints={'AAPL': now})
    tables = ['executions', 'clearing_records', 'reconciliation_results', 'incidents',
              'incident_outbox', 'pipeline_runs', 'reconciliation_history', 'trade_breaks_history', 'ingestion_checkpoints']
    before = {table: query(settings, f'SELECT * FROM {table} ORDER BY ALL') for table in tables}
    def fail(con):
        raise RuntimeError('injected after incident/outbox writes')
    with pytest.raises(RuntimeError, match='injected'):
        persist(settings, execution, high.assign(quantity=10), RunContext('failed', now),
                now + pd.Timedelta(hours=1), checkpoints={'AAPL': now + pd.Timedelta(hours=1)}, failpoint=fail)
    assert {table: query(settings, f'SELECT * FROM {table} ORDER BY ALL') for table in tables} == before


def test_first_run_rollback_does_not_leave_schema_or_history(settings, execution, high, run, now):
    with pytest.raises(RuntimeError):
        persist(settings, execution, high, run, now, failpoint=lambda con: (_ for _ in ()).throw(RuntimeError()))
    with duckdb.connect(str(settings.db_path), read_only=True) as con:
        assert con.execute('SHOW TABLES').fetchall() == []


def test_window_disappearance_keeps_open_and_ages_sla(settings, execution, high, run, now):
    persist(settings, execution, high, run, now)
    persist(settings, execution.iloc[:0], high.iloc[:0], RunContext('empty', now), now + pd.Timedelta(hours=1),
            ingestion_status=RunStatus.SUCCESS_NO_DATA)
    state = query(settings, 'SELECT break_status, first_seen_at, last_seen_at, age_minutes, sla_status, is_observed FROM incidents')[0]
    assert state[0] == 'OPEN' and pd.Timestamp(state[1]) == now and pd.Timestamp(state[2]) == now
    assert state[3:] == (60., 'BREACHED', False)
    assert query(settings, "SELECT COUNT(*) FROM trade_breaks WHERE break_status='OPEN'") == [(1,)]


def test_repeat_observation_preserves_first_seen(settings, execution, high, run, now):
    persist(settings, execution, high, run, now)
    later = now + pd.Timedelta(minutes=10)
    persist(settings, execution, high, RunContext('again', later), later)
    first, last, age = query(settings, 'SELECT first_seen_at,last_seen_at,age_minutes FROM incidents')[0]
    assert pd.Timestamp(first) == now and pd.Timestamp(last) == later and age == 10


def test_actual_correction_resolves_and_reopening_keeps_identity(settings, execution, high, clearing, run, now):
    persist(settings, execution, high, run, now)
    identity = query(settings, 'SELECT incident_id,break_id,first_seen_at FROM incidents')[0]
    persist(settings, execution, clearing, RunContext('corrected', now), now + pd.Timedelta(minutes=10))
    assert query(settings, 'SELECT break_status,sla_status FROM incidents') == [('RESOLVED', 'CLOSED')]
    persist(settings, execution, high, RunContext('reopened', now), now + pd.Timedelta(minutes=20))
    assert query(settings, 'SELECT incident_id,break_id,first_seen_at FROM incidents')[0] == identity
    assert query(settings, 'SELECT break_status,episode,age_minutes FROM incidents') == [('OPEN', 2, 20.)]


def test_unrelated_trade_cannot_resolve_old_incident(settings, execution, high, run, now):
    persist(settings, execution, high, run, now)
    other = execution.assign(trade_id='unrelated', market_trade_id='other')
    persist(settings, other, high.iloc[:0], RunContext('unrelated', now), now + pd.Timedelta(minutes=10))
    assert query(settings, 'SELECT break_status FROM incidents WHERE trade_id=?', [execution.trade_id.iloc[0]]) == [('OPEN',)]


def test_explicit_resolution_requires_reason_and_is_idempotent(settings, execution, high, run, now):
    persist(settings, execution, high, run, now)
    key = query(settings, 'SELECT dedup_key FROM incidents')[0][0]
    with pytest.raises(ValueError):
        resolve_incident(settings.db_path, key, '')
    resolve_incident(settings.db_path, key, 'Operator verified external correction', now=now + pd.Timedelta(minutes=1))
    resolve_incident(settings.db_path, key, 'Repeated command', now=now + pd.Timedelta(minutes=2))
    assert query(settings, "SELECT COUNT(*) FROM incident_outbox WHERE event_type='RESOLVED'") == [(1,)]


def test_no_data_before_first_trade_does_not_consume_snapshot_one(settings, execution, high, run, now):
    persist(settings, execution.iloc[:0], high.iloc[:0], run, now, ingestion_status=RunStatus.SUCCESS_NO_DATA,
            checkpoints={'AAPL': now})
    assert query(settings, 'SELECT snapshot_number FROM pipeline_runs') == [(None,)]
    assert query(settings, 'SELECT COUNT(*) FROM reconciliation_history') == [(0,)]
    persist(settings, execution, high, RunContext('first-data', now), now)
    assert query(settings, 'SELECT MAX(snapshot_number) FROM pipeline_runs') == [(1,)]
