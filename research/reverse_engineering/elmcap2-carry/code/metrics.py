"""Shared metrics: presence AUC, market-level selection (permutation null), side, price-within-tick, PnL correlation."""
import json
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score

def presence_auc(d, s):
    return float(roc_auc_score(d.y.values, s)) if d.y.nunique() == 2 else float('nan')

def family_auc(d, s):
    out = {}
    for f, g in d.assign(_s=s).groupby('fam'):
        if g.y.nunique() == 2: out[f] = round(float(roc_auc_score(g.y, g._s)), 3)
    return out

def selection(d, s, thr, n_perm=2000, seed=0):
    """Market level: max score per market vs wallet traded the market (in-window). Permutation null over markets."""
    m = d.assign(_s=s).groupby('cid').agg(s=('_s', 'max'), y=('y', 'max'))
    auc = float(roc_auc_score(m.y, m.s)) if m.y.nunique() == 2 else float('nan')
    pred = m.s >= thr
    tp = int((pred & (m.y == 1)).sum()); P = int(pred.sum()); Y = int(m.y.sum())
    recall = tp / max(1, Y); prec = tp / max(1, P); base = Y / len(m); lift = prec / base if base > 0 else float('nan')
    rng = np.random.default_rng(seed); yv = m.y.values; null = np.empty(n_perm)
    for i in range(n_perm):
        null[i] = roc_auc_score(rng.permutation(yv), m.s.values)
    p = float((1 + (null >= auc).sum()) / (1 + n_perm))
    # lift significance: hypergeometric
    from scipy.stats import hypergeom
    p_lift = float(hypergeom.sf(tp - 1, len(m), Y, P)) if P > 0 else 1.0
    return dict(markets=len(m), wallet_markets=Y, auc=round(auc, 4), auc_null_mean=round(float(null.mean()), 4), auc_p=p, thr=thr,
                predicted=P, recall=round(recall, 3), precision=round(prec, 4), lift=round(lift, 2), lift_p=p_lift)

def tick_of(p):
    return np.where((p > 0.96) | (p < 0.04), 0.001, 0.01)

def price_rule(pf):
    """Predicted bid for the favourite: the PIT price rounded down to the tick, capped at 1 - tick."""
    tk = tick_of(pf)
    return np.minimum(1 - tk, np.floor(pf / tk + 1e-9) * tk), tk

def side_price(d, pos_mask):
    g = d[pos_mask & (d.y == 1)]
    side_acc = float(g.side_fav.mean()) if len(g) else float('nan')
    pr, tk = price_rule(g.pf.values)
    within = np.abs(g.wpx.values - pr) <= tk + 1e-9
    return dict(cells=len(g), side_acc_fav=round(side_acc, 4), price_within_tick=round(float(np.nanmean(within)), 4),
                median_wpx_minus_pf=round(float(np.nanmedian(g.wpx.values - g.pf.values)), 4))
