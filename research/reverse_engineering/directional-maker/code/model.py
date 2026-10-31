"""Behaviour cloning of the cluster's BTC 5m maker fills: presence per
(window, side, 10-s bin), side given a fill, price, on BUILD -> VALIDATE.
No own-state features (the panel has none). Writes small results to
research/reverse_engineering/directional-maker/results_iter1.json and the
frozen LightGBM model to code/presence_model.txt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker"
RES = ROOT / "research/reverse_engineering/directional-maker"
BUILD = (1791504000, 1792108800)
VALID = (1792108800, 1792713600)

F_TIME = ["rel", "side_up"]
F_SPOT = ["fair_s", "z_s", "sig", "r1", "r2", "r3", "r5", "r10", "r30", "r60"]
F_TAPE = ["last_s", "edge_s", "n_prints"] + [f"{a}{k}" for a in ("hit_s", "hit_o", "vol_s", "vol_o", "dpx_s") for k in (10, 30, 60)]
F_ACT = ["rel", "n_prints"] + [f"{a}{k}" for a in ("hit_s", "hit_o", "vol_s", "vol_o") for k in (10, 30, 60)]
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=63, min_data_in_leaf=200, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=7, num_threads=2)
ROUNDS = 400


PARAMS_REG = dict(PARAMS, num_leaves=15, min_data_in_leaf=1000, learning_rate=0.03, lambda_l2=10.0)


def fit_eval(tr, va, feats, name):
    d = lgb.Dataset(tr[feats], tr["y"])
    m = lgb.train(PARAMS_REG, d, 300) if name.endswith("_reg") else lgb.train(PARAMS, d, ROUNDS)
    p = m.predict(va[feats])
    auc = roc_auc_score(va["y"], p)
    imp = dict(sorted(zip(feats, m.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:12])
    print(f"{name:10s} VALIDATE presence AUC {auc:.4f}  BUILD-fit AUC {roc_auc_score(tr['y'], m.predict(tr[feats])):.4f}")
    return m, p, auc, imp


def main():
    tr = pd.read_parquet(OUT / f"panel5_{BUILD[0]}_{BUILD[1]}.parquet")
    va = pd.read_parquet(OUT / f"panel5_{VALID[0]}_{VALID[1]}.parquet")
    # inside-window bins only (no fills before the start in BUILD)
    tr, va = tr[tr["rel"] >= 0].reset_index(drop=True), va[va["rel"] >= 0].reset_index(drop=True)
    for df in (tr, va):  # own inventory before the bin (own-state variant only)
        df.sort_values(["cid", "side_up", "rel"], inplace=True)
        df["inv_s"] = df.groupby(["cid", "side_up"])["y_sh"].cumsum() - df["y_sh"]
        o = df[["cid", "side_up", "rel", "inv_s"]].copy()
        o["side_up"] = 1 - o["side_up"]
        df["inv_o"] = df.merge(o.rename(columns={"inv_s": "inv_o"}), on=["cid", "side_up", "rel"], how="left")["inv_o"].to_numpy()
        df["inv_net"] = df["inv_s"] - df["inv_o"]
        df.reset_index(drop=True, inplace=True)
    print("rows", len(tr), len(va), "pos rate", round(tr["y"].mean(), 4), round(va["y"].mean(), 4))
    res = {"n_build": len(tr), "n_validate": len(va), "pos_rate_validate": float(va["y"].mean())}
    out = {}
    for name, feats in (("time", F_TIME), ("activity", F_ACT), ("spot", F_TIME + F_SPOT), ("tape", F_TIME + F_TAPE),
                        ("all", F_TIME + F_SPOT + F_TAPE), ("all_reg", F_TIME + F_SPOT + F_TAPE), ("activity_reg", F_ACT), ("all+own", F_TIME + F_SPOT + F_TAPE + ["inv_s", "inv_o", "inv_net"])):
        m, p, auc, imp = fit_eval(tr, va, feats, name)
        out[name] = {"auc": round(auc, 4), "importance": imp}
        if name in ("all", "all_reg", "activity", "activity_reg"):
            m.save_model(str(RES / f"code/presence_model_{name}.txt"))
        if name == "all":
            va["p_all"] = p
    res["presence"] = out
    # side given a fill: bins where the cluster fills exactly one side
    def side_rows(df):
        g = df.groupby(["cid", "rel"])
        k = g["y"].transform("sum")
        return df[(k == 1)]
    sv = side_rows(va)
    sv = sv.assign(pred=sv["p_all"])
    # for each such bin, the rule picks the side with the higher predicted presence
    piv = va.pivot_table(index=["cid", "rel"], columns="side_up", values="p_all")
    lab = va.pivot_table(index=["cid", "rel"], columns="side_up", values="y")
    one = lab[(lab.sum(axis=1) == 1)]
    pick_up = (piv.loc[one.index, 1] > piv.loc[one.index, 0]).astype(int)
    true_up = one[1].astype(int)
    acc = float((pick_up == true_up).mean())
    # market-only baseline: buy the favourite (last Up print > 0.5), and the contrarian of it
    lu = va[va["side_up"] == 1].set_index(["cid", "rel"])["last_s"].reindex(one.index)
    fav_up = (lu > 0.5).astype(int)
    acc_fav = float((fav_up == true_up).mean())
    fu = va[va["side_up"] == 1].set_index(["cid", "rel"])["fair_s"].reindex(one.index)
    acc_fair = float(((fu > 0.5).astype(int) == true_up).mean())
    print(f"side accuracy (bins with a one-sided fill, n={len(one)}): model {acc:.3f}  favourite-by-last-print {acc_fav:.3f}  binance-favourite {acc_fair:.3f}")
    res["side"] = {"n": int(len(one)), "model_acc": round(acc, 4), "fav_last_print_acc": round(acc_fav, 4), "binance_fav_acc": round(acc_fair, 4)}
    (RES / "results_iter1.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
