"""A6: distil the price/time behaviour clone into an explicit lookup rule fitted on BUILD (lag 3660):
score = smoothed BUILD presence rate in cells of (favourite-price bucket x hours-to-endDate bucket x hours-since-last-below-0.99 bucket)."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code')
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
import cells
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
b = pd.read_parquet(OUT + 'buys.parquet')
def mk(tag):
    cells.LAG = 3660
    u = pd.read_parquet(OUT + f'universe_meta_{tag}.parquet')
    if 'is_sport' in u: u = u[~u.is_sport & ~u.is_updown]
    P = pd.read_pickle(OUT + f'universe_prices_{tag}.pkl')
    d = cells.build_cells(u, P, b[b.conditionId.isin(u.conditionId)]); d['neg_risk'] = d.neg_risk.astype(int)
    return d
B = mk('Bs'); V = mk('V')
B.to_parquet(OUT + 'cells_Bs_lag3660.parquet'); V.to_parquet(OUT + 'cells_V_lag3660.parquet')
sw = pd.read_parquet(OUT + 'universe_meta_Bs.parquet').set_index('conditionId').sample_w
B['w'] = B.cid.map(sw).fillna(1.0).values
PFB = [0, 0.5, 0.8, 0.9, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 1.01]
HEB = [-1e9, -72, -24, 0, 24, 72, 168, 1e9]
H99 = [-1, 6, 24, 72, 1e9]
def keys(d):
    return (pd.cut(d.pf, PFB, right=False, labels=False).fillna(-1).astype(int).astype(str) + '_' + pd.cut(d.h_end, HEB, labels=False).fillna(-1).astype(int).astype(str) + '_' +
            pd.cut(d.hrs99, H99, labels=False).fillna(-1).astype(int).astype(str))
B['k'] = keys(B); V['k'] = keys(V)
g = B.groupby('k').apply(lambda x: pd.Series({'pos': (x.y * x.w).sum(), 'n': x.w.sum()}))
prior = (B.y * B.w).sum() / B.w.sum()
g['rate'] = (g.pos + 20 * prior) / (g.n + 20)   # shrink to prior with 20 pseudo-cells
table = g.rate.to_dict()
sv = V.k.map(table).fillna(prior).values; sb = B.k.map(table).fillna(prior).values
print('D1 lookup: BUILD AUC', round(float(roc_auc_score(B.y, sb, sample_weight=B.w)), 4), 'VALIDATE AUC', round(float(roc_auc_score(V.y, sv)), 4), 'cells in table', len(table))
json.dump(dict(PFB=PFB, HEB=HEB, H99=H99, prior=prior, table=table), open('/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code/rule_D1_table.json', 'w'))
# readable marginals on BUILD
B['pfb'] = pd.cut(B.pf, PFB, right=False); B['heb'] = pd.cut(B.h_end, HEB)
t = B.groupby(['pfb'], observed=True).apply(lambda x: (x.y * x.w).sum() / x.w.sum() * 100).round(3)
print('BUILD presence % by favourite price:', t.to_dict())
t2 = B[B.pf >= 0.99].groupby(['heb'], observed=True).apply(lambda x: (x.y * x.w).sum() / x.w.sum() * 100).round(3)
print('BUILD presence % by hours-to-endDate (pf>=0.99):', t2.to_dict())
