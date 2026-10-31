"""A4: fit presence models on BUILD cells, evaluate candidates on VALIDATE (primary metric + secondaries)."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code')
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
from metrics import presence_auc, family_auc, selection, side_price
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
RES = '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/'
B = pd.read_parquet(OUT + 'cells_Bs.parquet'); V = pd.read_parquet(OUT + 'cells_V.parquet')
sw = pd.read_parquet(OUT + 'universe_meta_Bs.parquet').set_index('conditionId').sample_w
B['w'] = B.cid.map(sw).fillna(1.0).values
FEATS = ['pf', 'lpf', 'h_end', 'after_end', 'pf6', 'pf24', 'pf72', 'jump24', 'jump72', 'vol24', 'hrs99', 'hrs95', 'age_h', 'hour', 'dow', 'neg_risk',
         'fam_fomc', 'fam_mention', 'fam_deadline', 'fam_election', 'fam_crypto', 'fam_other']
for d in (B, V): d['neg_risk'] = d.neg_risk.astype(int)
print('BUILD cells', len(B), 'pos', int(B.y.sum()), 'markets', B.cid.nunique(), 'pos markets', B[B.y == 1].cid.nunique())
print('VALID cells', len(V), 'pos', int(V.y.sum()), 'markets', V.cid.nunique(), 'pos markets', V[V.y == 1].cid.nunique())
res = {}
# candidate explicit scores (no fitting)
cands = {
    'S1_certainty': lambda d: d.lpf.values,
    'S2_certainty_after_end': lambda d: d.lpf.values + 1.0 * d.after_end.values,
}
# LightGBM behaviour clone
params = dict(objective='binary', learning_rate=0.03, num_leaves=15, min_child_samples=100, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0, verbose=-1, seed=1)
m = lgb.train(params, lgb.Dataset(B[FEATS], B.y, weight=B.w), num_boost_round=400)
imp = pd.Series(m.feature_importance('gain'), index=FEATS).sort_values(ascending=False)
print('LGBM gain importance:', (imp / imp.sum()).round(3).head(12).to_dict())
cands['L1_lgbm_all'] = lambda d: m.predict(d[FEATS])
m.save_model(OUT + 'lgbm_L1.txt')
for k, f in cands.items():
    sb, sv = f(B), f(V)
    thr = float(np.quantile(pd.Series(sb).groupby(B.cid.values).max(), 0.9))  # threshold fixed on BUILD: top 10% of markets
    r = dict(build_auc=round(float(roc_auc_score(B.y, sb, sample_weight=B.w)), 4), validate_auc=round(presence_auc(V, sv), 4), validate_family_auc=family_auc(V, sv),
             selection_V=selection(V, sv, thr, n_perm=500))
    # side/price on predicted-positive cells (score above BUILD 95th pct of cells)
    cthr = float(np.quantile(sb, 0.95))
    r['side_price_V'] = side_price(V, sv >= -np.inf)
    res[k] = r
    print(k, json.dumps(r)[:900])
json.dump(res, open(RES + 'results_iter1_a4.json', 'w'), indent=1, default=str)
