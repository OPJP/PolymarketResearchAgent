"""A7: freeze rule L2 (LightGBM behaviour clone on 10 price/time features, price lag 3660 s, fitted on BUILD only),
fix thresholds on BUILD, and compute every VALIDATE metric with the same functions final_rule.evaluate uses."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code')
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
from metrics import presence_auc, family_auc, selection, side_price
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
CODE = '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/code/'
RES = '/home/user/PolymarketResearchAgent/research/reverse_engineering/elmcap2-carry/'
F2 = ['pf', 'lpf', 'h_end', 'after_end', 'pf6', 'pf24', 'pf72', 'hrs99', 'hrs95', 'vol24']
B = pd.read_parquet(OUT + 'cells_Bs_lag3660.parquet'); V = pd.read_parquet(OUT + 'cells_V_lag3660.parquet')
sw = pd.read_parquet(OUT + 'universe_meta_Bs.parquet').set_index('conditionId').sample_w
B['w'] = B.cid.map(sw).fillna(1.0).values
params = dict(objective='binary', learning_rate=0.03, num_leaves=15, min_child_samples=100, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0, verbose=-1, seed=1, num_threads=2, deterministic=True)
m = lgb.train(params, lgb.Dataset(B[F2], B.y, weight=B.w), num_boost_round=400)
m.save_model(CODE + 'model_L2.txt')
sb = m.predict(B[F2]); sv = m.predict(V[F2])
mb = pd.Series(sb).groupby(B.cid.values).max()
# market-level threshold: weighted 90th percentile of BUILD market max-scores; cell threshold: weighted 95th pct of BUILD cells
wm = B.groupby('cid').w.first().reindex(mb.index).values
def wq(x, w, q):
    o = np.argsort(x); cw = np.cumsum(w[o]) / w.sum(); return float(x[o][np.searchsorted(cw, q)])
SEL_THR = wq(mb.values, wm, 0.90); CELL_THR = wq(sb, B.w.values, 0.95)
imp = pd.Series(m.feature_importance('gain'), index=F2); imp = (imp / imp.sum()).round(3).sort_values(ascending=False).to_dict()
res = dict(rule_id='L2_lgbm_price_time_lag3660', features=F2, importance_gain=imp, SEL_THR=SEL_THR, CELL_THR=CELL_THR,
           build_auc_weighted=round(float(roc_auc_score(B.y, sb, sample_weight=B.w)), 4),
           validate=dict(presence_auc=round(presence_auc(V, sv), 4), presence_auc_by_family=family_auc(V, sv),
                         selection=selection(V, sv, SEL_THR, n_perm=1000), side_price_all_wallet_cells=side_price(V, sv >= -1), side_price_rule_cells=side_price(V, sv >= CELL_THR)))
# PnL correlation on resolved VALIDATE markets (outcomes used only to settle PnL)
sys.argv = ['x']
import final_rule
u = pd.read_parquet(OUT + 'universe_meta_V.parquet'); u = u[~u.is_sport & ~u.is_updown]
res['validate']['pnl'] = final_rule.pnl_corr(V, sv, CELL_THR, u)
# presence recall/lift at the cell threshold
pred = sv >= CELL_THR
res['validate']['cell_level'] = dict(pred_cells=int(pred.sum()), recall=round(float(V.y[pred].sum() / V.y.sum()), 3), precision=round(float(V.y[pred].mean()), 4),
                                     lift=round(float(V.y[pred].mean() / V.y.mean()), 2), usd_capture=round(float(V.usd[pred].sum() / V.usd.sum()), 3))
print(json.dumps(res, indent=1, default=str)[:3500])
json.dump(res, open(RES + 'results_iter1_final.json', 'w'), indent=1, default=str)
