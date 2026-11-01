"""Iteration 2 (local run): re-fetch the wallet's TRADE activity, clamped to development periods.

Pre-T0 development: [START, H). Post-T0: only the development 6-hour blocks from tools/sealed.py.
Rows are written per chunk to parquet (needed columns only), so memory stays small.
Fills of sealed UNITS inside development blocks (games that started in a sealed block) are dropped
later, once Gamma gameStartTime is known (filter_units in common code).
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE, ROOT
import pandas as pd
import sealed
from polyrea.adapters.polymarket import PolymarketData

W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
H = 1792713600
T0 = 1793404800
START = int(sys.argv[1]) if len(sys.argv) > 1 else 1790121600 - 2 * 86400   # 2026-09-21
pm = PolymarketData()
COLS = ['timestamp', 'type', 'conditionId', 'asset', 'side', 'price', 'size', 'usdcSize', 'outcome',
        'outcomeIndex', 'title', 'slug', 'eventSlug', 'transactionHash']
os.makedirs(f'{CACHE}/activity', exist_ok=True)


def grab(a, b, tag):
    out = f'{CACHE}/activity/{tag}.parquet'
    if os.path.exists(out):
        return
    rows, src, cov = pm.activity(W, start=a, end=b - 1, types=('TRADE',))
    df = pd.DataFrame(rows)
    if len(df):
        df = df[[c for c in COLS if c in df.columns]]
        df = df[(df.timestamp >= a) & (df.timestamp < b)]
    df.to_parquet(out)
    print(time.strftime('%H:%M:%S'), tag, len(df), cov.status, cov.detail, flush=True)


# pre-T0 development, in 3-day chunks
a = START
while a < H:
    b = min(a + 3 * 86400, H)
    grab(a, b, f'pre_{a}')
    a = b
# post-T0 development blocks only
now = int(time.time())
for (x, y) in sealed.intervals('dbdd-inplay-taker', T0, now, sealed=False):
    y = min(int(y), now - 120)
    if y > x:
        grab(int(x), int(y), f'dev_{int(x)}_{int(y)}')
print('done', flush=True)
