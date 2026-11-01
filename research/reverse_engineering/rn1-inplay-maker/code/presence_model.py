"""Presence models on the pre-registered cells: fit on BUILD, score VALIDATE; OOF residuals on BUILD (E2).

Feature sets: ACT (activity-only baseline), LIST (+ listing metadata), FULL (+ siblings, pair structure).
Gains with a 95% block bootstrap over games (events). Writes results/presence_iter1.json and the frozen models
in code/models/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, C, R, VALID  # noqa: E402
from presence import ACT, FULL, LIST, SPREAD  # noqa: E402

PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=40, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, max_bin=63, verbose=-1, seed=7, num_threads=2)
NROUND = 250
TAG = sys.argv[1] if len(sys.argv) > 1 else "run"
SETS = {"ACT": ACT, "LIST": ACT + LIST, "FULL": ACT + LIST + FULL, "ACT2": ACT + SPREAD, "FULL2": ACT + LIST + FULL + SPREAD}


def fit(X, y):
    return lgb.train(PARAMS, lgb.Dataset(X, y, free_raw_data=True), NROUND)


def boot_gain(y, s_base, s_new, groups, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    ug, inv = np.unique(groups, return_inverse=True)
    idx_by = [np.where(inv == g)[0] for g in range(len(ug))]
    out = []
    for _ in range(n):
        pick = rng.integers(0, len(ug), len(ug))
        ii = np.concatenate([idx_by[g] for g in pick])
        yy = y[ii]
        if yy.min() == yy.max():
            continue
        out.append(roc_auc_score(yy, s_new[ii]) - roc_auc_score(yy, s_base[ii]))
    out = np.array(out)
    return {"gain_ci95": [float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))], "p_gain_le_0": float((out <= 0).mean()),
            "n_boot": int(len(out))}


def main():
    b = pd.read_parquet(C / f"cells_{BUILD[0]}_{BUILD[1]}.parquet")
    v = pd.read_parquet(C / f"cells_{VALID[0]}_{VALID[1]}.parquet")
    res = {"n_build": int(len(b)), "n_validate": int(len(v)), "pos_build": float(b["y"].mean()), "pos_validate": float(v["y"].mean()),
           "events_build": int(b["event"].nunique()), "events_validate": int(v["event"].nunique())}
    scores = {}
    (R / "code" / "models" / TAG).mkdir(parents=True, exist_ok=True)
    for name, cols in SETS.items():
        m = fit(b[cols].astype("float32"), b["y"])
        s = m.predict(v[cols].astype("float32"))
        scores[name] = s
        res[f"auc_{name}"] = float(roc_auc_score(v["y"], s))
        imp = pd.Series(m.feature_importance("gain"), index=cols).sort_values(ascending=False)
        res[f"importance_{name}"] = {k: round(float(x), 1) for k, x in imp.head(12).items()}
        m.save_model(str(R / "code" / "models" / TAG / f"presence_{name}.txt"))
    g = v["event"].to_numpy()
    res["gain_FULL_vs_ACT"] = res["auc_FULL"] - res["auc_ACT"]
    res["boot_FULL_vs_ACT"] = boot_gain(v["y"].to_numpy(), scores["ACT"], scores["FULL"], g)
    res["gain_FULL2_vs_ACT2"] = res["auc_FULL2"] - res["auc_ACT2"]
    res["boot_FULL2_vs_ACT2"] = boot_gain(v["y"].to_numpy(), scores["ACT2"], scores["FULL2"], g)
    res["gain_FULL2_vs_ACT"] = res["auc_FULL2"] - res["auc_ACT"]
    res["boot_FULL2_vs_ACT"] = boot_gain(v["y"].to_numpy(), scores["ACT"], scores["FULL2"], g)
    res["gain_FULL_vs_LIST"] = res["auc_FULL"] - res["auc_LIST"]
    res["boot_FULL_vs_LIST"] = boot_gain(v["y"].to_numpy(), scores["LIST"], scores["FULL"], g)
    # per family on VALIDATE
    fam = {}
    for f, sub in v.assign(s=scores["FULL"], sa=scores["ACT"]).groupby("fam"):
        if sub["y"].nunique() == 2 and len(sub) > 200:
            fam[int(f)] = {"n": int(len(sub)), "pos": round(float(sub["y"].mean()), 3),
                           "auc_full": round(float(roc_auc_score(sub["y"], sub["s"])), 3),
                           "auc_act": round(float(roc_auc_score(sub["y"], sub["sa"])), 3)}
    res["by_family_validate"] = fam
    # E2: out-of-fold BUILD residuals (GroupKFold by game)
    oof = np.zeros(len(b))
    cols = SETS["FULL"]
    for tr, te in GroupKFold(5).split(b, b["y"], b["event"]):
        m = fit(b.iloc[tr][cols].astype("float32"), b.iloc[tr]["y"])
        oof[te] = m.predict(b.iloc[te][cols].astype("float32"))
    b = b.assign(oof=oof)
    res["oof_auc_build_FULL"] = float(roc_auc_score(b["y"], oof))
    b.to_parquet(C / f"oof_build_iter1_{TAG}.parquet", index=False)
    print(json.dumps(res, indent=1))
    json.dump(res, open(R / "results" / f"presence_iter1_{TAG}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
