"""Iteration 9: distil the public price-offset model (price_offset_model.py rows). Explicit candidates fitted on BUILD,
scored on VALIDATE (within one tick of the order price, in-play tick 1c):
  M1  k = round(a1 mom10 + a2 mom60 + a3 mom300) (OLS on BUILD, cents)
  M2  M1 + b * agg_buy_ours (last print was a taker buy of the token: bid sits below it)
  M3  M2 + level terms (lvl, lvl^2) + age term (log1p lp_age)
  M4  LightGBM on the 3 momentum features only (the gain of the trend alone)
Output: results/price_distill.json"""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"; RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
X = pd.read_parquet(OUT / "price_offset_rows.parquet")
b, v = X[X.split == "build"], X[X.split == "validate"]
def within(kp, kt): return float((np.abs(np.asarray(kp) - np.asarray(kt)) <= 1).mean())
res = {"last_print": within(np.zeros(len(v)), v.k)}
def design(d, terms):
    cols = [np.ones(len(d))]
    for t in terms:
        if t == "lvl2": cols.append(d.lvl.to_numpy() ** 2)
        elif t == "lage": cols.append(np.log1p(d.lp_age.to_numpy()))
        else: cols.append(d[t].to_numpy(float) * (100 if t.startswith("mom") else 1))
    return np.column_stack(cols)
for name, terms in (("M1", ["mom10", "mom60", "mom300"]), ("M2", ["mom10", "mom60", "mom300", "agg_buy_ours"]),
                    ("M3", ["mom10", "mom60", "mom300", "agg_buy_ours", "lvl", "lvl2", "lage"])):
    Zb, Zv = design(b, terms), design(v, terms)
    # least absolute deviations is closer to the within-one-tick target: IRLS for the median
    beta = np.linalg.lstsq(Zb, b.k.to_numpy(float), rcond=None)[0]
    for _ in range(30):
        r = np.abs(b.k.to_numpy(float) - Zb @ beta); w = 1 / np.maximum(r, 0.5)
        beta = np.linalg.lstsq(Zb * w[:, None] ** 0.5, b.k.to_numpy(float) * w ** 0.5, rcond=None)[0]
    kp = np.clip(np.round(Zv @ beta), -10, 3)
    res[name] = {"validate": within(kp, v.k), "coef": [round(float(c), 4) for c in beta], "terms": ["icpt"] + terms}
import lightgbm as lgb
classes = np.arange(-10, 4)
m = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15, max_bin=63, min_child_samples=100, verbose=-1)
f3 = ["mom10", "mom60", "mom300"]
m.fit(b[f3], b.k + 10)
P = np.zeros((len(v), len(classes))); P[:, m.classes_] = m.predict_proba(v[f3])
S = P.copy(); S[:, 1:] += P[:, :-1]; S[:, :-1] += P[:, 1:]
res["M4_gbm_momentum_only"] = within(classes[np.argmax(S, 1)], v.k)
# where does the gain sit: by last-print age and momentum sign
v2 = v.assign(mom_bin=pd.cut(v.mom300 * 100, [-100, -3, -1, 1, 3, 100]))
res["k_median_by_mom300_bin_validate"] = {str(k): float(g.k.median()) for k, g in v2.groupby("mom_bin", observed=True)}
print(json.dumps(res, indent=1)); json.dump(res, open(RES / "price_distill.json", "w"), indent=1)
