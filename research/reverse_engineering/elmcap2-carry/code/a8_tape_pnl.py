"""A8: strict maker-fill PnL for the frozen L2 rule on VALIDATE. In every predicted cell (score >= CELL_THR) the rule
rests an unlimited bid for the PIT favourite at price_rule(pf); it is filled by taker SELL prints of that token at
price <= bid stamped >= t0 + 2 s and < t0 + 6 h (data-api taker rows). PnL settles at outcomePrices.
Per-market rule PnL vs the wallet's per-market PnL (its buys in universe cells)."""
import sys, json, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code')
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd, lightgbm as lgb
from concurrent.futures import ThreadPoolExecutor
from scipy.stats import spearmanr, pearsonr
from metrics import price_rule
from polyrea.adapters.polymarket import PolymarketData
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'; CODE = '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code/'
F2 = ['pf', 'lpf', 'h_end', 'after_end', 'pf6', 'pf24', 'pf72', 'hrs99', 'hrs95', 'vol24']
CELL_THR = 0.0267238585457027
V = pd.read_parquet(OUT + 'cells_V_lag3660.parquet')
V['s'] = lgb.Booster(model_file=CODE + 'model_L2.txt').predict(V[F2])
u = pd.read_parquet(OUT + 'universe_meta_V.parquet').set_index('conditionId')
pred = V[V.s >= CELL_THR]
mk = sorted(set(pred.cid) | set(V[V.y == 1].cid))
print('markets to tape', len(mk), flush=True)
pm = PolymarketData()
def tape(c):
    r = u.loc[c]
    try:
        rows, _, cov = pm.market_trades(c, start=int(r.end_ts - 14 * 86400), end=int(min(r.closed_ts, r.end_ts + 14 * 86400)), taker_only=True, max_rows=20000)
    except Exception as e:
        return c, None
    return c, pd.DataFrame(rows)
t0 = time.time(); T = {}
with ThreadPoolExecutor(6) as ex:
    for i, (c, d) in enumerate(ex.map(tape, mk)):
        T[c] = d
        if i % 100 == 0: print('tapes', i, len(mk), round(time.time() - t0), flush=True)
pd.to_pickle(T, OUT + 'tapes_V_taker.pkl')
b = pd.read_parquet(OUT + 'buys.parquet')
out = []
for c in mk:
    r = u.loc[c]
    try: pay = [float(x) for x in json.loads(r.outcomePrices)]; toks = json.loads(r.clobTokenIds)
    except Exception: continue
    g = pred[pred.cid == c]; d = T.get(c)
    rp = 0.0; rcost = 0.0
    if d is not None and len(d) and len(g):
        d = d[(d.side == 'SELL')]
        d = d.assign(price=d.price.astype(float), size=d['size'].astype(float), ts=d.timestamp.astype(int))
        for cell in g.itertuples():
            bid, _ = price_rule(np.array([cell.pf])); bid = float(bid[0]); tok = str(toks[int(cell.fav)])
            f = d[(d.asset.astype(str) == tok) & (d.price <= bid + 1e-9) & (d.ts >= cell.t0 + 2) & (d.ts < cell.t0 + 6 * 3600)]
            sh = f['size'].sum(); rcost += sh * bid; rp += sh * (pay[int(cell.fav)] - bid)
    w = b[(b.conditionId == c) & (b.timestamp >= V[V.cid == c].t0.min()) & (b.timestamp < V[V.cid == c].t0.max() + 6 * 3600)]
    wp = float((w['size'].astype(float) * np.array([pay[int(i)] for i in w.outcomeIndex.astype(int)]) - w.usdcSize).sum()) if len(w) else 0.0
    out.append((c, wp, float(w.usdcSize.sum()) if len(w) else 0.0, rp, rcost))
o = pd.DataFrame(out, columns=['cid', 'wallet_pnl', 'wallet_cost', 'rule_pnl', 'rule_cost'])
o.to_csv(OUT + 'pnl_V_strict.csv', index=False)
res = dict(markets=len(o), pearson_pnl=round(float(pearsonr(o.wallet_pnl, o.rule_pnl)[0]), 4), spearman_pnl=round(float(spearmanr(o.wallet_pnl, o.rule_pnl).correlation), 4),
           pearson_cost=round(float(pearsonr(o.wallet_cost, o.rule_cost)[0]), 4), spearman_cost=round(float(spearmanr(o.wallet_cost, o.rule_cost).correlation), 4),
           wallet_pnl=round(float(o.wallet_pnl.sum()), 2), wallet_cost=round(float(o.wallet_cost.sum()), 2), rule_pnl=round(float(o.rule_pnl.sum()), 2), rule_cost=round(float(o.rule_cost.sum()), 2),
           rule_ret=round(float(o.rule_pnl.sum() / max(1, o.rule_cost.sum())), 5), wallet_ret=round(float(o.wallet_pnl.sum() / max(1, o.wallet_cost.sum())), 5))
print(res)
json.dump(res, open('/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/results_iter1_strictpnl.json', 'w'), indent=1)
