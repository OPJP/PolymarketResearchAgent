"""Iteration 1: presence model spot+tape PIT features (others' prints only; no own-state). BUILD -> VALIDATE."""
import os as _os; _ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))  # repo root
import sys, os, time, json
sys.path.insert(0, _ROOT + "/research/reverse_engineering/btc5m-bot/code")
import numpy as np, pandas as pd
from spot import Spot
from cells import build_cells, FEATS
from tape_feats import add_tape_feats, TAPE_FEATS
from sklearn.metrics import roc_auc_score
import lightgbm as lgb
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot"
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
params = dict(objective="binary", learning_rate=0.05, num_leaves=127, min_data_in_leaf=300, feature_fraction=0.8, bagging_fraction=0.5, bagging_freq=1, verbose=-1, num_threads=3)
ALL = FEATS + TAPE_FEATS
res = {"n_build_windows": int(len(wb)), "n_val_windows": int(len(wv))}
for name, feats in (("spot_only", FEATS), ("spot_tape", ALL), ("tape_only", ["rel", "tau"] + TAPE_FEATS)):
    for lab in (["y", "yT", "yM"] if name != "tape_only" else ["y"]):
        m = lgb.train(params, lgb.Dataset(cb[feats], cb[lab]), num_boost_round=400)
        p = m.predict(cv[feats])
        imp = sorted(zip(feats, m.feature_importance("gain")), key=lambda t: -t[1]); tot = sum(v for _, v in imp)
        res[f"{name}:{lab}"] = {"auc": round(float(roc_auc_score(cv[lab], p)), 4), "top_gain_share": [(a, round(float(b / tot), 3)) for a, b in imp[:12]]}
        print(name, lab, res[f"{name}:{lab}"], flush=True)
        if name == "spot_tape" and lab == "y":
            m.save_model(f"{R}/code/model_spot_tape_y.txt")
            cv["p"] = p
        if name == "spot_tape" and lab in ("yT", "yM"):
            m.save_model(f"{R}/code/model_spot_tape_{lab}.txt")
for w in ["yGF", "yXM", "yDS"]:
    res[f"spot_tape(y-model):{w}"] = round(float(roc_auc_score(cv[w], cv.p)), 4)
print({k: v for k, v in res.items() if k.startswith("spot_tape(")})
json.dump(res, open(f"{R}/results_tape_model.json", "w"), indent=1)
cv[["cid", "start_ts", "is_up", "rel", "y", "yT", "yM", "yGF", "yXM", "yDS", "p", "ask_o", "m_last", "fv"]].to_parquet(f"{C}/val_pred_tape.parquet", index=False)
print("elapsed", round(time.time() - t0))
