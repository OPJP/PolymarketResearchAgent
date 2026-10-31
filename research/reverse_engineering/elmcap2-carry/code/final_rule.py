"""elmcap2-carry frozen rule (iteration 1). evaluate(start_ts, end_ts) -> dict of metrics.

Universe and cells exactly as pre-registered (NOTES.md): Gamma markets with endDate in [start_ts, end_ts),
volumeNum >= 20k, resolved before end_ts, non-sports, non-Up/Down; 6-hour cells from endDate-14d to
min(closedTime, endDate+14d). Point-in-time features from CLOB hourly prices stamped <= t0 - PRICE_LAG (1 h + 60 s)
and listing fields (endDate, startDate). Outcomes (outcomePrices) are used only to settle PnL.
The score is the frozen rule chosen on VALIDATE (see FINAL_RULE.md). All parameters are constants below.
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
import cells
from cells import build_cells
from metrics import presence_auc, family_auc, selection, side_price
from universe import universe, prices
from polyrea.adapters.polymarket import PolymarketData
W = '0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'
RULE_ID = 'L2_lgbm_price_time_lag3660'
SELECTION_THR = 0.05083237430462293   # market-level threshold: weighted 90th pct of BUILD market max-scores
CELL_THR = 0.0267238585457027   # cell threshold: weighted 95th pct of BUILD cell scores
PRICE_LAG = 3660   # use only hourly prices stamped <= t0 - 1 h - 60 s
MODEL_FILE = os.path.join(HERE, 'model_L2.txt')   # LightGBM text model fitted on BUILD only (a7_final.py)
FEATS = ['pf', 'lpf', 'h_end', 'after_end', 'pf6', 'pf24', 'pf72', 'hrs99', 'hrs95', 'vol24']

def score(d):
    import lightgbm as lgb
    m = lgb.Booster(model_file=MODEL_FILE)
    return m.predict(d[FEATS])

def wallet_buys(start_ts, end_ts):
    rows, _, _ = PolymarketData().activity(W, start=int(start_ts) - 30 * 86400, end=int(end_ts))
    a = pd.DataFrame(rows)
    t = a[(a.type == 'TRADE') & (a.side == 'BUY')].copy()
    for c in ('usdcSize', 'price', 'size'): t[c] = t[c].astype(float)
    return t

def pnl_corr(d, s, thr, u):
    """Per-market PnL: wallet (its buys in cells, settled at outcomePrices) vs a unit-size rule ($1 at the rule price
    in each cell with score >= cell threshold, no fill check; strict_fill_pnl is the realistic version)."""
    pays = {}
    for r in u.itertuples():
        try: pays[r.conditionId] = [float(x) for x in json.loads(r.outcomePrices)]
        except Exception: pass
    from metrics import price_rule
    pr, _ = price_rule(d.pf.values)
    d = d.assign(_s=s, _pr=pr)
    out = []
    for cid, g in d.groupby('cid'):
        pay = pays.get(cid)
        if not pay or len(pay) != 2: continue
        w = g[g.y == 1]
        wp = float(((w.usd / w.wpx) * np.where(w.side_fav >= 0.5, [pay[int(f)] for f in w.fav], [pay[1 - int(f)] for f in w.fav]) - w.usd).sum()) if len(w) else 0.0
        rr = g[g._s >= thr]
        rp = float(((1.0 / rr._pr) * np.array([pay[int(f)] for f in rr.fav]) - 1.0).sum()) if len(rr) else 0.0
        out.append((cid, wp, rp))
    o = pd.DataFrame(out, columns=['cid', 'wallet_pnl', 'rule_pnl'])
    c = float(np.corrcoef(o.wallet_pnl, o.rule_pnl)[0, 1]) if len(o) > 2 and o.rule_pnl.std() > 0 and o.wallet_pnl.std() > 0 else float('nan')
    from scipy.stats import spearmanr
    sp = float(spearmanr(o.wallet_pnl, o.rule_pnl).correlation) if len(o) > 2 else float('nan')
    return dict(markets=len(o), pearson=round(c, 4), spearman=round(sp, 4), wallet_pnl=round(float(o.wallet_pnl.sum()), 2), rule_pnl_per_unit=round(float(o.rule_pnl.sum()), 2))

def strict_fill_pnl(d, s, u, t, slack_ticks=0):
    """Strict maker fills: in each predicted cell the rule rests an unlimited bid for the PIT favourite at
    price_rule(pf); filled by taker SELL prints of that token at price <= bid - slack_ticks*tick, stamped in
    [t0 + 2 s, t0 + 6 h) (data-api taker rows). Settled at outcomePrices. Per-market PnL and capital vs the wallet."""
    from concurrent.futures import ThreadPoolExecutor
    from scipy.stats import spearmanr, pearsonr
    from metrics import price_rule
    pm = PolymarketData(); ui = u.set_index('conditionId')
    d = d.assign(_s=s); pred = d[d._s >= CELL_THR]
    mk = sorted(set(pred.cid) | set(d[d.y == 1].cid))
    def tape(c):
        r = ui.loc[c]
        try:
            rows, _, _ = pm.market_trades(c, start=int(r.end_ts - 14 * 86400), end=int(min(r.closed_ts, r.end_ts + 14 * 86400)), taker_only=True, max_rows=20000)
            return c, pd.DataFrame(rows)
        except Exception:
            return c, None
    with ThreadPoolExecutor(6) as ex: T = dict(ex.map(tape, mk))
    out = []
    for c in mk:
        r = ui.loc[c]
        try: pay = [float(x) for x in json.loads(r.outcomePrices)]; toks = json.loads(r.clobTokenIds)
        except Exception: continue
        g = pred[pred.cid == c]; tp = T.get(c); rp = rc = 0.0
        if tp is not None and len(tp) and len(g):
            tp = tp[tp.side == 'SELL']; tp = tp.assign(price=tp.price.astype(float), sz=tp['size'].astype(float), ts=tp.timestamp.astype(int), tok=tp.asset.astype(str))
            for cell in g.itertuples():
                bid, tk = price_rule(np.array([cell.pf])); bid = float(bid[0]); tk = float(tk[0]); tok = str(toks[int(cell.fav)])
                f = tp[(tp.tok == tok) & (tp.price <= bid - slack_ticks * tk + 1e-9) & (tp.ts >= cell.t0 + 2) & (tp.ts < cell.t0 + 6 * 3600)]
                sh = f.sz.sum(); rc += sh * bid; rp += sh * (pay[int(cell.fav)] - bid)
        dc = d[d.cid == c]
        w = t[(t.conditionId == c) & (t.timestamp >= dc.t0.min()) & (t.timestamp < dc.t0.max() + 6 * 3600)]
        wp = float((w['size'].astype(float) * np.array([pay[int(i)] for i in w.outcomeIndex.astype(int)]) - w.usdcSize).sum()) if len(w) else 0.0
        out.append((c, wp, float(w.usdcSize.sum()) if len(w) else 0.0, rp, rc))
    o = pd.DataFrame(out, columns=['cid', 'wallet_pnl', 'wallet_cost', 'rule_pnl', 'rule_cost'])
    def cor(a, b, fn):
        return round(float(fn(o[a], o[b])[0] if fn is pearsonr else fn(o[a], o[b]).correlation), 4) if len(o) > 2 and o[a].std() > 0 and o[b].std() > 0 else float('nan')
    return dict(slack_ticks=slack_ticks, markets=len(o), pearson_pnl=cor('wallet_pnl', 'rule_pnl', pearsonr), spearman_pnl=cor('wallet_pnl', 'rule_pnl', spearmanr),
                pearson_cost=cor('wallet_cost', 'rule_cost', pearsonr), rule_cost=round(float(o.rule_cost.sum()), 2), rule_pnl=round(float(o.rule_pnl.sum()), 2),
                rule_ret=round(float(o.rule_pnl.sum() / max(1.0, o.rule_cost.sum())), 5), wallet_cost=round(float(o.wallet_cost.sum()), 2), wallet_pnl=round(float(o.wallet_pnl.sum()), 2),
                wallet_ret=round(float(o.wallet_pnl.sum() / max(1.0, o.wallet_cost.sum())), 5))

def evaluate(start_ts, end_ts):
    u = universe(start_ts, end_ts, closed_before=end_ts)
    P = prices(u)
    t = wallet_buys(start_ts, end_ts)
    cells.LAG = PRICE_LAG
    d = build_cells(u, P, t[t.conditionId.isin(u.conditionId)])
    d['neg_risk'] = d.neg_risk.astype(int)
    s = score(d)
    cthr = CELL_THR
    res = dict(rule_id=RULE_ID, window=[int(start_ts), int(end_ts)], universe_markets=int(len(u)), cells=int(len(d)), positive_cells=int(d.y.sum()),
               presence_auc=round(presence_auc(d, s), 4), presence_auc_by_family=family_auc(d, s),
               selection=selection(d, s, SELECTION_THR), side_price=side_price(d, s >= cthr),
               coverage_usd=round(float(d.usd.sum() / max(1e-9, t[t.conditionId.isin(u.conditionId)].usdcSize.sum())), 4),
               pnl_unit=pnl_corr(d, s, cthr, u),
               pnl_strict=strict_fill_pnl(d, s, u, t, 0), pnl_strict_slack1=strict_fill_pnl(d, s, u, t, 1))
    return res

if __name__ == '__main__':
    a, b = int(sys.argv[1]), int(sys.argv[2])
    print(json.dumps(evaluate(a, b), indent=1, default=str))
