"""Checkpointed, paginated Alpaca ingestion. Fetching never advances checkpoints."""

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataclasses import dataclass, field
from pathlib import Path
import duckdb
import pandas as pd
import requests
from src.config import Settings
from src.contracts import RunStatus, utc, utc_now

BASE_URL = 'https://data.alpaca.markets/v2/stocks'


@dataclass
class IngestionBatch:
    trades: pd.DataFrame
    status: RunStatus
    checkpoints: dict[str, pd.Timestamp] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    windows: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = field(default_factory=dict)


def read_checkpoints(db_path, source):
    if not Path(db_path).exists():
        return {}
    with duckdb.connect(str(db_path), read_only=True) as con:
        exists = con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='ingestion_checkpoints'").fetchone()[0]
        if not exists:
            return {}
        return {symbol: utc(position) for symbol, position in con.execute(
            'SELECT symbol, position FROM ingestion_checkpoints WHERE source = ?', [source]).fetchall()}


def fetch_trades(symbol, start, end, limit=None, *, settings=None, client=None):
    settings = settings or Settings.from_env()
    client = client or requests
    if not settings.api_key or not settings.secret_key:
        raise ValueError('Alpaca credentials are not configured')
    params = dict(start=utc(start).isoformat(), end=utc(end).isoformat(),
                  limit=limit or settings.page_limit, feed='iex', sort='asc')
    headers = {'APCA-API-KEY-ID': settings.api_key, 'APCA-API-SECRET-KEY': settings.secret_key}
    records, seen_tokens = [], set()
    while True:
        response = client.get(f'{BASE_URL}/{symbol}/trades', headers=headers,
                              params=dict(params), timeout=settings.request_timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get('trades'), (list, type(None))):
            raise ValueError('Malformed Alpaca trade response')
        if 'trades' not in payload:
            raise ValueError('Alpaca response missing trades')
        for record in payload.get('trades') or []:
            if not isinstance(record, dict) or any(key not in record or record[key] is None for key in ['i', 't', 'p', 's', 'x']):
                raise ValueError('Alpaca record missing identity/economic fields')
            stamp = utc(record['t'])
            if not utc(start) <= stamp <= utc(end):
                raise ValueError('Alpaca returned a record outside the requested interval')
            records.append(dict(record, i=str(record['i']), symbol=symbol, source=settings.source))
        token = payload.get('next_page_token')
        if not token:
            break
        if token in seen_tokens:
            raise ValueError('Repeated pagination token; refusing incomplete window')
        seen_tokens.add(token)
        params['page_token'] = token
    return pd.DataFrame(records)


def ingest(settings=None, *, now=None, start=None, end=None, client=None):
    settings = settings or Settings.from_env()
    now = utc(now) if now is not None else utc_now()
    end = utc(end) if end is not None else now
    checkpoints = read_checkpoints(settings.db_path, settings.source)
    frames, positions, errors, windows = [], {}, {}, {}
    explicit_start = utc(start) if start is not None else None
    for symbol in settings.symbols:
        position = checkpoints.get(symbol)
        begin = explicit_start if explicit_start is not None else (
            position - pd.Timedelta(minutes=settings.overlap_minutes) if position is not None
            else end - pd.Timedelta(minutes=settings.initial_lookback_minutes))
        stop = end if explicit_start is not None else min(end, begin + pd.Timedelta(hours=settings.max_window_hours))
        if stop < begin:
            raise ValueError('Ingestion end precedes start/checkpoint')
        windows[symbol] = (begin, stop)
        try:
            frame = fetch_trades(symbol, begin, stop, settings=settings, client=client)
            if not frame.empty:
                frames.append(frame)
            positions[symbol] = stop
        except (requests.RequestException, ValueError, TypeError) as exc:
            errors[symbol] = f'{type(exc).__name__}: {exc}'
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if errors:
        status = RunStatus.INGESTION_FAILED if len(errors) == len(settings.symbols) else RunStatus.PARTIAL_INGESTION
    else:
        status = RunStatus.SUCCESS_NO_DATA if combined.empty else RunStatus.SUCCESS
    # Any failed symbol rejects the entire batch at the persistence boundary.
    return IngestionBatch(combined, status, positions, errors, windows)


if __name__ == '__main__':
    raise SystemExit('Use python run_pipeline.py; checkpoints commit with operational state.')
