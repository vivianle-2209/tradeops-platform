"""Single-worker TradeOps orchestration; run data never crosses stages via CSV.

The Actions workflow splits persistence and dispatch to durably publish the outbox
before any external HTTP effect. Local default mode performs both stages.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import logging
from logging.handlers import RotatingFileHandler
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from src.cleaning import clean_trades
from src.config import PROJECT_ROOT, Settings
from src.contracts import RunContext, RunStatus, EXECUTION, CLEARING, normalize_frame, utc_now
from src.enrich_executions import enrich_executions
from src.generate_clearing import generate_clearing
from src.ingestion import ingest
from src.load_database import (persist_run, record_failure, existing_execution_ids, update_dispatch_status)
from src.send_to_n8n import dispatch_breaks

HEALTHY = {RunStatus.SUCCESS.value, RunStatus.SUCCESS_NO_DATA.value}


def build_logger():
    logger = logging.getLogger('tradeops_pipeline')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        directory = PROJECT_ROOT / 'logs'
        directory.mkdir(exist_ok=True)
        handlers = [logging.StreamHandler(), RotatingFileHandler(directory / 'pipeline.log',
                    maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')]
        for handler in handlers:
            handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
            logger.addHandler(handler)
    return logger


def execute_pipeline(settings, run, *, start=None, end=None, persist_only=False,
                     client=None, dispatch_client=None):
    """Inject clients in tests. Neither importing nor constructing settings calls APIs."""
    logger = build_logger()
    started = time.perf_counter()
    logger.info('START | run_id=%s', run.run_id)
    # A committed replay must not fetch/reroll any source data.
    import duckdb
    if Path(settings.db_path).exists():
        with duckdb.connect(str(settings.db_path), read_only=True) as con:
            exists = con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='schema_migrations'").fetchone()[0]
            committed = exists and con.execute('SELECT COUNT(*) FROM pipeline_runs WHERE run_id=? AND state_committed=TRUE', [run.run_id]).fetchone()[0]
        if committed:
            if persist_only:
                with duckdb.connect(str(settings.db_path), read_only=True) as con:
                    return con.execute('SELECT ingestion_status FROM pipeline_runs WHERE run_id=?', [run.run_id]).fetchone()[0]
            result = dispatch_breaks(settings, client=dispatch_client)
            return update_dispatch_status(settings.db_path, run.run_id, result)
    try:
        batch = ingest(settings, start=start, end=end, client=client)
    except Exception as exc:
        logger.exception('FAILED | ingestion | run_id=%s', run.run_id)
        record_failure(run, RunStatus.INGESTION_FAILED, settings=settings, error=type(exc).__name__)
        return RunStatus.INGESTION_FAILED.value
    if batch.errors:
        record_failure(run, batch.status, settings=settings, errors=batch.errors)
        logger.error('%s | run_id=%s | failed_symbols=%s', batch.status.value, run.run_id, list(batch.errors))
        # Previously committed delivery remains independent of source availability.
        if not persist_only:
            result = dispatch_breaks(settings, client=dispatch_client)
            update_dispatch_status(settings.db_path, run.run_id, result)
        return batch.status.value
    try:
        executions = (normalize_frame(pd.DataFrame(), EXECUTION) if batch.trades.empty
                      else enrich_executions(clean_trades(batch.trades)))
        new = executions[~executions.trade_id.isin(existing_execution_ids(settings.db_path))]
        clearing = generate_clearing(new) if not new.empty else normalize_frame(pd.DataFrame(), CLEARING)
    except Exception as exc:
        logger.exception('FAILED | validation | run_id=%s', run.run_id)
        record_failure(run, RunStatus.VALIDATION_FAILED, settings=settings, error=type(exc).__name__)
        return RunStatus.VALIDATION_FAILED.value
    try:
        snapshot = persist_run(executions, clearing, run=run, settings=settings,
                               checkpoints=batch.checkpoints, ingestion_status=batch.status,
                               advance_checkpoints=start is None)
    except Exception as exc:
        logger.exception('FAILED | database | run_id=%s', run.run_id)
        try:
            record_failure(run, RunStatus.DATABASE_FAILED, settings=settings, error=type(exc).__name__)
        except Exception:
            logger.exception('Could not persist failure metadata | run_id=%s', run.run_id)
        return RunStatus.DATABASE_FAILED.value
    status = batch.status.value
    if not persist_only:
        result = dispatch_breaks(settings, client=dispatch_client)
        status = update_dispatch_status(settings.db_path, run.run_id, result)
    logger.info('%s | run_id=%s | snapshot_id=%s | duration=%.2fs',
                status, run.run_id, snapshot, time.perf_counter()-started)
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--persist-only', action='store_true')
    mode.add_argument('--dispatch-only', action='store_true')
    parser.add_argument('--run-id', help='Reuse the same ID when retrying the same logical run')
    parser.add_argument('--start', help='UTC replay/backfill start; does not advance live checkpoints')
    parser.add_argument('--end', help='UTC end (default current time)')
    parser.add_argument('--symbols', help='Comma-separated source symbols')
    parser.add_argument('--db-path', type=Path)
    args = parser.parse_args(argv)
    if args.dispatch_only and not args.run_id:
        parser.error('--dispatch-only requires --run-id')
    load_dotenv()
    settings = Settings.from_env()
    if args.db_path:
        settings = replace(settings, db_path=args.db_path)
    if args.symbols:
        settings = replace(settings, symbols=tuple(s.strip().upper() for s in args.symbols.split(',')))
    run = RunContext(run_id=args.run_id) if args.run_id else RunContext()
    if args.dispatch_only:
        status = update_dispatch_status(settings.db_path, run.run_id, dispatch_breaks(settings))
    else:
        status = execute_pipeline(settings, run, start=args.start, end=args.end, persist_only=args.persist_only)
    print(f'TradeOps {status} | run_id={run.run_id}')
    return 0 if status in HEALTHY else 1


if __name__ == '__main__':
    raise SystemExit(main())
