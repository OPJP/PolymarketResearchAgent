"""Iteration 15, information P2 (X140) steps 3-4, compact: does a per-wallet information clock make the carrying wallet predictable?
First legs (rank 0) of the operator's taker decisions, 10-17..22 (dcclock14_frame). Target: wallet == XM (and DS, GF one-vs-rest).
Feature sets (all PIT-clean: every spot window ends at or before m0 - 260 ms exchange time, the bot's physical horizon):
  base   : rel, hour, window index mod 4, |p - 0.5| (others' last Polymarket price at the decision), own-anchor tick strength
  clock  : base + the 250-ms microprice return windows ending c = 400..260 ms before m0 (k400..k260, toward the outcome), the
           decision-anchor returns over 100..2000 ms (dec_bs_mic_*, dec_bt_*), their ratios (persistence: k340 / k260, k300 / k260)
  post   : clock + k250..k150 (AFTER the horizon; mechanism probe only, not PIT)
LightGBM (binary, 300 rounds, dcside13 params), fit 10-17..19, scored once on 10-20..22; AUC per target and set. Then thin14's redraw
ceiling for XM's window PnL recomputed with the clock model's P^(XM): corr between two redraws and redraw vs true.
Usage: python -I xmclock15.py IT14_DIR OUT.json"""
import sys, json
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score

D14, OUT = sys.argv[1], sys.argv[2]
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=15)
KPRE = [f"k{c}" for c in range(400, 250, -10)]
KPOST = [f"k{c}" for c in range(250, 140, -10)]
DEC = [f"dec_bs_mic_{K}" for K in (100, 250, 500, 1000, 2000)] + [f"dec_bt_{K}" for K in (100, 250, 500, 1000, 2000)]
d = pd.read_parquet(f"{D14}/dcclock14_frame.parquet", columns=["cid", "wallet", "up", "m", "m0", "rank", "start_ts", "day", "rel", "dec_pm_last", "dec_pm_dist", "own_bs_mic_250"] + KPRE + KPOST + DEC)
d = d[d["rank"] == 0].copy()
d["hour"] = (d.m0 // 1000 % 86400) // 3600
d["k4"] = (d.start_ts // 300) % 4
d["pdist"] = d.dec_pm_dist
d["tick"] = d.own_bs_mic_250.abs()
eps = 1e-6
d["pers340"] = d.k340 / (d.k260.abs() + eps); d["pers300"] = d.k300 / (d.k260.abs() + eps)
BASE = ["rel", "hour", "k4", "pdist", "tick"]
SETS = {"base": BASE, "clock": BASE + KPRE + DEC + ["pers340", "pers300"], "post": BASE + KPRE + DEC + ["pers340", "pers300"] + KPOST}
fit = d.start_ts < 1792454400; sc = ~fit
rep = {"n_fit": int(fit.sum()), "n_score": int(sc.sum()), "share": d[sc].wallet.value_counts(normalize=True).round(4).to_dict()}
P = {}
for tgt in ("XM", "DS", "GF"):
    y = (d.wallet == tgt).astype(int).to_numpy()
    for nm, cols in SETS.items():
        m = lgb.train(PARAMS, lgb.Dataset(d.loc[fit, cols], y[fit.to_numpy()]), 300)
        p = m.predict(d.loc[sc, cols])
        rep[f"auc_{tgt}_{nm}"] = round(float(roc_auc_score(y[sc.to_numpy()], p)), 4)
        P[(tgt, nm)] = p
        if tgt == "XM" and nm == "clock":
            imp = pd.Series(m.feature_importance("gain"), index=cols); rep["xm_clock_top"] = (imp / imp.sum()).sort_values(ascending=False).head(8).round(3).to_dict()
print(json.dumps(rep, indent=1), flush=True)
json.dump(rep, open(OUT, "w"), indent=1)
