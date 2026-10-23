from dataclasses import replace
import pandas as pd
import pytest
import requests
from src.contracts import RunStatus, RunContext
from src.ingestion import fetch_trades, ingest, read_checkpoints
from src.load_database import persist_run
from src.cleaning import clean_trades
from conftest import Client, Response


def api_trade(now, identifier='1'):
    return dict(i=identifier, t=now.isoformat(), p=100, s=10, x='V')


def test_pagination_consumes_every_page(settings, now):
    client = Client([Response({'trades': [api_trade(now)], 'next_page_token': 'next'}),
                     Response({'trades': [api_trade(now, '2')], 'next_page_token': None})])
    frame = fetch_trades('AAPL', now-pd.Timedelta(minutes=1), now, settings=settings, client=client)
    assert len(frame) == 2 and len(client.calls) == 2
    assert client.calls[1][1]['params']['page_token'] == 'next'


def test_repeated_page_token_fails_instead_of_truncating(settings, now):
    client = Client([Response({'trades': [], 'next_page_token': 'same'})] * 2)
    with pytest.raises(ValueError, match='Repeated'):
        fetch_trades('AAPL', now, now, settings=settings, client=client)


def test_checkpoint_only_advances_on_persistence(settings, now, execution, clearing, run):
    batch = ingest(settings, now=now, client=Client([Response({'trades': []})]))
    assert read_checkpoints(settings.db_path, settings.source) == {}
    persist_run(execution, clearing, settings=settings, run=run, now=now, checkpoints=batch.checkpoints)
    assert read_checkpoints(settings.db_path, settings.source) == {'AAPL': now}
    later = now + pd.Timedelta(minutes=30)
    client = Client([Response({'trades': []})])
    ingest(settings, now=later, client=client)
    assert pd.Timestamp(client.calls[0][1]['params']['start']) == now-pd.Timedelta(minutes=2)


def test_failed_request_does_not_advance_checkpoint(settings, now, execution, clearing, run):
    persist_run(execution, clearing, settings=settings, run=run, now=now, checkpoints={'AAPL': now})
    batch = ingest(settings, now=now+pd.Timedelta(hours=1), client=Client([requests.ConnectionError('offline')]))
    assert batch.status == RunStatus.INGESTION_FAILED and batch.errors
    assert read_checkpoints(settings.db_path, settings.source)['AAPL'] == now


def test_partial_symbol_failure_is_explicit(settings, now):
    settings = replace(settings, symbols=('AAPL', 'MSFT'))
    batch = ingest(settings, now=now, client=Client([Response({'trades': []}), requests.Timeout('offline')]))
    assert batch.status == RunStatus.PARTIAL_INGESTION
    assert list(batch.errors) == ['MSFT']


def test_empty_success_is_not_an_outage(settings, now):
    assert ingest(settings, now=now, client=Client([Response({'trades': []})])).status == RunStatus.SUCCESS_NO_DATA


def test_page_failure_discards_symbol_checkpoint(settings, now):
    batch = ingest(settings, now=now, client=Client([
        Response({'trades': [api_trade(now)], 'next_page_token': 'next'}), requests.Timeout('offline')]))
    assert batch.status == RunStatus.INGESTION_FAILED
    assert batch.checkpoints == {} and batch.trades.empty


def test_backlog_catches_up_without_skipping(settings, now, execution, clearing, run):
    old = now-pd.Timedelta(days=3)
    persist_run(execution, clearing, settings=settings, run=run, now=old, checkpoints={'AAPL': old})
    batch = ingest(settings, now=now, client=Client([Response({'trades': []})]))
    assert batch.checkpoints['AAPL'] == old-pd.Timedelta(minutes=2)+pd.Timedelta(hours=24)
    assert batch.checkpoints['AAPL'] < now


def test_overlap_records_clean_to_one_identity(settings, now):
    client = Client([Response({'trades': [api_trade(now), api_trade(now)]})])
    batch = ingest(settings, now=now, client=client)
    assert len(clean_trades(batch.trades)) == 1


def test_replay_does_not_move_checkpoint(settings, now, execution, clearing, run):
    persist_run(execution, clearing, settings=settings, run=run, now=now, checkpoints={'AAPL': now})
    persist_run(execution, clearing, settings=settings, run=RunContext('backfill', now), now=now,
                checkpoints={'AAPL': now+pd.Timedelta(days=1)}, advance_checkpoints=False)
    assert read_checkpoints(settings.db_path, settings.source)['AAPL'] == now
