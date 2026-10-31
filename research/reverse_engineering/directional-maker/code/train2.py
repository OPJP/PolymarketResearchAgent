"""Iteration 2: train presence models on BUILD clean panels, compare on VALIDATE.

python code/train2.py [save]   prints a JSON summary; with 'save' writes the chosen models next to this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / ".cache/re/directional-maker"
H = 1792713600
VAL0 = 1792108800

TIME = ["rel", "side_up"]
ACT = ["rel", "side_up", "n_prints", "n_in", "last_s", "big60", "ntak60", "prev_n"] + [
    f"{a}{k}" for a in ("hit_s", "hit_o", "vol_s", "vol_o", "dpx_s") for k in (10, 30, 60)]
SPOT = ["fair_s", "z_s", "sig", "r1", "r2", "r3", "r5", "r10", "r30", "r60"]
PATH = ["e_open_s", "emax_s", "emean_s", "epos_s", "f10_s", "z10_s"]
XWIN = ["prev_same", "strike_move_s"]
OWN = ["inv_s", "inv_o"]
SETS = {
    "time": TIME,
    "activity": ACT,
    "spot": TIME + SPOT,
    "all_v1": ACT + SPOT + ["edge_s"],
    "all_path": ACT + SPOT + ["edge_s"] + PATH,
    "all_path_xwin": ACT + SPOT + ["edge_s"] + PATH + XWIN,
    "all_path_xwin+own": ACT + SPOT + ["edge_s"] + PATH + XWIN + OWN,
    "activity+own": ACT + OWN,
}
PARAMS = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=1000, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=10.0, max_bin=63, verbose=-1, seed=7, num_threads=2)
ROUNDS = 300


def load():
    fr = [pd.read_parquet(f) for f in sorted(OUT.glob("panel2_day_*.parquet"))]
    p = pd.concat(fr, ignore_index=True)
    p = p[p["start_ts"] + 300 <= H]
    p["inv_net"] = p["inv_s"] - p["inv_o"]
    return p[p["start_ts"] < VAL0].reset_index(drop=True), p[p["start_ts"] >= VAL0].reset_index(drop=True)


def auc(y, s):
    y = np.asarray(y)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else float("nan")


def side_metrics(v: pd.DataFrame, col: str) -> dict:
    key = ["cid", "rel"]
    up = v[v["side_up"] == 1].set_index(key)
    dn = v[v["side_up"] == 0].set_index(key)
    lab = (up["y"] > 0).astype(int) - (dn["y"] > 0).astype(int)
    one = lab[lab != 0].index
    true_up = (lab.loc[one] > 0).to_numpy()
    pick = (up.loc[one, col] > dn.loc[one, col]).to_numpy()
    fav = (up.loc[one, "last_s"].fillna(0.5) > 0.5).to_numpy()
    bfav = (up.loc[one, "fair_s"] > 0.5).to_numpy()
    dis = pick != fav
    k = int(np.sum((pick == true_up) & dis))
    p = float(stats.binomtest(k, int(dis.sum()), 0.5, alternative="greater").pvalue) if dis.sum() else float("nan")
    return {"n": int(len(one)), "acc": float(np.mean(pick == true_up)), "fav_last_print": float(np.mean(fav == true_up)),
            "binance_fav": float(np.mean(bfav == true_up)), "p_vs_fav": p}


def main(save: bool) -> None:
    b, v = load()
    res = {"n_build": len(b), "n_val": len(v), "pos_build": float(b["y"].mean()), "pos_val": float(v["y"].mean()),
           "build_windows": int(b["cid"].nunique()), "val_windows": int(v["cid"].nunique()), "models": {}}
    act_w = v.groupby("cid")["y"].transform("max") > 0
    for name, feats in SETS.items():
        m = lgb.train(PARAMS, lgb.Dataset(b[feats], b["y"]), ROUNDS)
        v["p_" + name] = m.predict(v[feats])
        imp = dict(sorted(zip(feats, m.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:10])
        day = v.assign(d=v["start_ts"] // 86400).groupby("d").apply(lambda g: auc(g["y"], g["p_" + name]))
        res["models"][name] = {"auc": auc(v["y"], v["p_" + name]), "auc_active_windows": auc(v.loc[act_w, "y"], v.loc[act_w, "p_" + name]),
                               "daily": [round(x, 3) for x in day.tolist()], "imp": imp}
        if save:
            m.save_model(str(HERE / f"presence2_{name}.txt"))
        print(name, round(res["models"][name]["auc"], 4), flush=True)
    for name in ("all_v1", "all_path", "all_path_xwin", "all_path_xwin+own"):
        res["models"][name]["side"] = side_metrics(v, "p_" + name)
    # window-level on/off from the mean predicted presence in the first 60 s (public part only)
    wv = v[v["rel"] < 60].groupby("cid").agg(y=("y", "max"), p=("p_all_path_xwin", "mean"))
    wa = v.groupby("cid").agg(active=("y", "max"))
    res["window_on_off_auc_first60s_mean_p"] = auc(wa.loc[wv.index, "active"], wv["p"])
    res["val_active_share"] = float(wa["active"].mean())
    res["build_active_share"] = float(b.groupby("cid")["y"].max().mean())
    v[["cid", "start_ts", "rel", "side_up", "y", "last_s", "fair_s", "won_s"] + [c for c in v.columns if c.startswith("p_")]].to_parquet(
        OUT / "val_scores2.parquet", index=False)
    print(json.dumps(res, indent=1, default=str))
    (HERE.parent / "results_iter2_presence.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main(len(sys.argv) > 1 and sys.argv[1] == "save")
