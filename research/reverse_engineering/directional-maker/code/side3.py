"""Iteration 3, family N5 (conditional side model) and an R2 capacity check.

Side: instead of comparing two presence scores, model the side directly: on BUILD bins where the cluster fills
exactly one side, LightGBM predicts P(fill side = Up) from the Up-side and Down-side public features of the bin
(and their differences). Evaluated on VALIDATE one-sided bins against the R2 presence comparison (0.679) and the
favourite baselines. Window level: dominant side of one-sided active windows from the mean conditional side
probability over the bins of the first T seconds (public features only).
Capacity: R2 features with more rounds / leaves (choice on VALIDATE only).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train2 import ACT, SPOT, PATH, XWIN, OWN, PARAMS, ROUNDS, auc, OUT, H, VAL0  # noqa: E402

R2 = ACT + SPOT + ["edge_s"] + PATH + XWIN
SIDE_FEATS = [c for c in R2 if c not in ("rel", "side_up")]


def load():
    fr = [pd.read_parquet(f) for f in sorted(OUT.glob("panel2_day_*.parquet"))]
    p = pd.concat(fr, ignore_index=True)
    return p[p["start_ts"] + 300 <= H].reset_index(drop=True)


def wide(p: pd.DataFrame) -> pd.DataFrame:
    up = p[p["side_up"] == 1].set_index(["cid", "rel"])
    dn = p[p["side_up"] == 0].set_index(["cid", "rel"])
    X = pd.DataFrame(index=up.index)
    X["start_ts"] = up["start_ts"]
    for c in SIDE_FEATS:
        X["u_" + c] = up[c]
        X["d_" + c] = dn[c].reindex(up.index)
    X["y_up"] = (up["y"] > 0).astype(int)
    X["y_dn"] = (dn["y"].reindex(up.index) > 0).astype(int)
    X["won_up"] = up["won_s"]
    for c in OWN:
        X["u_" + c] = up[c]
    return X.reset_index()


def main():
    p = load()
    X = wide(p)
    cols = ["rel"] + [c for c in X.columns if c.startswith(("u_", "d_")) and not c.endswith(("inv_s", "inv_o"))]
    one = (X["y_up"] + X["y_dn"]) == 1
    b = one & (X["start_ts"] < VAL0)
    v = one & (X["start_ts"] >= VAL0)
    prm = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=100, feature_fraction=0.8,
               bagging_fraction=0.8, bagging_freq=1, lambda_l2=10.0, max_bin=63, verbose=-1, seed=7, num_threads=2)
    res = {"n_build_one_sided": int(b.sum()), "n_val_one_sided": int(v.sum())}
    for name, rounds in (("side_cond_300", 300), ("side_cond_600", 600)):
        m = lgb.train(prm, lgb.Dataset(X.loc[b, cols], X.loc[b, "y_up"]), rounds)
        pv = m.predict(X.loc[v, cols])
        yv = X.loc[v, "y_up"].to_numpy()
        acc = float(np.mean((pv > 0.5) == yv))
        fav = (X.loc[v, "u_last_s"].fillna(0.5) > 0.5).to_numpy()
        dis = (pv > 0.5) != fav
        k = int(np.sum(((pv > 0.5) == yv) & dis))
        conf = np.abs(pv - 0.5)
        q75, q90 = np.quantile(conf, 0.75), np.quantile(conf, 0.90)
        rel = X.loc[v, "rel"].to_numpy()
        res[name] = {"acc": acc, "auc": auc(yv, pv), "fav": float(np.mean(fav == yv)),
                     "p_vs_fav": float(stats.binomtest(k, int(dis.sum()), 0.5, alternative="greater").pvalue),
                     "acc_0_30": float(np.mean(((pv > 0.5) == yv)[rel < 30])),
                     "acc_top25": float(np.mean(((pv > 0.5) == yv)[conf >= q75])),
                     "acc_top10": float(np.mean(((pv > 0.5) == yv)[conf >= q90])),
                     "imp": dict(sorted(zip(cols, m.feature_importance("gain").round(0).tolist()), key=lambda t: -t[1])[:10])}
        if name == "side_cond_300":
            m.save_model(str(HERE / "side3_cond.txt"))
            # window level: dominant side of one-sided active windows from the mean P(up) over all bins before T
            Xa = X[X["start_ts"] >= VAL0].copy()
            Xa["pu"] = m.predict(Xa[cols])
            g = p[(p["start_ts"] >= VAL0)].groupby(["cid", "side_up"])["y"].sum().unstack(fill_value=0)
            # share of fill BINS on Up as the window's side label (>= 70% one side)
            frac = g[1] / (g[0] + g[1]).replace(0, np.nan)
            lab = frac[(frac >= 0.7) | (frac <= 0.3)]
            wl = {}
            for T in (30, 60, 120):
                mu = Xa[Xa["rel"] < T].groupby("cid")["pu"].mean()
                ix = lab.index.intersection(mu.index)
                wl[f"T{T}"] = {"acc": float(np.mean((mu[ix] > 0.5) == (lab[ix] >= 0.7))), "n": int(len(ix))}
            res["window_side_from_cond"] = wl
        print(name, json.dumps({k: v_ for k, v_ in res[name].items() if k != "imp"}), flush=True)
    # R2 capacity check (presence AUC on VALIDATE)
    bb = p[p["start_ts"] < VAL0]
    vv = p[p["start_ts"] >= VAL0]
    cap = {}
    for tag, upd, rounds in (("r2_300_15", {}, 300), ("r2_800_15", {}, 800), ("r2_500_31", {"num_leaves": 31}, 500),
                             ("r2_600_7", {"num_leaves": 7}, 600)):
        prm2 = dict(PARAMS, **upd)
        m = lgb.train(prm2, lgb.Dataset(bb[R2], bb["y"]), rounds)
        cap[tag] = auc(vv["y"], m.predict(vv[R2]))
        print(tag, round(cap[tag], 4), flush=True)
    res["capacity"] = cap
    print(json.dumps(res.get("window_side_from_cond")))
    (HERE.parent / "results_iter3_side.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
