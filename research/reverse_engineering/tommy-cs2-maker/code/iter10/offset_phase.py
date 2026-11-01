"""X134 (information panel iter-9 P3), historical ceiling: does message PHASE / INTENSITY on the feed's own clock
explain the wallet's price offset? Rows = its filled maker orders 16-22 Oct (message_ledger.py ->
ledger_rows_iter10.parquet). Target = price - last public print on the token (cents). Regressors (descriptive ceiling,
the clock is the wallet-independent subscriber clock at its TRUE signing times, i.e. not point-in-time):
  order class (msg / follow / quiet / own_msg / repair), log time since the last message, log time since its own last
  take, messages in the last 5 / 30 s, price-level bins, match vs map unknown here (per-cid fixed effects NOT used).
Fit on BUILD (game start < 10-21), score on VALIDATE: R^2 of the offset, and within one tick of
round(last print + fitted offset) vs the last print alone. A LightGBM version gives the non-linear ceiling.
Output: results/offset_phase.json
"""
import json
import numpy as np, pandas as pd

ROOT = '.cache/re/tommy-cs2-maker'
OUT = 'research/reverse_engineering/tommy-cs2-maker/results/offset_phase.json'
VAL0 = 1792540800
X = pd.read_parquet(f'{ROOT}/ledger_rows_iter10.parquet')
X = X[np.isfinite(X.a_last)].copy()
X['off'] = (X.price - X.a_last) * 100
X = X[np.abs(X.off) <= 30]


def feats(d):
    F = pd.DataFrame(index=d.index)
    for c in ('msg', 'follow', 'quiet', 'own_msg', 'repair'):
        F[c] = (d.cls == c).astype(float)
    F['ldm'] = np.log1p(np.minimum(d.dmsg, 3.6e6) / 1000)
    F['ldo'] = np.log1p(np.minimum(d.down, 3.6e6) / 1000)
    F['n5'] = np.log1p(d.n5); F['n30'] = np.log1p(d.n30)
    for lo, hi in ((0, .15), (.15, .3), (.3, .5), (.5, .7), (.7, .85), (.85, 1.01)):
        F[f'lv{lo}'] = ((d.a_last >= lo) & (d.a_last < hi)).astype(float)
    return F

B, V = X[X.gs_ts < VAL0], X[X.gs_ts >= VAL0]
FB, FV = feats(B), feats(V)
A = np.column_stack([FB.to_numpy(), np.ones(len(FB))])
coef, *_ = np.linalg.lstsq(A, B.off.to_numpy(), rcond=None)
pv = np.column_stack([FV.to_numpy(), np.ones(len(FV))]) @ coef
pb = A @ coef


def r2(y, p):
    return round(float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)), 4)


def wt(d, p):
    a = d.a_last.to_numpy(float)
    pr = np.round(a + np.round(p) / 100, 2)
    tick = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
    return round(float((np.abs(d.price.to_numpy(float) - pr) <= tick + 1e-9).mean()), 3)

res = {'n_build': int(len(B)), 'n_validate': int(len(V)),
       'linear': {'r2_build': r2(B.off.to_numpy(), pb), 'r2_validate': r2(V.off.to_numpy(), pv),
                  'within_tick_validate': wt(V, pv), 'within_tick_last_print_validate': wt(V, np.zeros(len(V))),
                  'within_tick_last_minus_1c_validate': wt(V, -np.ones(len(V))),
                  'coef': dict(zip(list(FB.columns) + ['icpt'], [round(float(c), 3) for c in coef]))},
       'offset_sd_c_validate': round(float(V.off.std()), 2)}
try:
    import lightgbm as lgb
    m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=15, max_bin=63, min_child_samples=50, verbose=-1)
    m.fit(FB, B.off)
    pg = m.predict(FV)
    res['lgbm'] = {'r2_validate': r2(V.off.to_numpy(), pg), 'within_tick_validate': wt(V, pg),
                   'importance': dict(zip(FB.columns, [int(v) for v in m.feature_importances_]))}
    # residual SD
    res['lgbm']['resid_sd_c_validate'] = round(float(np.std(V.off.to_numpy() - pg)), 2)
except Exception as e:  # noqa: BLE001
    res['lgbm'] = str(e)
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps(res, indent=1))
