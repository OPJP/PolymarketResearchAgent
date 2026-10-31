"""Behaviour cloning (selection): LightGBM on BUILD prints, evaluated on VALIDATE with the within-market AUC.
Reports single-feature within-market AUCs (BUILD), model AUC without/with the print's own size (fingerprint)."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker/code')
import numpy as np, pandas as pd, lightgbm as lgb
from evalkit import within_auc, selection_report

CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'
OUT = '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker'
F = pd.read_parquet(f'{CACHE}/feats.parquet')
F = F[F.period.isin(['BUILD', 'VALIDATE'])].reset_index(drop=True)
# markets where the wallet traded at least once in-play (the selection population)
wm = F.groupby('cid').is_wallet.transform('max').astype(bool)
F = F[wm].reset_index(drop=True)
F['smt_c'] = F.smt.astype('category'); F['fam_c'] = F.fam.astype('category')
F['log_quiet'] = np.log1p(F.quiet.clip(0, 1e5)); F['log_sib_quiet'] = np.log1p(F.sib_quiet.clip(0, 1e6))
F['frac_game'] = F.minute / 120.0
NUM = ['log_quiet', 'last_pk', 'dp_print', 'mv10', 'mv30', 'mv60', 'mv300', 'mv900', 'n10', 'usd10', 'flow10', 'n60', 'usd60',
       'flow60', 'n300', 'usd300', 'flow300', 'n_before', 'minute', 'price', 'tok', 'sib_n10', 'sib_n60', 'sib_mv30',
       'sib_mv120', 'log_sib_quiet', 'n_sib', 'line', 'fee_rate', 'is_over', 'is_under', 'is_yes', 'is_no']
CAT = ['smt_c', 'fam_c']
B = F[F.period == 'BUILD']; V = F[F.period == 'VALIDATE']
print('BUILD', len(B), int(B.is_wallet.sum()), B.cid.nunique(), '| VALIDATE', len(V), int(V.is_wallet.sum()), V.cid.nunique(), flush=True)
res = {'build': {'prints': int(len(B)), 'wallet': int(B.is_wallet.sum()), 'markets': int(B.cid.nunique())},
       'validate': {'prints': int(len(V)), 'wallet': int(V.is_wallet.sum()), 'markets': int(V.cid.nunique())}}
# single-feature within-market AUCs on BUILD (direction-free: report auc)
single = {}
for c in NUM:
    d = B[['cid', 'is_wallet', c]].copy(); d['score'] = d[c].astype(float).fillna(-1e9)
    single[c] = round(float(within_auc(d)), 4)
res['single_feature_auc_build'] = dict(sorted(single.items(), key=lambda kv: -abs(kv[1] - 0.5)))
print('single AUC (BUILD):', list(res['single_feature_auc_build'].items())[:15], flush=True)


def fit(cols, name):
    bt = B.sort_values('ts'); cut = int(len(bt) * 0.8)
    tr, va = bt.iloc[:cut], bt.iloc[cut:]
    params = dict(objective='binary', learning_rate=0.05, num_leaves=63, min_data_in_leaf=200, feature_fraction=0.8,
                  bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, num_threads=3)
    dtr = lgb.Dataset(tr[cols], tr.is_wallet.astype(int), categorical_feature=[c for c in cols if c in CAT])
    dva = lgb.Dataset(va[cols], va.is_wallet.astype(int), reference=dtr)
    m = lgb.train(params, dtr, 1500, valid_sets=[dva], callbacks=[lgb.early_stopping(50, verbose=False)])
    v = V.copy(); v['score'] = m.predict(V[cols], num_iteration=m.best_iteration)
    rep = selection_report(v)
    imp = dict(sorted(zip(cols, m.feature_importance('gain').round(0).tolist()), key=lambda kv: -kv[1]))
    rep['best_iter'] = int(m.best_iteration); rep['importance_gain'] = {k: float(x) for k, x in list(imp.items())[:20]}
    # by family / market type
    rep['auc_by_fam'] = {k: round(float(within_auc(g)), 3) for k, g in v.groupby('fam') if g.is_wallet.sum() >= 20}
    rep['auc_by_smt'] = {k: round(float(within_auc(g)), 3) for k, g in v.groupby('smt') if g.is_wallet.sum() >= 20}
    print(name, json.dumps({k: rep[k] for k in ['auc', 'recall', 'lift', 'precision', 'base_rate', 'perm_p_normal_approx']}), flush=True)
    print('  importance', list(rep['importance_gain'].items())[:12], flush=True)
    return m, rep, v


m1, r1, v1 = fit(NUM + CAT, 'lgb_public')
res['lgb_public'] = r1
F['log_usd'] = np.log(F.usd.clip(0.01)); B = F[F.period == 'BUILD']; V = F[F.period == 'VALIDATE']
m2, r2, v2 = fit(NUM + CAT + ['log_usd'], 'lgb_public_plus_own_size_fingerprint')
res['lgb_fingerprint_size'] = r2
json.dump(res, open(f'{OUT}/model_selection_result.json', 'w'), indent=1, default=float)
v1[['cid', 'ts', 'tok', 'price', 'is_wallet', 'score', 'fam', 'smt']].to_parquet(f'{CACHE}/validate_scores_lgb_public.parquet')
# freeze the public (no own-state) model for final_rule.py
m1.save_model(f'{OUT}/code/model_lgb_public.txt', num_iteration=m1.best_iteration)
json.dump({'features': NUM + CAT, 'cat': CAT, 'smt_categories': list(F.smt_c.cat.categories), 'fam_categories': list(F.fam_c.cat.categories)},
          open(f'{OUT}/code/model_lgb_public_spec.json', 'w'), indent=1)
