from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from src.contracts import RunContext
from src.load_database import persist_run
from src.storage import transaction


def dashboard_data(settings, monkeypatch):
    monkeypatch.syspath_prepend(str(Path('dashboard').resolve()))
    from tradeops_ui import data
    monkeypatch.setattr(data, 'DB_PATH', settings.db_path)
    data.clear_caches()
    return data


def test_empty_dashboard_renders_without_touching_real_database(settings, monkeypatch):
    with transaction(settings.db_path):
        pass
    dashboard_data(settings, monkeypatch)
    app = AppTest.from_file(Path('dashboard/app.py').resolve(), default_timeout=30).run()
    assert not app.exception, [e.message for e in app.exception]


def test_historical_page_renders_scoped_data(settings, execution, high, run, now, monkeypatch):
    persist_run(execution, high, settings=settings, run=run, now=now)
    data = dashboard_data(settings, monkeypatch)
    app = AppTest.from_file(Path('dashboard/app_pages/historical_operations.py').resolve(), default_timeout=30).run()
    assert not app.exception, [e.message for e in app.exception]
    assert any(metric.label == 'Pipeline Runs' and metric.value == '1' for metric in app.metric)


def test_current_dashboard_shared_sla_and_exposure(settings, execution, high, run, now, monkeypatch):
    persist_run(execution, high, settings=settings, run=run, now=now)
    data = dashboard_data(settings, monkeypatch)
    loaded = data.load_tables(settings.db_path.stat().st_mtime)
    kpis = data.compute_kpis(loaded['reconciliation'], loaded['breaks'])
    assert kpis['affected'] == 1000 and kpis['open'] == 1
    live = data.apply_live_sla(loaded['breaks'], now+pd.Timedelta(hours=1))
    assert live.sla_status.iloc[0] == 'BREACHED'
