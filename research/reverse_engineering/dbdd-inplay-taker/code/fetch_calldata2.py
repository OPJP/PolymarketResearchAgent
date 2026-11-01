"""Fetch and decode V2 calldata (catalog B1) for every wallet fill in the activity files, newest first.
Writes .cache/re/dbdd-inplay-taker/calldata/{taker,maker}_<chunk>.parquet."""
import sys, os, glob, time
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE
import pandas as pd
from calldata import fetch, rows_from

W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
os.makedirs(f'{CACHE}/calldata', exist_ok=True)
act = pd.concat([pd.read_parquet(f, columns=['timestamp', 'transactionHash']) for f in glob.glob(f'{CACHE}/activity/*.parquet')])
act = act.dropna().sort_values('timestamp', ascending=False)
txs = list(dict.fromkeys(act.transactionHash))
done = set()
for f in glob.glob(f'{CACHE}/calldata/taker_*.parquet'):
    done |= set(pd.read_parquet(f, columns=['tx']).tx)
txs = [t for t in txs if t not in done]
print('to fetch', len(txs), 'done', len(done), flush=True)
CH = 1000
n0 = len(glob.glob(f'{CACHE}/calldata/taker_*.parquet'))
t0 = time.time()
for i in range(0, len(txs), CH):
    part = txs[i:i + CH]
    m = fetch(part, batch=20)
    t, mk = rows_from(m, W)
    t.to_parquet(f'{CACHE}/calldata/taker_{n0:04d}.parquet')
    mk.to_parquet(f'{CACHE}/calldata/maker_{n0:04d}.parquet')
    n0 += 1
    print(time.strftime('%H:%M:%S'), i + len(part), '/', len(txs), 'got', len(m), round(time.time() - t0), 's', flush=True)
print('done', flush=True)
