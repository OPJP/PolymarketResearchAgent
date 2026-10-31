"""Recompute Tommy's mechanism numbers (pair cost, two-sided share, locked vs residual) with sells signed correctly."""
import _env, os, pickle, json
import numpy as np, pandas as pd
from polyrea.analysis.ledger import build_ledger
from polyrea.analysis.profile import per_market_decomposition, resolution_info, summarize_profile, timing_features
win = pickle.load(open(os.path.join(_env.SCR, 'win_Tommy.pkl'), 'rb'))
res_ts = {cid: r['closed_ts'] for cid, m in win['markets'].items() if (r := resolution_info(m))['resolved'] and r['closed_ts']}
led = build_ledger(win['wallet'], win['activity'], res_ts)
tr = pd.DataFrame(led.trades); tr = tr[(tr.ts >= win['start']) & (tr.ts < win['as_of'])].reset_index(drop=True)
pm = per_market_decomposition(tr, win['markets'])
s = summarize_profile(tr, pm, timing_features(tr, win['markets']))
print('AS CODED : two-sided share %.3f median pair cost %.3f median balance %.3f settled %.0f locked %.0f resid %.0f' % (s['share_two_sided_markets'], s['median_pair_cost'], s['median_balance'], s['settled_pnl'], s['settled_locked_pnl'], s['settled_residual_pnl']))
rows = []
for cid, g in tr.groupby('condition_id'):
    m = win['markets'].get(cid) or {}; res = resolution_info(m); tok = json.loads(m.get('clobTokenIds') or '[]')
    b, sl = g[g.side == 'BUY'], g[g.side == 'SELL']
    qb = {i: b[b.outcome_index == i]['size'].sum() for i in (0, 1)}; cb = {i: b[b.outcome_index == i]['usdc'].sum() for i in (0, 1)}
    qs = {i: sl[sl.outcome_index == i]['size'].sum() for i in (0, 1)}; ps = {i: sl[sl.outcome_index == i]['usdc'].sum() for i in (0, 1)}
    a = {i: cb[i] / qb[i] if qb[i] else np.nan for i in (0, 1)}
    realized = sum(ps[i] - (a[i] if qb[i] else 0) * min(qs[i], qb[i]) for i in (0, 1))
    net = {i: max(qb[i] - qs[i], 0.0) for i in (0, 1)}
    pairs = min(net[0], net[1]); locked = pairs * (1 - a[0] - a[1]) if pairs > 0 else 0.0
    rside = 0 if net[0] > net[1] else 1; rq = abs(net[0] - net[1])
    ok = res['resolved'] and len(tok) == 2
    resid = (rq * res['payout'].get(str(tok[rside]), 0.0) - rq * a[rside]) if ok and rq > 0 else (0.0 if ok else np.nan)
    rows.append(dict(cid=cid, resolved=ok, two_sided_buys=qb[0] > 0 and qb[1] > 0, pair_cost_buys=(a[0] + a[1]) if min(qb.values()) > 0 else np.nan,
                     balance_buys=min(qb.values()) / max(qb.values()) if max(qb.values()) > 0 else np.nan, realized=realized, locked=locked, resid=resid))
d = pd.DataFrame(rows); r = d[d.resolved]
print('CORRECTED: two-sided share %.3f median pair cost (buys) %.3f median balance (buys) %.3f | resolved: realized-from-sells %.0f locked(net held) %.0f resid(net held) %.0f total %.0f' % (
    d.two_sided_buys.mean(), d.pair_cost_buys.median(), d.balance_buys.median(), r.realized.sum(), r.locked.sum(), r.resid.sum(), r.realized.sum() + r.locked.sum() + r.resid.sum()))
