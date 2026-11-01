"""Iteration 2 (late): side models with PIT Binance USD-M futures features (aggTrades of the day, trades with
T < (s-1)*1000 only; Up-oriented), BUILD days with futures -> VALIDATE days with futures, one-sided seconds."""
import os, sys, glob, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
from side_study import one_sided
from cells import FEATS
from tape_feats import TAPE_FEATS
from build_cells_day import EXTRA
from ofi import Agg, OFI_FEATS
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"; V0 = 1792108800
days = sorted(int(os.path.basename(f)[:-8]) for f in glob.glob(f"{C}/fut/*.parquet"))
parts = []
for d0 in days:
    D = one_sided([f"{C}/cells/{d0}.parquet"], ["y", "yT"])
    D["s"] = (D.start_ts + D.rel).astype(np.int64)
    D = D[(D.s - 12 >= d0) & (D.s < d0 + 86400)].reset_index(drop=True)
    a = Agg(pd.read_parquet(f"{C}/fut/{d0}.parquet"))
    f = a.feats((D.s.to_numpy() - 1) * 1000)
    for k in OFI_FEATS:
        D["F_" + k] = f[k].astype(np.float32)
    D["F_basis3"] = D["F_pm3000"] - D["r3"]  # futures 3-s move minus spot kline move (both PIT, Up-oriented)
    parts.append(D)
D = pd.concat(parts, ignore_index=True)
FUT = ["F_" + k for k in OFI_FEATS] + ["F_basis3"]
TAPE = TAPE_FEATS + EXTRA + [c for c in D.columns if c.startswith("D_")]
params = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, verbose=-1, num_threads=3, max_bin=63)
res = {"days_build": [d for d in days if d < V0], "days_val": [d for d in days if d >= V0]}
for lab in ("y", "yT"):
    d = D[D[f"{lab}_one"]]; t = d[f"{lab}_up"].to_numpy().astype(int); v = d.s.to_numpy() >= V0
    quiet = np.abs(d.r3.to_numpy()) < 0.01
    r = {"n_build": int((~v).sum()), "n_val": int(v.sum())}
    for nm, fs in [("spot_tape", FEATS + TAPE), ("spot_tape_futures", FEATS + TAPE + FUT), ("futures_only", ["rel", "tau"] + FUT)]:
        m = lgb.train(params, lgb.Dataset(d[fs][~v], t[~v]), 300)
        p = m.predict(d[fs][v]); ok = (p >= 0.5) == t[v]
        imp = sorted(zip(fs, m.feature_importance("gain")), key=lambda q: -q[1]); tot = sum(x for _, x in imp)
        r[nm] = {"acc": round(float(ok.mean()), 4), "acc_spot_r3_zero": round(float(ok[quiet[v]].mean()), 4), "top": [(k, round(float(x / tot), 3)) for k, x in imp[:6]]}
        print(lab, nm, r[nm]["acc"], r[nm]["acc_spot_r3_zero"], flush=True)
    res[lab] = r
json.dump(res, open(f"{R}/results_futures_side_iter2.json", "w"), indent=1)
