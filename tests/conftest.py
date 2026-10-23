"""Every test uses temporary state. Live HTTP and production DB writes are forbidden."""
from dataclasses import replace
from pathlib import Path
import socket
import sys

import duckdb
import pandas as pd
import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import Settings, PROJECT_ROOT
from src.cleaning import clean_trades
from src.enrich_executions import enrich_executions
from src.contracts import clearing_frame, RunContext


@pytest.fixture(autouse=True)
def prohibit_live_effects(monkeypatch):
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Live network calls are forbidden in tests")
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    original_connect = socket.socket.connect
    def local_ipc_only(sock, address):
        # Windows asyncio implements socketpair through loopback IPC. AppTest needs
        # that local pipe; every HTTP request and every external socket stays blocked.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        return forbidden(sock, address)
    monkeypatch.setattr(socket.socket, "connect", local_ipc_only)
    connect = duckdb.connect
    production = (PROJECT_ROOT / "data/tradeops.duckdb").resolve()
    def guarded_connect(database=":memory:", *args, **kwargs):
        if str(database) != ":memory:" and Path(database).resolve() == production:
            raise AssertionError("Tests must not open the production database")
        return connect(database, *args, **kwargs)
    monkeypatch.setattr(duckdb, "connect", guarded_connect)
    yield
    assert not attempts, "A test attempted live network access (even if a caller swallowed the error)"


@pytest.fixture
def settings(tmp_path):
    return replace(Settings(), db_path=tmp_path / "test.duckdb", symbols=("AAPL",),
                   api_key="test", secret_key="test", webhook_url="https://example.invalid/webhook")


@pytest.fixture
def now():
    return pd.Timestamp("2026-10-20T14:00:00Z")


@pytest.fixture
def raw(now):
    return pd.DataFrame([dict(i="123", symbol="AAPL", t=now.isoformat(), p=100., s=10, x="V", c=["@" ])])


@pytest.fixture
def execution(raw):
    return enrich_executions(clean_trades(raw))


@pytest.fixture
def clearing(execution, now):
    row = execution.iloc[0].to_dict()
    row.update(clearing_id="test-clearing", source="TEST_CLEARING", record_source="CLEARING",
               clearing_timestamp=now + pd.Timedelta(minutes=3), clearing_status="CONFIRMED")
    return clearing_frame(pd.DataFrame([row]))


@pytest.fixture
def high(clearing):
    result = clearing.copy()
    result["quantity"] = 20.
    return result


@pytest.fixture
def run(now):
    return RunContext("test-run", now)


def query(settings, sql, params=None):
    with duckdb.connect(str(settings.db_path), read_only=True) as con:
        return con.execute(sql, params or []).fetchall()


class Response:
    def __init__(self, payload=None, error=None):
        self.payload, self.error = payload, error
    def json(self):
        return self.payload
    def raise_for_status(self):
        if self.error:
            raise self.error


class Client:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
    post = get
