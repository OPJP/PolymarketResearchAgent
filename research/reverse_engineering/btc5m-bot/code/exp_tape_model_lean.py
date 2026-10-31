"""Iteration 1 (lean): spot+tape PIT presence models for y, yT, yM; compares with the 14-day spot-only model on the same VALIDATE windows."""
import sys, os, time, json
sys.path.insert(0, "/home/user/PolymarketResearchAgent/research/reverse_engineering/btc5m-bot/code")
import numpy as np, pandas as pd
from spot import Spot
from cells import build_cells, FEATS
from tape_feats import add_tape_feats, TAPE_FEATS
from sklearn.metrics import roc_auc_score
import lightgbm as lgb
C = "/home/user/PolymarketResearchAgent/.cache/re/btc5m-bot"
R = "/home/user/PolymarketResearchAgent/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600
t0 = time.time()
sp = Spot()
f = pd.read_parquet(f"{C}/fills.parquet")
win = pd.read_parquet(f"{C}/windows.parquet")
has = lambda d: d[[os.path.exists(f"{C}/tapes/{c}.parquet") for c in d.cid]]
wb = has(win[(win.start_ts >= 1791504000) & (win.start_ts < V0)])
wv = has(win[(win.start_ts >= V0) & (win.end_ts <= V1)])
cb = add_tape_feats(build_cells(wb, f, sp), f, sp)
cv = add_tape_feats(build_cells(wv, f, sp), f, sp)
print("BUILD windows w/ tape", len(wb), "VALIDATE windows w/ tape", len(wv), round(time.time() - t0), flush=True)
params = dict(objective="binary", learning_rate=0.08, num_leaves=127, min_data_in_leaf=300, feature_fraction=0.8, bagging_fraction=0.5, bagging_freq=1, verbose=-1, num_threads=4)
ALL = FEATS + TAPE_FEATS
res = {"n_build_windows": int(len(wb)), "n_val_windows": int(len(wv))}
ps = pd.read_parquet(f"{C}/val_pred_spot.parquet")
cv = cv.merge(ps[["cid", "is_up", "rel", "p_spot"]], on=["cid", "is_up", "rel"], how="left")
res["spot14d:y_same_windows"] = round(float(roc_auc_score(cv.y, cv.p_spot)), 4)
print("14-day spot-only model on same VALIDATE windows", res["spot14d:y_same_windows"], flush=True)
for lab in ["y", "yT", "yM"]:
    m = lgb.train(params, lgb.Dataset(cb[ALL], cb[lab]), num_boost_round=250)
    p = m.predict(cv[ALL])
    imp = sorted(zip(ALL, m.feature_importance("gain")), key=lambda t: -t[1]); tot = sum(v for _, v in imp)
    res[f"spot_tape:{lab}"] = {"auc": round(float(roc_auc_score(cv[lab], p)), 4), "top_gain_share": [(a, round(float(b / tot), 3)) for a, b in imp[:14]]}
    print(lab, res[f"spot_tape:{lab}"], round(time.time() - t0), flush=True)
    m.save_model(f"{R}/code/model_spot_tape_{lab}.txt")
    cv[f"p_{lab}"] = p
for w in ["yGF", "yXM", "yDS"]:
    res[f"spot_tape(y-model):{w}"] = round(float(roc_auc_score(cv[w], cv.p_y)), 4)
from scipy.stats import rankdata
bl = rankdata(cv.p_y) + rankdata(cv.p_spot)
res["blend_rank_spot14d_spot_tape:y"] = round(float(roc_auc_score(cv.y, bl)), 4)
print(res, flush=True)
json.dump(res, open(f"{R}/results_tape_model.json", "w"), indent=1)
cv[["cid", "start_ts", "is_up", "rel", "y", "yT", "yM", "yGF", "yXM", "yDS", "p_y", "p_yT", "p_yM", "p_spot", "ask_o", "bid_o", "m_last", "fv", "flow5"]].to_parquet(f"{C}/val_pred_tape.parquet", index=False)
print("elapsed", round(time.time() - t0))
