"""A3: build cells for BUILD/VALIDATE, train behaviour-cloning presence models on BUILD, score on VALIDATE."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code')
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from cells import build_cells, FAMS
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
RES = '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/'
b = pd.read_parquet(OUT + 'buys.parquet')
def cells_for(tag):
    u = pd.read_parquet(OUT + f'universe_meta_{tag}.parquet')
    if 'is_sport' in u: u = u[~u.is_sport & ~u.is_updown]
    P = pd.read_pickle(OUT + f'universe_prices_{tag}.pkl')
    bb = b[b.conditionId.isin(u.conditionId)]
    d = build_cells(u, P, bb)
    d.to_parquet(OUT + f'cells_{tag}.parquet')
    return d
if __name__ == '__main__':
    tags = sys.argv[1:] or ['B', 'V']
    for tg in tags:
        d = cells_for(tg)
        print(tg, 'cells', len(d), 'markets', d.cid.nunique(), 'pos cells', int(d.y.sum()), 'pos markets', d[d.y == 1].cid.nunique(), 'wallet usd in cells', round(d.usd.sum()))
