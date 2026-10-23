
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import random
from datetime import timedelta

import numpy as np
import pandas as pd


INPUT_PATH = "data/processed/executions.csv"
OUTPUT_PATH = "data/processed/clearing.csv"




def generate_clearing(df):
    """Generate reproducible demo evidence per trade; persist once, never reroll it.

    ~4.2% of identities have a controlled break. Source updates can later correct
    these records; overlap replay cannot change their simulated attributes.
    """
    from src.contracts import CLEARING, clearing_frame, stable_id
    records = []
    for trade in df.to_dict('records'):
        seed = int(stable_id('SCENARIO', trade['trade_id']).split('-')[1][:16], 16)
        scenario = seed % 1000
        if 34 <= scenario < 39:
            continue
        record = {key: trade.get(key) for key in ['trade_id', 'symbol', 'side', 'quantity',
                                                  'price', 'currency', 'account', 'venue']}
        record.update(source='TRADEOPS_SIMULATOR', record_source='CLEARING',
                      clearing_id=stable_id('CLR', trade['trade_id']), clearing_status='CONFIRMED',
                      clearing_timestamp=pd.Timestamp(trade['execution_timestamp']) + pd.Timedelta(seconds=120 + seed % 360))
        if scenario < 8:
            record['quantity'] += 1 + seed % 99
        elif scenario < 14:
            record['price'] += 0.5
        elif scenario < 19:
            record['account'] = 'ACC-9999'
        elif scenario < 22:
            record['currency'] = 'EUR'
        elif scenario < 25:
            record['side'] = 'SELL' if record['side'] == 'BUY' else 'BUY'
        elif scenario < 29:
            record['clearing_status'] = 'FAILED'
        elif scenario < 34:
            record['clearing_timestamp'] += pd.Timedelta(minutes=30)
        records.append(record)
        if 39 <= scenario < 42:
            duplicate = dict(record, clearing_id=stable_id('CLR-DUP', trade['trade_id']))
            duplicate['clearing_timestamp'] += pd.Timedelta(seconds=1)
            records.append(duplicate)
    return clearing_frame(pd.DataFrame(records, columns=CLEARING))



if __name__ == "__main__":

    executions = pd.read_csv(INPUT_PATH)

    clearing = generate_clearing(
        executions
    )

    os.makedirs(
        "data/processed",
        exist_ok=True,
    )

    clearing.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print("TradeOps clearing generation complete")
    print("-" * 45)

    print()
    print("Sample clearing records:")
    print(clearing.head())

    print()
    print(f"Execution rows: {len(executions)}")
    print(f"Clearing rows: {len(clearing)}")

    print()
    print("Clearing columns:")
    print(clearing.columns.tolist())

    print()
    print("Clearing status counts:")
    print(
        clearing[
            "clearing_status"
        ].value_counts()
    )

    print()
    print("Saved to:")
    print(OUTPUT_PATH)