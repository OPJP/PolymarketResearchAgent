"""Iteration 10 (price component, follow-up of X137): does the maker leg run ONE coherent event valuation across the
event's markets? On a feed message it re-prices the match market and the current map market within 150 ms (X137 msg
class). Series math predicts the match value's change = sensitivity x the map value's change, with sensitivity 1 on map 3
(score 1-1) and about 0.5 on maps 1-2 of a BO3 (2q(1-q) at 0-0, 1-q or q at 1-0 / 0-1).
Rows: ledger_rows_iter10.parquet (filled maker orders 16-22 Oct, development). dV = price - its previous own level on the
same token; on the other team's token the implied change of team A's value is -dV. Per (message, market) the mean
implied change of team A (outcome 0 of the match market, names aligned through universe.parquet). Pairs (match, map k)
on the same message: OLS slope of the match change on the map change by map number, correlation, n.
Output: results/series_coherence_msg_follow.json
"""
import json
import numpy as np, pandas as pd

ROOT = '.cache/re/tommy-cs2-maker'
X = pd.read_parquet(f'{ROOT}/ledger_rows_iter10.parquet')
U = pd.read_parquet(f'{ROOT}/universe.parquet', columns=['cid', 'slug', 'smt', 'outcomes', 'event_slug'])
U['outs'] = U.outcomes.apply(lambda s: json.loads(s) if isinstance(s, str) else list(s))
X = X.merge(U[['cid', 'slug', 'smt', 'outs', 'event_slug']], on='cid', how='left')
X = X[X.cls.isin(['msg', 'follow']) & np.isfinite(X.a_own) & X.smt.isin(['moneyline', 'child_moneyline'])].copy()
X['dv'] = (X.price - X.a_own) * 100
X = X[np.abs(X.dv) <= 30]
X = X[np.isfinite(X.dmsg) & (X.dmsg <= 5000)]
X['mkey'] = X.event + '|' + np.round((X.sign_ms - X.dmsg) / 10).astype('int64').astype(str)
X['team'] = [o[int(i)] if isinstance(o, list) and len(o) == 2 else None for o, i in zip(X.outs, X.oi)]
match_teamA = U[U.smt == 'moneyline'].set_index('event_slug').outs.apply(lambda o: o[0] if len(o) == 2 else None).to_dict()
X['teamA'] = X.event.map(match_teamA)
X = X.dropna(subset=['team', 'teamA'])
X['dA'] = np.where(X.team == X.teamA, X.dv, -X.dv)
X['mapno'] = np.where(X.smt == 'moneyline', 0, X.slug.str.extract(r'-game(\d)$')[0].astype(float))
G = X.groupby(['mkey', 'mapno']).dA.mean().unstack()
res = {'messages_with_msg_orders': int(G.shape[0])}
for k in (1, 2, 3):
    if 0 not in G or k not in G:
        continue
    j = G[[0, k]].dropna()
    if len(j) < 5:
        res[f'map{k}'] = {'n': int(len(j))}
        continue
    x, y = j[k].to_numpy(), j[0].to_numpy()
    slope = float(np.polyfit(x, y, 1)[0]) if np.std(x) > 0 else None
    res[f'map{k}'] = {'n': int(len(j)), 'slope_match_on_map': round(slope, 3) if slope is not None else None,
                      'corr': round(float(np.corrcoef(x, y)[0, 1]), 3), 'same_sign_share': round(float(np.mean(np.sign(x) == np.sign(y))), 3),
                      'ratio_median': round(float(np.median(y[np.abs(x) >= 1] / x[np.abs(x) >= 1])), 3) if (np.abs(x) >= 1).sum() >= 5 else None}
json.dump(res, open('research/reverse_engineering/tommy-cs2-maker/results/series_coherence_msg_follow.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
