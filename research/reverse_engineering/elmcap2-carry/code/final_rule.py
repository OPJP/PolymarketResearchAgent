"""elmcap2-carry frozen rule (iteration 1). evaluate(start_ts, end_ts) -> dict of metrics.

Universe and cells exactly as pre-registered (NOTES.md): Gamma markets with endDate in [start_ts, end_ts),
volumeNum >= 20k, resolved before end_ts, non-sports, non-Up/Down; 6-hour cells from endDate-14d to
min(closedTime, endDate+14d). Point-in-time features from CLOB hourly prices stamped <= t0-60s and listing fields.
The score is the frozen rule chosen on VALIDATE (see FINAL_RULE.md). All parameters are constants below.
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from cells import build_cells
from metrics import presence_auc, family_auc, selection, side_price
from universe import universe, prices
from polyrea.adapters.polymarket import PolymarketData
W = '0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'
RULE_ID = 'PLACEHOLDER'
SELECTION_THR = None   # market-level threshold, fixed on BUILD
FEATS = ['pf', 'lpf', 'h_end', 'after_end', 'pf6', 'pf24', 'pf72', 'jump24', 'jump72', 'vol24', 'hrs99', 'hrs95', 'age_h', 'hour', 'dow', 'neg_risk',
         'fam_fomc', 'fam_mention', 'fam_deadline', 'fam_election', 'fam_crypto', 'fam_other']

def score(d):
    raise NotImplementedError

def wallet_buys(start_ts, end_ts):
    rows, _, _ = PolymarketData().activity(W, start=int(start_ts) - 30 * 86400, end=int(end_ts))
    a = pd.DataFrame(rows)
    t = a[(a.type == 'TRADE') & (a.side == 'BUY')].copy()
    for c in ('usdcSize', 'price', 'size'): t[c] = t[c].astype(float)
    return t

def pnl_corr(d, s, thr, u):
    """Per-market PnL: wallet (its buys in cells, settled at outcomePrices) vs rule ($1 at the rule price in each
    cell with score >= cell threshold, filled if a later hourly price in the cell printed at or below it)."""
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

def evaluate(start_ts, end_ts):
    u = universe(start_ts, end_ts, closed_before=end_ts)
    P = prices(u)
    t = wallet_buys(start_ts, end_ts)
    d = build_cells(u, P, t[t.conditionId.isin(u.conditionId)])
    d['neg_risk'] = d.neg_risk.astype(int)
    s = score(d)
    cthr = CELL_THR
    res = dict(rule_id=RULE_ID, window=[int(start_ts), int(end_ts)], universe_markets=int(len(u)), cells=int(len(d)), positive_cells=int(d.y.sum()),
               presence_auc=round(presence_auc(d, s), 4), presence_auc_by_family=family_auc(d, s),
               selection=selection(d, s, SELECTION_THR), side_price=side_price(d, s >= cthr),
               coverage_usd=round(float(d.usd.sum() / max(1e-9, t[t.conditionId.isin(u.conditionId)].usdcSize.sum())), 4),
               pnl=pnl_corr(d, s, cthr, u))
    return res

if __name__ == '__main__':
    a, b = int(sys.argv[1]), int(sys.argv[2])
    print(json.dumps(evaluate(a, b), indent=1, default=str))
