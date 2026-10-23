"""Deterministic reconciliation with complete two-sided evidence."""

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from src.config import PRICE_TOLERANCE, LATE_CLEARING_SECONDS
from src.contracts import (RECONCILIATION, BREAK, execution_frame, clearing_frame,
                           normalize_frame, stable_id)


def reconcile_trades(executions, clearing):
    executions = execution_frame(executions)
    clearing = clearing_frame(clearing)
    by_trade = {key: frame for key, frame in clearing.groupby('trade_id')}
    execution_map = executions.set_index('trade_id').to_dict('index')
    rows = []
    for trade_id in sorted(set(execution_map) | set(by_trade)):
        execution = execution_map.get(trade_id)
        records = by_trade.get(trade_id)
        canonical = None if records is None else records.sort_values(
            ['clearing_timestamp', 'clearing_id']).iloc[0].to_dict()
        row = dict.fromkeys(RECONCILIATION)
        row.update(trade_id=trade_id, execution_present=execution is not None,
                   clearing_present=canonical is not None,
                   clearing_record_count=0 if records is None else len(records))
        for side, record in [('exec', execution), ('clear', canonical)]:
            record = record or {}
            for name in ['symbol', 'side', 'quantity', 'price', 'currency', 'account', 'venue', 'source']:
                row[f'{name}_{side}'] = record.get(name)
        # Canonical symbol is a separate display/scope field. Evidence columns stay null.
        row['symbol'] = (execution or canonical)['symbol']
        row['venue'] = (execution or canonical).get('venue')
        for name in ['market_trade_id', 'order_id', 'trader_id', 'execution_timestamp']:
            row[name] = (execution or {}).get(name)
        for name in ['clearing_id', 'clearing_timestamp', 'clearing_status']:
            row[name] = (canonical or {}).get(name)
        en = None if execution is None else float(execution['quantity'] * execution['price'])
        cn = None if canonical is None else float(canonical['quantity'] * canonical['price'])
        row['execution_notional'], row['clearing_notional'] = en, cn
        row['trade_exposure'] = max(value for value in [en, cn] if value is not None)
        exceptions = []
        if execution is None:
            exceptions.append('MISSING_EXECUTION_RECORD')
        elif canonical is None:
            exceptions.append('MISSING_CLEARING_RECORD')
        else:
            row['quantity_difference'] = execution['quantity'] - canonical['quantity']
            row['price_difference'] = execution['price'] - canonical['price']
            row['clearing_latency_seconds'] = (canonical['clearing_timestamp'] - execution['execution_timestamp']).total_seconds()
            if len(records) > 1:
                exceptions.append('DUPLICATE_CLEARING_RECORD')
            if row['quantity_difference'] != 0:
                exceptions.append('QUANTITY_MISMATCH')
            if abs(row['price_difference']) > PRICE_TOLERANCE:
                exceptions.append('PRICE_MISMATCH')
            for name in ['side', 'account', 'currency']:
                left, right = execution.get(name), canonical.get(name)
                if pd.notna(left) and pd.notna(right) and left != right:
                    exceptions.append(name.upper() + '_MISMATCH')
            if canonical['clearing_status'] == 'FAILED':
                exceptions.append('SETTLEMENT_FAILED')
            if row['clearing_latency_seconds'] > LATE_CLEARING_SECONDS:
                exceptions.append('LATE_CLEARING')
        impacts = [exception_impact(row, kind) for kind in exceptions]
        # Trade-level risk proxy: maximum exception impact, never sum duplicated evidence.
        row['affected_notional'] = max(impacts, default=0.)
        row['break_count'] = len(exceptions)
        row['exception_types'] = '|'.join(exceptions) if exceptions else 'MATCHED'
        row['reconciliation_status'] = 'BREAK' if exceptions else 'MATCHED'
        rows.append(row)
    return normalize_frame(pd.DataFrame(rows, columns=RECONCILIATION), RECONCILIATION,
                           required=('trade_id', 'symbol', 'reconciliation_status'), key=('trade_id',))


def exception_impact(row, kind):
    if kind == 'QUANTITY_MISMATCH':
        return abs(row['quantity_difference']) * row['price_exec']
    if kind == 'PRICE_MISMATCH':
        return abs(row['price_difference']) * row['quantity_exec']
    # Missing side, status, duplication, ownership, direction, currency and latency
    # expose the full known gross trade notional. This is a risk proxy, not P&L.
    return row['trade_exposure']


def create_break_table(results):
    records = []
    for result in results.to_dict('records'):
        if result['reconciliation_status'] != 'BREAK':
            continue
        for kind in result['exception_types'].split('|'):
            key = result['trade_id'] + ':' + kind
            row = dict(result, dedup_key=key, break_id=stable_id('BRK', key),
                       exception_type=kind, exception_impact=exception_impact(result, kind), break_status='OPEN')
            records.append(row)
    return normalize_frame(pd.DataFrame(records, columns=BREAK), BREAK,
                           required=('trade_id', 'break_id', 'dedup_key', 'exception_type'), key=('dedup_key',))


def correction_proven(result, kind):
    """Absence is never correction. Require present, known counterpart evidence."""
    if result is None:
        return False
    if kind == 'MISSING_CLEARING_RECORD':
        return bool(result['clearing_present'])
    if kind == 'MISSING_EXECUTION_RECORD':
        return bool(result['execution_present'])
    if not (result['execution_present'] and result['clearing_present']):
        return False
    if kind in str(result['exception_types']).split('|'):
        return False
    if kind == 'SETTLEMENT_FAILED' and result['clearing_status'] != 'CONFIRMED':
        return False
    field = {'ACCOUNT_MISMATCH': 'account', 'CURRENCY_MISMATCH': 'currency',
             'SIDE_MISMATCH': 'side'}.get(kind)
    if field and any(pd.isna(result[f'{field}_{side}']) for side in ['exec', 'clear']):
        return False
    return True


if __name__ == '__main__':
    from pathlib import Path
    results = reconcile_trades(pd.read_csv('data/processed/executions.csv'),
                               pd.read_csv('data/processed/clearing.csv'))
    Path('data/processed').mkdir(parents=True, exist_ok=True)
    results.to_csv('data/processed/reconciliation_results.csv', index=False)
    create_break_table(results).to_csv('data/processed/trade_breaks.csv', index=False)
