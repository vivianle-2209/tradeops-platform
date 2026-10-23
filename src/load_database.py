"""Transactional operational state, incidents, history, checkpoints and outbox."""

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from pathlib import Path
import duckdb
import pandas as pd
from src.config import Settings
from src.contracts import (RunContext, RunStatus, EXECUTION, CLEARING, RECONCILIATION,
                           INCIDENT, PIPELINE_RUN, execution_frame, clearing_frame,
                           normalize_frame, utc_now, utc)
from src.events import event_for_incident
from src.metrics import total_exposure
from src.reconciliation import reconcile_trades, create_break_table
from src.severity import score_breaks
from src.sla import merge_incidents, age_incident
from src.storage import transaction, read_frame, write_frame


def _summary(reconciliation, incidents):
    total = len(reconciliation)
    matched = int(reconciliation.reconciliation_status.eq('MATCHED').sum())
    return dict(total_trades=total, matched_trades=matched, broken_trades=total-matched,
                break_rate=(total-matched)/total*100 if total else 0.,
                affected_notional=total_exposure(incidents), symbol_count=int(reconciliation.symbol.nunique()),
                break_observations=int(incidents.is_observed.sum()) if not incidents.empty else 0)


def _persist_incidents(con, incidents, now):
    rows, events = [], []
    for row in incidents.to_dict('records'):
        updated, event = event_for_incident(row, now)
        rows.append(updated)
        if event:
            events.append(event)
    frame = normalize_frame(pd.DataFrame(rows), INCIDENT, required=('dedup_key', 'incident_id'), key=('dedup_key',))
    if not frame.empty:
        frame = frame.sort_values(['sla_priority', 'severity_score', 'age_minutes', 'dedup_key'],
                                  ascending=[True, False, False, True]).reset_index(drop=True)
        frame['priority_rank'] = range(1, len(frame)+1)
    write_frame(con, 'incidents', frame, replace_keys=('dedup_key',))
    write_frame(con, 'incident_outbox', pd.DataFrame(events))
    return frame


def persist_run(executions, clearing, *, run, settings=None, checkpoints=None,
                ingestion_status=RunStatus.SUCCESS, advance_checkpoints=True, now=None,
                failpoint=None):
    """One commit for all operational state. Retrying a run_id is a no-op.

    Failed-attempt diagnostics and post-HTTP delivery status are separate transactions;
    neither can expose a partially committed operational snapshot.
    """
    settings = settings or Settings.from_env()
    now = utc(now) if now is not None else utc_now()
    ingestion_status = RunStatus(ingestion_status)
    if ingestion_status not in {RunStatus.SUCCESS, RunStatus.SUCCESS_NO_DATA}:
        raise ValueError('Only a complete, validated ingestion batch can commit operational state')
    executions, clearing = execution_frame(executions), clearing_frame(clearing)
    with transaction(settings.db_path) as con:
        existing = con.execute('SELECT snapshot_id, state_committed FROM pipeline_runs WHERE run_id=?', [run.run_id]).fetchone()
        if existing and existing[1]:
            return existing[0]
        touched = set(executions.trade_id) | set(clearing.trade_id)
        if not clearing.empty:
            con.register('identity_check', clearing)
            reassigned = con.execute('''SELECT COUNT(*) FROM clearing_records c JOIN identity_check n
                USING (clearing_id) WHERE c.trade_id != n.trade_id''').fetchone()[0]
            con.unregister('identity_check')
            if reassigned:
                raise ValueError('A clearing_id cannot be reassigned to another trade')
        write_frame(con, 'executions', executions, replace_keys=('trade_id',))
        # A supplied clearing population is authoritative FOR its supplied trades.
        # This allows a duplicate population to be corrected without deleting other trades.
        if not clearing.empty:
            con.register('clearing_updates', clearing)
            con.execute('DELETE FROM clearing_records WHERE trade_id IN (SELECT trade_id FROM clearing_updates)')
            con.unregister('clearing_updates')
        write_frame(con, 'clearing_records', clearing, replace_keys=('clearing_id',))
        all_executions = read_frame(con, 'executions', EXECUTION)
        all_clearing = read_frame(con, 'clearing_records', CLEARING)
        results = reconcile_trades(all_executions, all_clearing)
        write_frame(con, 'reconciliation_results', results, replace_keys=('trade_id',))
        previous = read_frame(con, 'incidents', INCIDENT)
        observed = score_breaks(create_break_table(results))
        incidents = merge_incidents(previous, observed, results, touched, run.run_id, now)
        incidents = _persist_incidents(con, incidents, now)
        if failpoint:
            failpoint(con)  # Used by rollback tests; no production side effects.
        summary = _summary(results, incidents)
        snapshot_id, snapshot_number = None, None
        if not results.empty:
            snapshot_id = run.snapshot_id
            snapshot_number = con.execute('SELECT COALESCE(MAX(snapshot_number),0)+1 FROM pipeline_runs').fetchone()[0]
            meta = dict(run_id=run.run_id, snapshot_id=snapshot_id, snapshot_at=now)
            write_frame(con, 'reconciliation_history', results.assign(**meta))
            write_frame(con, 'trade_breaks_history', incidents.assign(**meta))
        if advance_checkpoints:
            for symbol, position in (checkpoints or {}).items():
                con.execute("""INSERT INTO ingestion_checkpoints VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (source, symbol) DO UPDATE SET
                    position=GREATEST(ingestion_checkpoints.position, excluded.position),
                    run_id=excluded.run_id, updated_at=excluded.updated_at""",
                    [settings.source, symbol, utc(position), run.run_id, now])
        status = ingestion_status.value if isinstance(ingestion_status, RunStatus) else ingestion_status
        record = dict(run_id=run.run_id, started_at=run.started_at, finished_at=now,
                      status=status, ingestion_status=status, state_committed=True, snapshot_id=snapshot_id,
                      snapshot_number=snapshot_number, snapshot_at=now if snapshot_id else None,
                      symbol_errors='{}', **summary)
        write_frame(con, 'pipeline_runs', pd.DataFrame([record]), replace_keys=('run_id',))
        return snapshot_id


