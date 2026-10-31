"""A9 (BUILD): the wallet's share of near-certain sell flow. For BUILD-sample markets with L2-predicted cells, fetch
taker rows (data-api) and compare the wallet's buy shares in predicted cells with all taker SELL shares of the
favourite printed at >= 0.99 in those cells."""
import sys, json, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code'); sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd, lightgbm as lgb
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.polymarket import PolymarketData
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'; CODE = '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code/'
F2 = ['pf', 'lpf', 'h_end', 'after_end', 'pf6', 'pf24', 'pf72', 'hrs99', 'hrs95', 'vol24']; CELL_THR = 0.0267238585457027
B = pd.read_parquet(OUT + 'cells_Bs_lag3660.parquet'); B['s'] = lgb.Booster(model_file=CODE + 'model_L2.txt').predict(B[F2])
u = pd.read_parquet(OUT + 'universe_meta_Bs.parquet').set_index('conditionId')
pred = B[B.s >= CELL_THR]; mk = sorted(pred.cid.unique())
print('BUILD markets with predicted cells', len(mk), 'traded among them', int(pred.groupby('cid').y.max().sum()), flush=True)
pm = PolymarketData()
def tape(c):
    r = u.loc[c]
    try:
        rows, _, _ = pm.market_trades(c, start=int(r.end_ts - 14 * 86400), end=int(min(r.closed_ts, r.end_ts + 14 * 86400)), taker_only=True, max_rows=20000)
        return c, pd.DataFrame(rows)
    except Exception:
        return c, None
t0 = time.time()
with ThreadPoolExecutor(6) as ex: T = dict(ex.map(tape, mk))
print('tapes', len(T), round(time.time() - t0), flush=True)
b = pd.read_parquet(OUT + 'buys.parquet')
out = []
for c in mk:
    tp = T.get(c); g = pred[pred.cid == c]
    if tp is None or not len(tp): continue
    toks = json.loads(u.loc[c].clobTokenIds)
    tp = tp[tp.side == 'SELL']; tp = tp.assign(price=tp.price.astype(float), sz=tp['size'].astype(float), ts=tp.timestamp.astype(int), tok=tp.asset.astype(str))
    flow = 0.0; wsh = 0.0
    wb = b[b.conditionId == c]
    for cell in g.itertuples():
        tok = str(toks[int(cell.fav)])
        f = tp[(tp.tok == tok) & (tp.price >= 0.99) & (tp.ts >= cell.t0) & (tp.ts < cell.t0 + 6 * 3600)]
        flow += f.sz.sum()
        w = wb[(wb.asset.astype(str) == tok) & (wb.timestamp >= cell.t0) & (wb.timestamp < cell.t0 + 6 * 3600) & (wb.price >= 0.99)]
        wsh += w['size'].astype(float).sum()
    out.append((c, int(g.y.max()), flow, wsh))
o = pd.DataFrame(out, columns=['cid', 'traded', 'flow99', 'wallet99'])
o['share'] = o.wallet99 / o.flow99.replace(0, np.nan)
tr = o[o.traded == 1]; nt = o[o.traded == 0]
res = dict(markets=len(o), traded=len(tr), share_pooled_traded=round(float(tr.wallet99.sum() / max(1, tr.flow99.sum())), 3), share_median_traded=round(float(tr.share.median()), 3),
           flow99_traded_total=round(float(tr.flow99.sum())), flow99_untraded_total=round(float(nt.flow99.sum())), untraded_with_flow=int((nt.flow99 > 0).sum()), untraded=len(nt),
           median_flow99_traded=round(float(tr.flow99.median())), median_flow99_untraded=round(float(nt.flow99.median())))
print(res)
json.dump(res, open('/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/results_iter1_share_build.json', 'w'), indent=1)
