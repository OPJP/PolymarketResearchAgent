"""H1 on BTC 5m: reference-clock-shift null (fast) and extended delta grid with at-touch bound.
Also persists the 15m numbers printed by h1b.py (that run was stopped before it reached json.dump)."""
import sys, json, pickle
sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
from common import *
from feats import implied_up_series
from tapemaker_vec import tape_maker_vec

S = '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
res = json.load(open(S + 'h1_tapemaker_results.json'))
res['15m']['match_test_reference_shift_null'] = {'auc': 0.5726, 'null_mean': 0.5257, 'null_p95': 0.5838, 'perm_p': 0.1393, 'shift_range_s': [60, 600]}
res['15m']['prem_quantiles'] = {'wallet': [-0.35, -0.07, -0.02, 0.02, 0.17], 'others': [-0.29, -0.09, -0.01, 0.062, 0.26]}
res['15m']['ext_grid_at_touch_False'] = {'fit_best': {'latency': 5, 'delta': 0.2, 'fills': 116, 'pnl': -61.0639, 'per_market_t': -0.7365},
                                         'test': {'fills': 198, 'pnl': -91.2136, 'return_on_bought': -0.0585, 'per_market_p': 0.7675, 'per_market_bootstrap_p': 0.7631}}
res['15m']['ext_grid_at_touch_True'] = {'fit_best': {'latency': 2, 'delta': 0.2, 'fills': 105, 'pnl': -60.842, 'per_market_t': -0.8316},
                                        'test': {'fills': 172, 'pnl': -111.687, 'return_on_bought': -0.0809, 'per_market_p': 0.8655, 'per_market_bootstrap_p': 0.8711}}
res['15m']['vectorized_equivalence_check'] = {'vec_pnl': -1117.4273, 'repo_pnl': -1117.4273, 'fills': [1082, 1082]}
json.dump(res, open(S + 'h1_tapemaker_results.json', 'w'), indent=1, default=float)

dur = '5m'
lo, hi = 30, 240
P = pickle.load(open(S + f'period_btc_{dur}.pkl', 'rb'))
testm = pd.read_pickle(S + f'mk_{dur}_test_L2.pkl').reset_index(drop=True)
tf = pd.read_pickle(S + f'flow_{dur}_test.pkl')
ff = pd.read_pickle(S + f'flow_{dur}_fit.pkl')
ser = implied_up_series(tf)
cids = testm.condition_id.to_numpy()
order = np.argsort(cids, kind='stable')
uniq, starts = np.unique(cids[order], return_index=True)
bounds = list(starts) + [len(order)]
groups = [(order[bounds[i]:bounds[i + 1]], ser.get(c)) for i, c in enumerate(uniq)]
ts_all = testm.ts.to_numpy().astype(np.int64)
isup = testm.is_up.to_numpy()
price = testm.price.to_numpy()


def prem(L, shift=0):
    out = np.full(len(testm), np.nan)
    for idx, s in groups:
        if s is None:
            continue
        sts, up = s
        i = np.searchsorted(sts, ts_all[idx] + shift - L + 1, side='left') - 1
        out[idx] = np.where(i >= 0, up[np.clip(i, 0, None)], np.nan)
    return price - np.where(isup, out, 1 - out)


L = res[dur]['match_choice']['L']
d = res[dur]['match_choice']['delta']
y = testm.y.to_numpy()
a = auc(-np.abs(prem(L) + d), y)
rng = np.random.default_rng(11)
null = []
for _ in range(200):
    sh = int(rng.integers(lo, hi)) * int(rng.choice([-1, 1]))
    null.append(auc(-np.abs(prem(L, sh) + d), y))
null = np.array([x for x in null if np.isfinite(x)])
rc = {'auc': a, 'null_mean': float(null.mean()), 'null_p95': float(np.percentile(null, 95)), 'perm_p': permutation_pvalue(a, null), 'shift_range_s': [lo, hi]}
print(dur, 'reference-clock-shift null:', rc, flush=True)
res[dur]['match_test_reference_shift_null'] = rc
pr = prem(L)
res[dur]['prem_quantiles'] = {'wallet': np.nanpercentile(pr[y == 1], [5, 25, 50, 75, 95]).round(3).tolist(),
                              'others': np.nanpercentile(pr[y == 0], [5, 25, 50, 75, 95]).round(3).tolist()}
print(res[dur]['prem_quantiles'], flush=True)
json.dump(res, open(S + 'h1_tapemaker_results.json', 'w'), indent=1, default=float)

ext = {}
for at in (False, True):
    for lat in (2, 5):
        for dl in (0.0, 0.02, 0.05, 0.08, 0.12, 0.16, 0.20):
            r = tape_maker_vec(ff, P['fit']['windows'], dl, lat, at_touch=at)
            r.pop('_fills', None)
            ext[(at, lat, dl)] = r
for at in (False, True):
    cand = {k: v for k, v in ext.items() if k[0] == at and v.get('fills', 0) >= 30}
    best = max(cand, key=lambda k: cand[k]['per_market_t'])
    te = tape_maker_vec(tf, P['test']['windows'], best[2], best[1], at_touch=at)
    te.pop('_fills', None)
    print(f'at_touch={at} FIT best lat={best[1]} delta={best[2]}', {k: cand[best][k] for k in ('fills', 'pnl', 'return_on_bought', 'per_market_t')},
          'TEST', {k: te[k] for k in ('fills', 'pnl', 'return_on_bought', 'per_market_t', 'per_market_p', 'per_market_bootstrap_p')}, flush=True)
    res[dur][f'ext_grid_at_touch_{at}'] = {'fit_best': {'latency': best[1], 'delta': best[2], **cand[best]}, 'test': te,
                                           'fit_all': {f'lat={k[1]},d={k[2]}': {kk: v.get(kk) for kk in ('fills', 'pnl', 'per_market_t')} for k, v in ext.items() if k[0] == at}}
json.dump(res, open(S + 'h1_tapemaker_results.json', 'w'), indent=1, default=float)
print('done')
