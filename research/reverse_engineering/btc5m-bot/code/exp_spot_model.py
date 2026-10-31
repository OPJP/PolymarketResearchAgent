"""Iteration 1 experiment: presence model with spot-only PIT features (no own-state). BUILD -> VALIDATE."""
import sys, time, json
sys.path.insert(0, "/home/user/PolymarketResearchAgent/research/reverse_engineering/btc5m-bot/code")
import numpy as np, pandas as pd
from spot import Spot
from cells import build_cells, FEATS
from sklearn.metrics import roc_auc_score
import lightgbm as lgb
C = "/home/user/PolymarketResearchAgent/.cache/re/btc5m-bot"
R = "/home/user/PolymarketResearchAgent/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600
B0 = 1790899200 + 3600  # first BUILD window start (spot vol lookback available)
t0 = time.time()
sp = Spot()
f = pd.read_parquet(f"{C}/fills.parquet")
win = pd.read_parquet(f"{C}/windows.parquet")
wb = win[(win.start_ts >= B0) & (win.start_ts < V0)]
wv = win[(win.start_ts >= V0) & (win.end_ts <= V1)]
rng = np.random.default_rng(0)
cb = build_cells(wb, f, sp)
keep = (cb.y == 1) | (rng.random(len(cb)) < 0.35)
w_neg = 1 / 0.35
cb = cb[keep].reset_index(drop=True)
wt = np.where(cb.y == 1, 1.0, w_neg)
cv = build_cells(wv, f, sp)
print("BUILD cells (subsampled)", len(cb), "VALIDATE cells", len(cv), "VAL base rate", round(cv.y.mean(), 4), round(time.time() - t0), flush=True)
params = dict(objective="binary", learning_rate=0.05, num_leaves=127, min_data_in_leaf=300, feature_fraction=0.9, bagging_fraction=0.5, bagging_freq=1, verbose=-1, num_threads=3)
res = {}
for lab in ["y", "yT", "yM", "yGF", "yXM", "yDS"]:
    wts = np.where(cb[lab] == 1, 1.0, np.where(cb.y == 1, 1.0, w_neg))
    m = lgb.train(params, lgb.Dataset(cb[FEATS], cb[lab], weight=wts), num_boost_round=400)
    p = m.predict(cv[FEATS])
    imp = sorted(zip(FEATS, m.feature_importance("gain")), key=lambda t: -t[1])
    tot = sum(v for _, v in imp)
    res[lab] = {"auc": round(float(roc_auc_score(cv[lab], p)), 4), "base_rate": round(float(cv[lab].mean()), 4), "top_gain_share": [(a, round(float(b / tot), 3)) for a, b in imp[:10]]}
    print(lab, res[lab], flush=True)
    if lab == "y":
        m.save_model(f"{C}/spot_model_y.txt")
        cv["p_spot"] = p
# per-day AUC on VALIDATE
cv["day"] = (cv.start_ts // 86400)
res["y_by_day"] = {int(d): round(float(roc_auc_score(g.y, g.p_spot)), 4) for d, g in cv.groupby("day")}
# window-level presence (does the cluster trade window at all)
res["n_build_windows"] = int(len(wb)); res["n_val_windows"] = int(len(wv))
json.dump(res, open(f"{R}/results_spot_model.json", "w"), indent=1)
cv[["cid", "is_up", "rel", "y", "yT", "yM", "p_spot"]].to_parquet(f"{C}/val_pred_spot.parquet", index=False)
print("elapsed", round(time.time() - t0))
