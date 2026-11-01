"""E2 + E7: out-of-fold residuals of the selection model on BUILD (GroupKFold over games = event slugs), their
shape (family, hour, minute in game, quiet, goal recency, price), and cross-market synchrony of the missed
decisions (residual_clustering; only decisions more than 10 min after each game start, as the brief asks for
irregular starts). Writes results/iter2_e2.json."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE, ROOT
import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.model_selection import GroupKFold
import final_rule as fr
import indicators as ind

WS = os.path.join(ROOT, 'research', 'reverse_engineering', 'dbdd-inplay-taker')
gm = json.load(open(f'{CACHE}/gamma2.json'))
B = pd.read_parquet(f'{CACHE}/feats_build_it2.parquet')
B['game'] = B.cid.map(lambda c: re.sub(r'-(more-markets|halftime-result|total-corners|exact-score|player-props|first-half.*|btts.*)$', '',
                                       (((gm[c].get('events') or [{}])[0] or {}).get('slug') or gm[c].get('slug') or '')))
P = dict(objective='binary', learning_rate=0.05, num_leaves=31, min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8,
         bagging_freq=1, max_bin=63, verbose=-1, seed=1)
oof = np.zeros(len(B))
for tr, te in GroupKFold(5).split(B, B.y, B.game):
    d = lgb.Dataset(B.iloc[tr][fr.FULL_FEATS].astype('float32'), B.iloc[tr].y.astype(int))
    m = lgb.train(P, d, 150)
    oof[te] = m.predict(B.iloc[te][fr.FULL_FEATS].astype('float32'))
B['oof'] = oof
# within-market percentile of each wallet print's OOF score; a 'miss' = below the market's top-15% flag
B['pct'] = B.groupby('cid').oof.rank(pct=True)
w = B[B.y].copy()
w['miss'] = w.pct < 1 - fr.FLAG_TOP
res = {'n_wallet_build': int(len(w)), 'oof_auc': fr.within_market_auc(B, 'oof')['auc'], 'miss_share': float(w.miss.mean())}
w['hour'] = pd.to_datetime(w.ts, unit='s').dt.hour
w['fam'] = w.fam_c.map(lambda i: fr.FAMS[int(i)])
w['qbin'] = pd.cut(np.expm1(w.log_quiet), [-1, 2, 10, 30, 120, 1e9], labels=['<2s', '2-10s', '10-30s', '30-120s', '>120s'])
w['mbin'] = pd.cut(w.minute, [-1, 10, 30, 60, 90, 1e9], labels=['0-10', '10-30', '30-60', '60-90', '>90'])
w['gbin'] = np.where(w.goal_recent > 0, 'goal<=80s', 'no_recent_goal')
w['pbin'] = pd.cut(w.price, [0, .2, .4, .6, .8, 1], labels=['<.2', '.2-.4', '.4-.6', '.6-.8', '>.8'])
for col in ('fam', 'hour', 'qbin', 'mbin', 'gbin', 'pbin'):
    g = w.groupby(col, observed=True).miss.agg(['mean', 'size'])
    res[f'miss_by_{col}'] = {str(k): [round(float(r['mean']), 3), int(r['size'])] for k, r in g.iterrows()}
# E7: synchrony of misses across markets (decisions > 10 min after start)
mm = w[w.miss & (w.minute > 10)]
if len(mm) > 50:
    rc = ind.residual_clustering(mm.ts.values.astype(float), mm.cid.values, delta_s=2.0, n_null=500, seed=1)
    res['e7_residual_clustering'] = {k: rc[k] for k in rc if k not in ('top', 'clusters')}
    res['e7_top'] = rc.get('top', [])[:10] if isinstance(rc.get('top'), list) else None
    # hits for comparison
    hh = w[(~w.miss) & (w.minute > 10)]
    rc2 = ind.residual_clustering(hh.ts.values.astype(float), hh.cid.values, delta_s=2.0, n_null=500, seed=2)
    res['e7_hits_clustering'] = {k: rc2[k] for k in rc2 if k not in ('top', 'clusters')}
json.dump(res, open(os.path.join(WS, 'results', 'iter2_e2.json'), 'w'), indent=1, default=str)
for k, v in res.items():
    print(k, v)