def record_failure(run, status, *, settings=None, errors=None, error=None):
    """Diagnostic metadata only; failed ingestion never advances state/checkpoints."""
    settings = settings or Settings.from_env()
    with transaction(settings.db_path) as con:
        existing = con.execute('SELECT state_committed FROM pipeline_runs WHERE run_id=?', [run.run_id]).fetchone()
        if existing and existing[0]:
            return  # Never overwrite a committed run with an attempted replay failure.
        record = dict(run_id=run.run_id, started_at=run.started_at, finished_at=utc_now(),
                      status=status.value, ingestion_status=status.value, state_committed=False,
                      error=error, symbol_errors=json.dumps(errors or {}))
        write_frame(con, 'pipeline_runs', pd.DataFrame([record]), replace_keys=('run_id',))


def update_dispatch_status(db_path, run_id, result):
    with transaction(db_path) as con:
        current = con.execute('SELECT status FROM pipeline_runs WHERE run_id=?', [run_id]).fetchone()
        if not current:
            raise ValueError('Dispatch run_id has not been persisted')
        status = current[0]
        if status not in {RunStatus.SUCCESS.value, RunStatus.SUCCESS_NO_DATA.value,
                          RunStatus.DISPATCH_FAILED.value, RunStatus.DISPATCH_PARTIAL_FAILURE.value}:
            pass  # Preserve the source/database failure; delivery counters are independent.
        elif result['failed']:
            status = (RunStatus.DISPATCH_PARTIAL_FAILURE if result['sent'] else RunStatus.DISPATCH_FAILED).value
        elif result['pending']:
            status = RunStatus.DISPATCH_PARTIAL_FAILURE.value
        elif status in [RunStatus.DISPATCH_FAILED.value, RunStatus.DISPATCH_PARTIAL_FAILURE.value]:
            status = con.execute('SELECT ingestion_status FROM pipeline_runs WHERE run_id=?', [run_id]).fetchone()[0]
        con.execute('UPDATE pipeline_runs SET status=?, dispatch_sent=?, dispatch_failed=?, dispatch_pending=?, finished_at=? WHERE run_id=?',
                    [status, result['sent'], result['failed'], result['pending'], utc_now(), run_id])
        return status


def resolve_incident(db_path, dedup_key, reason, *, now=None):
    """Explicit operator resolution API. Requires an auditable reason; emits an event."""
    if not reason or not reason.strip():
        raise ValueError('An explicit resolution requires a reason')
    now = utc(now) if now is not None else utc_now()
    with transaction(db_path) as con:
        frame = read_frame(con, 'incidents', INCIDENT)
        selected = frame[frame.dedup_key.eq(dedup_key)]
        if selected.empty:
            raise KeyError(dedup_key)
        row = selected.iloc[0].to_dict()
        if row['break_status'] == 'RESOLVED':
            return
        row.update(break_status='RESOLVED', resolved_at=now, resolution_reason=reason, is_observed=False)
        _persist_incidents(con, pd.DataFrame([age_incident(row, now)]), now)


def existing_execution_ids(db_path):
    if not Path(db_path).exists():
        return set()
    with duckdb.connect(str(db_path), read_only=True) as con:
        exists = con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='executions'").fetchone()[0]
        return {row[0] for row in con.execute('SELECT trade_id FROM executions').fetchall()} if exists else set()


if __name__ == '__main__':
    raise SystemExit('Use python run_pipeline.py; persistence requires an explicit run context.')
