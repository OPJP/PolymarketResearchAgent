"""A5: robustness of L1 (BUILD-fitted LGBM): (i) price lag 1 h + 60 s instead of 60 s (guards against hourly
points that summarise the following hour), (ii) without age_h, (iii) without family flags. Fit on BUILD, AUC on VALIDATE."""
import sys
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code')
import numpy as np, pandas as pd, lightgbm as lgb, json
from sklearn.metrics import roc_auc_score
import cells
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
b = pd.read_parquet(OUT + 'buys.parquet')
def mk(tag, lag):
    cells.LAG = lag
    u = pd.read_parquet(OUT + f'universe_meta_{tag}.parquet')
    if 'is_sport' in u: u = u[~u.is_sport & ~u.is_updown]
    P = pd.read_pickle(OUT + f'universe_prices_{tag}.pkl')
    d = cells.build_cells(u, P, b[b.conditionId.isin(u.conditionId)]); d['neg_risk'] = d.neg_risk.astype(int)
    return d
FE = ['pf', 'lpf', 'h_end', 'after_end', 'pf6', 'pf24', 'pf72', 'jump24', 'jump72', 'vol24', 'hrs99', 'hrs95', 'age_h', 'hour', 'dow', 'neg_risk',
      'fam_fomc', 'fam_mention', 'fam_deadline', 'fam_election', 'fam_crypto', 'fam_other']
params = dict(objective='binary', learning_rate=0.03, num_leaves=15, min_child_samples=100, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0, verbose=-1, seed=1, num_threads=2)
sw = pd.read_parquet(OUT + 'universe_meta_Bs.parquet').set_index('conditionId').sample_w
out = {}
for lag in [60, 3660]:
    B = mk('Bs', lag); V = mk('V', lag); B['w'] = B.cid.map(sw).fillna(1.0).values
    for nm, fs in [('all', FE), ('no_age', [f for f in FE if f != 'age_h']), ('no_fam', [f for f in FE if not f.startswith('fam_')]), ('price_time_only', ['pf', 'lpf', 'h_end', 'after_end', 'pf6', 'pf24', 'pf72', 'hrs99', 'hrs95', 'vol24'])]:
        m = lgb.train(params, lgb.Dataset(B[fs], B.y, weight=B.w), num_boost_round=400)
        out[f'lag{lag}_{nm}'] = round(float(roc_auc_score(V.y, m.predict(V[fs]))), 4)
        print(f'lag{lag}_{nm}', out[f'lag{lag}_{nm}'], flush=True)
json.dump(out, open('/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/results_iter1_a5.json', 'w'), indent=1)
