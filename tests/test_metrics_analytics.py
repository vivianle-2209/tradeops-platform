import duckdb
import pandas as pd
import pytest
from src.analytics import history_runs, history_trend, history_observations, history_severity
from src.contracts import RunContext
from src.load_database import persist_run
from src.reconciliation import reconcile_trades, create_break_table
from src.metrics import total_exposure, exposure_by_group


def test_price_only_impact_is_nonzero(execution, clearing):
    results = reconcile_trades(execution, clearing.assign(price=101.))
    breaks = create_break_table(results)
    assert breaks.exception_impact.iloc[0] == 10.
    assert results.affected_notional.iloc[0] == 10.


def test_multiple_exceptions_do_not_duplicate_trade_exposure(execution, high):
    breaks = create_break_table(reconcile_trades(execution, high.assign(account='DIFFERENT')))
    assert len(breaks) == 2
    assert total_exposure(breaks) == breaks.affected_notional.max()
    assert exposure_by_group(breaks, 'exception_type').sum() == total_exposure(breaks)


def test_orphan_keeps_clearing_evidence_without_fabricating_execution(execution, clearing):
    results = reconcile_trades(execution.iloc[:0], clearing)
    breaks = create_break_table(results)
    row = breaks.iloc[0]
    assert row.symbol == 'AAPL' and row.symbol_clear == 'AAPL' and pd.isna(row.symbol_exec)
    assert row.account_clear == clearing.account.iloc[0] and pd.isna(row.account_exec)
    assert row.trade_exposure == 1000 and row.exception_impact == 1000


def test_history_scope_applies_to_summary_trend_severity_and_detail(settings, execution, high, run, now):
    other = execution.assign(trade_id='other', symbol='MSFT', market_trade_id='other')
    other_clearing = high.assign(trade_id='other', symbol='MSFT', clearing_id='other', quantity=10)
    persist_run(pd.concat([execution, other]), pd.concat([high, other_clearing]),
                settings=settings, run=run, now=now)
    with duckdb.connect(str(settings.db_path), read_only=True) as con:
        summary = history_runs(con, symbols=('AAPL',))
        assert summary.total_trades.iloc[0] == 1 and summary.broken_trades.iloc[0] == 1
        trend = history_trend(con, symbols=('MSFT',), metric='Break Rate')
        assert trend.break_rate.iloc[0] == 0
        recon, breaks = history_observations(con, run.snapshot_id, ('MSFT',))
        assert len(recon) == 1 and breaks.empty
        assert history_severity(con, symbols=('MSFT',)).empty


def test_history_local_dates_and_weighted_break_rate(settings, execution, high, clearing, run, now):
    persist_run(execution, high, settings=settings, run=run, now=now)
    other = execution.assign(trade_id='second', market_trade_id='second')
    persist_run(pd.concat([execution, other]), pd.concat([clearing, clearing.assign(trade_id='second', clearing_id='second')]),
                settings=settings, run=RunContext('second', now), now=now+pd.Timedelta(minutes=30))
    with duckdb.connect(str(settings.db_path), read_only=True) as con:
        trend = history_trend(con, start=now.date(), end=now.date(), metric='Break Rate', timezone_name='UTC')
        assert trend.break_rate.iloc[0] == pytest.approx(100/3)
        assert history_runs(con, start=pd.Timestamp('2026-10-21').date(), timezone_name='UTC').empty


@pytest.mark.parametrize('granularity', ['Daily', 'Hourly', '30-minute', 'Intraday'])
def test_history_granularity(settings, execution, high, run, now, granularity):
    persist_run(execution, high, settings=settings, run=run, now=now)
    with duckdb.connect(str(settings.db_path), read_only=True) as con:
        assert len(history_trend(con, metric='Trades', granularity=granularity)) == 1
