"""Fit the iteration-2 selection models on BUILD (sampled tapes2 markets), freeze them, and score VALIDATE.

full = activity + metadata + ESPN goal recency; base = market activity only (co-occurrence baseline), same model
class and tuning. Early stopping on the last 20% of BUILD by unit start. VALIDATE metrics -> results/iter2_val.json.
"""
import sys, os, glob, json, re, time
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE, ROOT
import numpy as np, pandas as pd
import lightgbm as lgb
import final_rule as fr

WS = os.path.join(ROOT, 'research', 'reverse_engineering', 'dbdd-inplay-taker')
VAL0, H = 1791849600, 1792713600
gm = json.load(open(f'{CACHE}/gamma2.json'))
ke = pd.read_parquet(f'{CACHE}/espn_soccer_keyevents.parquet')
goals_by_ev = ke[ke.scoring.astype(bool) & ke.wallclock.notna()].groupby('event_slug').wallclock.apply(list).to_dict()


def base_slug(c):
    m = gm[c]
    s = ((m.get('events') or [{}])[0] or {}).get('slug') or m.get('slug') or ''
    return re.sub(r'-(more-markets|halftime-result|total-corners|exact-score|player-props|first-half.*|btts.*)$', '', s)


def feats_for(period):
    parts = []
    for f in glob.glob(f'{CACHE}/tapes2/*.parquet'):
        c = os.path.basename(f)[:-8]
        m = gm.get(c)
        if not m or m.get('sealed', 1):
            continue
        u = m['unit_ts']
        if period == 'BUILD' and not (u < VAL0):
            continue
        if period == 'VALIDATE' and not (VAL0 <= u < H):
            continue
        try:
            d = pd.read_parquet(f)
        except Exception:
            continue
        if d.empty or 'timestamp' not in d:
            continue
        d = d.sort_values('timestamp', kind='stable').reset_index(drop=True)
        F = fr.market_features(d, u, m, goals_by_ev.get(base_slug(c)))
        if len(F):
            F['cid'] = c
            F['unit'] = u
            parts.append(F)
    return pd.concat(parts, ignore_index=True)


t0 = time.time()
B = feats_for('BUILD')
V = feats_for('VALIDATE')
print('BUILD prints', len(B), 'wallet', int(B.y.sum()), 'markets', B.cid.nunique(), '| VALIDATE', len(V), int(V.y.sum()), V.cid.nunique(), round(time.time() - t0), 's', flush=True)
B.to_parquet(f'{CACHE}/feats_build_it2.parquet')
V.to_parquet(f'{CACHE}/feats_val_it2.parquet')
cut = B.unit.quantile(0.8)
tr, es = B[B.unit < cut], B[B.unit >= cut]
P = dict(objective='binary', learning_rate=0.05, num_leaves=31, min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8,
         bagging_freq=1, max_bin=63, verbose=-1, seed=1)
models = {}
for name, cols, path in (('full', fr.FULL_FEATS, fr.MODEL_FULL), ('base', fr.BASE_FEATS, fr.MODEL_BASE)):
    dtr = lgb.Dataset(tr[cols].astype('float32'), tr.y.astype(int), categorical_feature=[c for c in ('fam_c', 'smt_c') if c in cols] or 'auto')
    des = lgb.Dataset(es[cols].astype('float32'), es.y.astype(int), reference=dtr)
    bst = lgb.train(P, dtr, 600, valid_sets=[des], callbacks=[lgb.early_stopping(40, verbose=False)])
    bst.save_model(path)
    models[name] = bst
    imp = dict(zip(cols, bst.feature_importance('gain')))
    print(name, 'iters', bst.best_iteration, 'top gain', sorted(imp.items(), key=lambda x: -x[1])[:8], flush=True)
V = fr.score(V)
sel = fr.within_market_auc(V, 's_full')
bas = fr.within_market_auc(V, 's_base')
gain, ci, p0 = fr.block_bootstrap_gain(V, 's_full', 's_base', n_boot=500)
# goal indicator incremental on soccer only
Vs = V[V.fam_c == fr.FAMS.index('soccer_other')]
sel_s, bas_s = fr.within_market_auc(Vs, 's_full'), fr.within_market_auc(Vs, 's_base')
res = {'n_build_prints': int(len(B)), 'n_build_wallet': int(B.y.sum()), 'n_build_markets': int(B.cid.nunique()),
       'n_val_prints': sel['n_prints'], 'n_val_wallet': sel['n_pos'], 'n_val_markets': int(V.cid.nunique()),
       'selection_auc': sel['auc'], 'selection_recall': sel['recall'], 'selection_lift': sel['lift'], 'selection_baseline': bas['auc'],
       'baseline_recall': bas['recall'], 'baseline_lift': bas['lift'], 'gain': gain, 'gain_ci95': ci, 'p_gain_le_0': p0,
       'soccer_other_auc_full': sel_s['auc'], 'soccer_other_auc_base': bas_s['auc'],
       'importance_full': {k: float(v) for k, v in zip(fr.FULL_FEATS, models['full'].feature_importance('gain'))}}
