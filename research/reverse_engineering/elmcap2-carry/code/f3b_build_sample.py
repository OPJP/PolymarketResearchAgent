"""F3b: BUILD prices for a fitting sample: every BUILD-universe market the wallet traded + a fixed random sample
(seed 7) of 2,000 other BUILD-universe markets (negatives subsampled to save requests; VALIDATE uses the full universe)."""
import sys, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code')
import numpy as np, pandas as pd
from universe import prices
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
u = pd.read_parquet(OUT + 'universe_meta_B.parquet'); u = u[~u.is_sport & ~u.is_updown]
b = pd.read_parquet(OUT + 'buys.parquet')
traded = u.conditionId.isin(b.conditionId.unique())
rest = u[~traded].sample(n=min(2000, (~traded).sum()), random_state=7)
s = pd.concat([u[traded], rest])
s['sample_w'] = np.where(s.conditionId.isin(u[traded].conditionId), 1.0, (~traded).sum() / len(rest))
print('BUILD universe', len(u), 'traded', int(traded.sum()), 'sample', len(s), flush=True)
t0 = time.time(); P = prices(s); print('prices done', len(P), round(time.time() - t0), flush=True)
s.to_parquet(OUT + 'universe_meta_Bs.parquet'); pd.to_pickle(P, OUT + 'universe_prices_Bs.pkl')
