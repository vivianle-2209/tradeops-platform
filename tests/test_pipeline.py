import pandas as pd
import pytest
import run_pipeline
from src.contracts import RunStatus, RunContext
from src.ingestion import IngestionBatch
from src.load_database import persist_run
from conftest import query, Client, Response


@pytest.mark.parametrize('status', [RunStatus.INGESTION_FAILED, RunStatus.PARTIAL_INGESTION])
def test_failed_ingestion_records_status_but_no_operational_data(settings, run, now, monkeypatch, status):
    monkeypatch.setattr(run_pipeline, 'ingest', lambda *a, **k: IngestionBatch(pd.DataFrame(), status, {'AAPL': now}, {'AAPL': 'offline'}))
    assert run_pipeline.execute_pipeline(settings, run, persist_only=True) == status.value
    assert query(settings, 'SELECT COUNT(*) FROM executions') == [(0,)]
    assert query(settings, 'SELECT COUNT(*) FROM ingestion_checkpoints') == [(0,)]
    assert query(settings, 'SELECT status FROM pipeline_runs') == [(status.value,)]


def test_successful_empty_cycle_has_no_historical_snapshot(settings, run, monkeypatch):
    monkeypatch.setattr(run_pipeline, 'ingest', lambda *a, **k: IngestionBatch(pd.DataFrame(), RunStatus.SUCCESS_NO_DATA))
    assert run_pipeline.execute_pipeline(settings, run) == RunStatus.SUCCESS_NO_DATA.value
    assert query(settings, 'SELECT COUNT(*) FROM reconciliation_history') == [(0,)]
    assert query(settings, 'SELECT state_committed FROM pipeline_runs') == [(True,)]


def test_failed_dispatch_propagates_to_pipeline(settings, execution, high, run, now):
    persist_run(execution, high, settings=settings, run=run, now=now)
    import requests
    status = run_pipeline.execute_pipeline(settings, run, dispatch_client=Client([requests.Timeout('offline')]))
    assert status == RunStatus.DISPATCH_FAILED.value
    assert query(settings, 'SELECT status FROM pipeline_runs') == [(status,)]


def test_persisted_run_replay_does_not_fetch_again(settings, execution, high, run, now, monkeypatch):
    persist_run(execution, high, settings=settings, run=run, now=now)
    monkeypatch.setattr(run_pipeline, 'ingest', lambda *a, **k: pytest.fail('Committed replay must not fetch'))
    assert run_pipeline.execute_pipeline(settings, run, persist_only=True) == RunStatus.SUCCESS.value


def test_pipeline_validation_failure_does_not_advance(settings, run, raw, now, monkeypatch):
    batch = IngestionBatch(raw.assign(p=0), RunStatus.SUCCESS, {'AAPL': now})
    monkeypatch.setattr(run_pipeline, 'ingest', lambda *a, **k: batch)
    assert run_pipeline.execute_pipeline(settings, run, persist_only=True) == RunStatus.VALIDATION_FAILED.value
    assert query(settings, 'SELECT COUNT(*) FROM ingestion_checkpoints') == [(0,)]


def test_orchestrator_database_failure_is_explicit(settings, run, raw, now, monkeypatch):
    monkeypatch.setattr(run_pipeline, 'ingest', lambda *a, **k: IngestionBatch(raw, RunStatus.SUCCESS))
    monkeypatch.setattr(run_pipeline, 'persist_run', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('injected')))
    assert run_pipeline.execute_pipeline(settings, run, persist_only=True) == RunStatus.DATABASE_FAILED.value
    assert query(settings, 'SELECT status FROM pipeline_runs') == [(RunStatus.DATABASE_FAILED.value,)]


def test_no_data_replay_is_idempotent(settings, run, monkeypatch):
    monkeypatch.setattr(run_pipeline, 'ingest', lambda *a, **k: IngestionBatch(pd.DataFrame(), RunStatus.SUCCESS_NO_DATA))
    assert run_pipeline.execute_pipeline(settings, run, persist_only=True) == RunStatus.SUCCESS_NO_DATA.value
    monkeypatch.setattr(run_pipeline, 'ingest', lambda *a, **k: pytest.fail('No-data replay must not fetch'))
    assert run_pipeline.execute_pipeline(settings, run, persist_only=True) == RunStatus.SUCCESS_NO_DATA.value


def test_full_source_to_outbox_flow_with_mocked_clients(settings, run, raw, now, monkeypatch):
    from src.contracts import clearing_frame
    def simulated_break(executions):
        records = executions.copy()
        records['clearing_id'] = 'integration-clearing'
        records['clearing_timestamp'] = now + pd.Timedelta(minutes=3)
        records['clearing_status'] = 'CONFIRMED'
        records['quantity'] = 20
        return clearing_frame(records)
    monkeypatch.setattr(run_pipeline, 'generate_clearing', simulated_break)
    source = Client([Response({'trades': raw.drop(columns='symbol').to_dict('records')})])
    destination = Client([Response()])
    status = run_pipeline.execute_pipeline(settings, run, start=now-pd.Timedelta(minutes=30), end=now,
                                           client=source, dispatch_client=destination)
    assert status == RunStatus.SUCCESS.value
    assert query(settings, 'SELECT snapshot_number FROM pipeline_runs') == [(1,)]
    assert query(settings, 'SELECT delivery_status FROM incident_outbox') == [('DELIVERED',)]
    assert len(source.calls) == 1 and len(destination.calls) == 1
    assert query(settings, 'SELECT COUNT(*) FROM ingestion_checkpoints') == [(0,)]  # Backfill.
