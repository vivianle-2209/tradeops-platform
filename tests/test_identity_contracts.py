from dataclasses import replace
import pandas as pd
import pytest
from src.cleaning import clean_trades
from src.enrich_executions import enrich_executions
from src.generate_clearing import generate_clearing
from src.contracts import RunContext, execution_frame


def test_identity_stable_across_runs_and_batch_order(raw):
    first = clean_trades(raw)
    other = raw.assign(i="456")
    second = clean_trades(pd.concat([other, raw], ignore_index=True))
    assert first.trade_id.iloc[0] == second.loc[second.market_trade_id.eq("123"), "trade_id"].iloc[0]
    assert second.trade_id.nunique() == 2
    assert RunContext().run_id != RunContext().run_id
    assert RunContext("same").snapshot_id == RunContext("same").snapshot_id


@pytest.mark.parametrize("field,value", [("i", "124"), ("symbol", "MSFT"), ("x", "OTHER"),
                                        ("t", "2026-10-21T14:00:00Z"), ("source", "OTHER_FEED")])
def test_identity_scope_does_not_collide(raw, field, value):
    assert clean_trades(raw).trade_id.iloc[0] != clean_trades(raw.assign(**{field: value})).trade_id.iloc[0]


def test_overlap_deduplicates_source_identity(raw):
    assert len(clean_trades(pd.concat([raw, raw], ignore_index=True))) == 1


def test_synthetic_attributes_replay_without_batch_dependence(raw):
    small = enrich_executions(clean_trades(raw))
    large = enrich_executions(clean_trades(pd.concat([raw.assign(i="999"), raw], ignore_index=True)))
    pd.testing.assert_frame_equal(small.reset_index(drop=True), large[large.trade_id.eq(small.trade_id.iloc[0])].reset_index(drop=True))
    pd.testing.assert_frame_equal(generate_clearing(small), generate_clearing(small))


@pytest.mark.parametrize("field,value", [("p", 0), ("s", -1), ("t", None), ("symbol", None)])
def test_invalid_source_records_are_rejected(raw, field, value):
    with pytest.raises(ValueError):
        clean_trades(raw.assign(**{field: value}))


def test_contract_rejects_duplicate_keys_and_nonfinite(execution):
    with pytest.raises(ValueError):
        execution_frame(pd.concat([execution, execution]))
    with pytest.raises(ValueError):
        execution_frame(execution.assign(price=float("inf")))
