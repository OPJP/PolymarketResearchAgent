"""Presence model: does the wallet print in (market, 10 s bin)? Point-in-time features at bin start b use prints
<= b - 2 only. Negatives subsampled at 10% (AUC-invariant). LightGBM fitted on BUILD, AUC on VALIDATE
(pooled and within-market). No own-state features."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker/code')
import numpy as np, pandas as pd, lightgbm as lgb
from features import market_meta, W
from build_features import load_tapes, base_slug
from evalkit import within_auc_stats
from sklearn.metrics import roc_auc_score
from polyrea_path import *  # noqa (adds repo root)
from polyrea.analysis.profile import market_family

CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'
OUT = '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker'
V0 = 1791849600; B0 = 1790121600; BIN = 10; NEG = 0.10
gm = json.load(open(f'{CACHE}/gamma.json'))
tapes = load_tapes()
wm = set(tapes[tapes.proxyWallet.str.lower() == W].cid.unique())
rng = np.random.default_rng(1)
rows = []
for c, d in tapes[tapes.cid.isin(wm)].groupby('cid'):
    m = market_meta(gm[c])
    if len(m['toks']) != 2 or not np.isfinite(m['gst']):
        continue
    d = d.sort_values('timestamp')
    tok = d.asset.astype(str).map({m['toks'][0]: 0, m['toks'][1]: 1}); ok = tok.notna().to_numpy()
    ts = d.timestamp.to_numpy()[ok].astype(np.int64); p0 = np.where(tok.to_numpy()[ok] == 0, d.price.to_numpy()[ok], 1 - d.price.to_numpy()[ok])
    isw = (d.proxyWallet.str.lower() == W).to_numpy()[ok]
    if len(ts) < 3:
        continue
    g0 = int(m['gst']); g1 = int(min(ts.max(), g0 + 4 * 3600))
    if g1 <= g0:
        continue
    b = np.arange(g0, g1, BIN)
    lab = np.zeros(len(b), bool)
    wi = ((ts[isw] - g0) // BIN).astype(int); wi = wi[(wi >= 0) & (wi < len(b))]; lab[wi] = True
    keep = lab | (rng.random(len(b)) < NEG)
    b = b[keep]; lab = lab[keep]
    T = b - 2
    j = np.searchsorted(ts, T, side='right') - 1
    last = np.where(j >= 0, p0[np.clip(j, 0, None)], np.nan)
    f = {'cid': c, 'b': b, 'y': lab, 'quiet': np.where(j >= 0, b - ts[np.clip(j, 0, None)], 1e5), 'p0': last,
         'ext': np.abs(last - 0.5), 'minute': (b - g0) / 60.0, 'n_before': j + 1}
    for dt in (10, 60, 300):
        k = np.searchsorted(ts, T - dt, side='right') - 1
        prev = np.where(k >= 0, p0[np.clip(k, 0, None)], np.nan)
        f[f'amv{dt}'] = np.abs(last - prev); f[f'n{dt}'] = j - k
    f['smt'] = m['smt']; f['fam'] = market_family(m['slug']); f['period'] = 'VALIDATE' if g0 >= V0 else ('BUILD' if g0 >= B0 else 'PRE')
    rows.append(pd.DataFrame(f))
P = pd.concat(rows, ignore_index=True)
P = P[P.period.isin(['BUILD', 'VALIDATE'])]
P['smt'] = P.smt.astype('category'); P['fam'] = P.fam.astype('category')
X = ['quiet', 'p0', 'ext', 'minute', 'n_before', 'amv10', 'amv60', 'amv300', 'n10', 'n60', 'n300', 'smt', 'fam']
B = P[P.period == 'BUILD']; V = P[P.period == 'VALIDATE'].copy()
print('bins BUILD', len(B), int(B.y.sum()), '| VALIDATE', len(V), int(V.y.sum()), flush=True)
bt = B.sort_values('b'); cut = int(len(bt) * 0.8)
dtr = lgb.Dataset(bt.iloc[:cut][X], bt.iloc[:cut].y.astype(int)); dva = lgb.Dataset(bt.iloc[cut:][X], bt.iloc[cut:].y.astype(int), reference=dtr)
params = dict(objective='binary', learning_rate=0.05, num_leaves=63, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, verbose=-1, num_threads=3)
mdl = lgb.train(params, dtr, 1500, valid_sets=[dva], callbacks=[lgb.early_stopping(50, verbose=False)])
V['score'] = mdl.predict(V[X], num_iteration=mdl.best_iteration)
V['is_wallet'] = V.y
res = {'pooled_auc': float(roc_auc_score(V.y, V.score)), 'within_market_auc': within_auc_stats(V, 'score')[0],
       'bins_validate': int(len(V)), 'pos_validate': int(V.y.sum()), 'neg_subsample': NEG, 'bin_s': BIN,
       'importance_gain': dict(sorted(zip(X, mdl.feature_importance('gain').round(0).tolist()), key=lambda kv: -kv[1]))}
print(json.dumps(res, default=float), flush=True)
json.dump(res, open(f'{OUT}/presence_result.json', 'w'), indent=1, default=float)
