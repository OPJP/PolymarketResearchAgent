"""B1 for other takers in the same markets (the comparison population for X2 and C3).

Sample: in-play taker BUY prints by other wallets in the sampled BUILD/VALIDATE tapes (tapes2), seeded.
Fetch and decode their calldata, so the wallet's orders and quotes hit can be compared with other takers'.
Writes .cache/re/dbdd-inplay-taker/calldata_others/{taker,maker}.parquet and others_sample.parquet.
"""
import sys, os, glob, json, time
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE
import pandas as pd, numpy as np
from calldata import fetch, rows_from

W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
H = 1792713600
gm = json.load(open(f'{CACHE}/gamma2.json'))
os.makedirs(f'{CACHE}/calldata_others', exist_ok=True)
parts = []
for f in glob.glob(f'{CACHE}/tapes2/*.parquet'):
    c = os.path.basename(f)[:-8]
    m = gm.get(c) or {}
    u = m.get('unit_ts')
    if not u or u >= H:
        continue
    d = pd.read_parquet(f, columns=['timestamp', 'side', 'proxyWallet', 'transactionHash', 'price', 'size', 'asset', 'outcomeIndex'])
    d = d[(d.side == 'BUY') & (d.timestamp >= u) & (d.proxyWallet.str.lower() != W)]
    if len(d):
        d['cid'] = c
        parts.append(d)
P = pd.concat(parts, ignore_index=True)
rng = np.random.default_rng(11)
S = P.iloc[rng.permutation(len(P))[:N]].copy()
S.to_parquet(f'{CACHE}/calldata_others/others_sample.parquet')
print('population', len(P), 'sample', len(S), flush=True)
txs = list(dict.fromkeys(S.transactionHash))
t0 = time.time()
TT, MM = [], []
for i in range(0, len(txs), 1000):
    m = fetch(txs[i:i + 1000], batch=20)
    t, mk = rows_from(m, W)
    TT.append(t)
    MM.append(mk)
    print(time.strftime('%H:%M:%S'), i + 1000, len(m), round(time.time() - t0), 's', flush=True)
pd.concat(TT).to_parquet(f'{CACHE}/calldata_others/taker.parquet')
pd.concat(MM).to_parquet(f'{CACHE}/calldata_others/maker.parquet')
print('done', flush=True)