# side on the wallet's VALIDATE prints
w = V[V.y]
v = w[w.mv300.notna() & (w.mv300 != 0)]
res['side_accuracy_mv300'] = float((v.mv300 > 0).mean())
res['side_n_mv300'] = int(len(v))
res['side_coverage_mv300'] = float(len(v) / len(w))
res['side_baseline_favourite'] = float((w.price > 0.5).mean())
v2 = w[w.flow60.notna() & (w.flow60 != 0)]
res['side_accuracy_flow60'] = float((v2.flow60 > 0).mean())
res['side_coverage_flow60'] = float(len(v2) / len(w))
# price/size from the calldata (all VALIDATE orders, not only sampled markets)
O = pd.read_parquet(f'{CACHE}/orders.parquet')
Ov = O[O.period == 'VALIDATE']
res['price_within_tick'] = float((np.abs(Ov.t_px - Ov.price) <= 0.0105).mean())
res['price_limit_eq_fill'] = float((np.abs(Ov.t_px - Ov.price) < 0.0015).mean())
res['size_integer_usdc_share'] = float((np.abs(Ov.t_usdc - Ov.t_usdc.round()) < 1e-6).mean())
# coverage: wallet fills of the sampled VALIDATE markets that are in the scored in-play population
act = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/activity/pre_*.parquet')])
av = act[act.conditionId.isin(set(V.cid))]
unit = av.conditionId.map(lambda c: gm[c]['unit_ts'])
inplay = av.timestamp >= unit
res['coverage_fills'] = float(inplay.mean())
res['coverage_usd'] = float(av[inplay].usdcSize.sum() / max(av.usdcSize.sum(), 1e-9))
res['wallet_prints_in_tape_vs_activity_fills'] = [int(len(w)), int(inplay.sum())]
# outcome: rule PnL vs wallet PnL per market
pay = {}
for c in V.cid.unique():
    op = gm[c].get('outcomePrices')
    try:
        op = [float(x) for x in (json.loads(op) if isinstance(op, str) else op)]
        if len(op) == 2 and max(op) > 0.99:
            pay[c] = op
    except Exception:
        pass
wp = {}
for r in av[av.conditionId.isin(pay)].itertuples(index=False):
    wp[r.conditionId] = wp.get(r.conditionId, 0.0) + float(r.size) * pay[r.conditionId][int(r.outcomeIndex)] - float(r.usdcSize)
rp, spent = {}, 0.0
for c, g in V[V.cid.isin(pay)].groupby('cid'):
    thr = np.quantile(g.s_full, 1 - fr.FLAG_TOP)
    fl = g[(g.s_full >= thr) & (~g.y) & (g.px >= fr.PNL_PRICE_RANGE[0]) & (g.px <= fr.PNL_PRICE_RANGE[1])]
    rp[c] = float(sum(fr.STAKE_USD / p * pay[c][int(k)] - fr.STAKE_USD for p, k in zip(fl.px, fl.tokidx)))
    spent += fr.STAKE_USD * len(fl)
cs = sorted(set(wp) & set(rp))
from scipy.stats import pearsonr, spearmanr
x, y = np.array([rp[c] for c in cs]), np.array([wp[c] for c in cs])
res.update({'pnl_markets': len(cs), 'pnl_corr_pearson': float(pearsonr(x, y)[0]), 'pnl_corr_spearman': float(spearmanr(x, y)[0]),
            'rule_return_on_flagged_other_prints': float(x.sum() / spent) if spent else None, 'wallet_pnl_sampled_markets': float(y.sum()),
            'wallet_return_sampled_markets': float(y.sum() / av[av.conditionId.isin(pay)].usdcSize.sum())})
json.dump(res, open(os.path.join(WS, 'results', 'iter2_val.json'), 'w'), indent=1)
for k, v in res.items():
    if k != 'importance_full':
        print(k, v)
print('importance_full', sorted(res['importance_full'].items(), key=lambda x: -x[1])[:10])
