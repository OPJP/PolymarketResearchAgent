"""Public taker tapes (data-api takerOnly) for a reproducible sample of development markets the wallet traded.
Sample: every market of the post-T0 development units + a seeded random sample of VALIDATE and BUILD units.
Writes .cache/re/dbdd-inplay-taker/tapes2/<cid>.parquet (needed columns only)."""
import sys, os, glob, json, time
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE
import pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.polymarket import PolymarketData
import sealed

KEY = 'dbdd-inplay-taker'
H, T0 = 1792713600, 1793404800
VAL = (1791849600, 1792713600)
BUILD = (1790121600, 1791849600)
N_VAL = int(sys.argv[1]) if len(sys.argv) > 1 else 700
N_BUILD = int(sys.argv[2]) if len(sys.argv) > 2 else 300
pm = PolymarketData()
gm = json.load(open(f'{CACHE}/gamma2.json'))
act = pd.concat([pd.read_parquet(f, columns=['timestamp', 'conditionId']) for f in glob.glob(f'{CACHE}/activity/*.parquet')])
first = act.groupby('conditionId').timestamp.min()
last = act.groupby('conditionId').timestamp.max()
os.makedirs(f'{CACHE}/tapes2', exist_ok=True)
rows = []
for c in first.index:
    m = gm.get(c)
    if not m or m.get('sealed', 1):
        continue
    rows.append((c, float(m['unit_ts'])))
u = pd.DataFrame(rows, columns=['cid', 'unit_ts'])
rng = np.random.default_rng(20261101)
post = u[u.unit_ts >= T0]
val = u[(u.unit_ts >= VAL[0]) & (u.unit_ts < VAL[1])]
bld = u[(u.unit_ts >= BUILD[0]) & (u.unit_ts < BUILD[1])]
pick = pd.concat([post, val.iloc[rng.permutation(len(val))[:N_VAL]], bld.iloc[rng.permutation(len(bld))[:N_BUILD]]])  # same seed: a larger N extends the same sample
pick.to_csv(f'{CACHE}/tapes2_sample.csv', index=False)
print('post', len(post), 'val', min(N_VAL, len(val)), 'of', len(val), 'build', min(N_BUILD, len(bld)), 'of', len(bld), flush=True)
COLS = ['timestamp', 'side', 'asset', 'price', 'size', 'proxyWallet', 'outcomeIndex', 'transactionHash']


def job(r):
    c, ref = r.cid, r.unit_ts
    out = f'{CACHE}/tapes2/{c}.parquet'
    if os.path.exists(out):
        return 0
    st = int(min(ref - 3600, first[c] - 600))
    en = int(max(ref + 8 * 3600, last[c] + 600))
    if ref < H:
        en = min(en, H - 1)
    else:
        # post-T0 development unit: clamp to the end of its development block (records after it are sealed)
        b0, b1 = sealed.block_bounds(ref)
        en = min(en, b1 - 1)
    try:
        rr, src, cov = pm.market_trades(c, start=st, end=en, taker_only=True)
    except Exception as e:
        return -1
    d = pd.DataFrame(rr)
    if len(d):
        d = d[[k for k in COLS if k in d.columns]]
    d.to_parquet(out)
    return len(d)


t0 = time.time()
with ThreadPoolExecutor(3) as ex:
    for i, n in enumerate(ex.map(job, pick.itertuples(index=False))):
        if i % 100 == 0:
            print(time.strftime('%H:%M:%S'), i, n, round(time.time() - t0), 's', flush=True)
print('done', flush=True)
