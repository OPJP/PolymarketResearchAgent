"""Iteration 2 selection test: which in-window taker prints fill a cluster maker order?

Population: every data-api taker print inside a BTC 5m window [start, end), except the cluster's own taker
prints. Label: the print's transaction contains a cluster maker fill. Each print hits the bid of one side s
(taker SELL s or taker BUY the complement) at maker price q.
Score: LightGBM fitted on BUILD prints on (a) the bin-level public panel row of (window, s, 10-s bin) that
contains the print (features published by the bin start, clean tape) and (b) print-level fields known at the
print: q, size, seconds into the window, taker direction, q minus the last clean print on s, Binance fair of s
from seconds published by ts-2 and fair - q. A market-activity-only model (no spot) is the co-occurrence baseline.
Test (VALIDATE): stratified AUC with match_test's strata (price 50 x time 40 x side; window x price 10 x time 10 x
side), recall/lift at the BUILD top-15% threshold, and a rotation null (each day's windows take the spot path of
the window k places later; bin-level spot columns and the print's fair are recomputed on that path).
Negatives are subsampled (BUILD 10%, VALIDATE 25%, fixed seed) with weights; AUCs are unbiased under it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa: E402
from panel2 import OUT, WALLETS, H, cluster_trades  # noqa: E402
from train2 import ACT, SPOT, PATH, XWIN  # noqa: E402

VAL0 = 1792108800
SPOTCOLS = SPOT + ["edge_s"] + PATH + XWIN
BINF = ACT + SPOTCOLS
PRINTF = ["q", "size_p", "rel_p", "taker_buy", "dq_last", "fair_p", "edge_p"]
F_ALL = BINF + PRINTF
F_ACT = ACT + ["q", "size_p", "rel_p", "taker_buy", "dq_last"]
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=500, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=10.0, max_bin=63, verbose=-1, seed=7, num_threads=2)


def day_prints(d: int, w: pd.DataFrame, sp: Spot, mk_tx: set, cw: set, neg_frac: float, rng, tk=None, pan=None):
    """Print table of one block (UTC day d). tk / pan default to the cached day files."""
    tk = pd.read_parquet(OUT / f"taker5m_day_{d}.parquet") if tk is None else tk
    pan = pd.read_parquet(OUT / f"panel2_day_{d}.parquet") if pan is None else pan
    wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)].sort_values("start_ts").reset_index(drop=True)
    pan = pan[pan["cid"].isin(set(wd["cid"]))]
    tk = tk[~tk["wallet"].isin(cw)].merge(wd[["cid", "start_ts", "end_ts", "up_token"]], on="cid")
    tk["y"] = tk["tx"].isin(mk_tx).astype(np.int8)
    is_up = tk["asset"].to_numpy() == tk["up_token"].to_numpy()
    buy = tk["side"].astype(str).to_numpy() == "BUY"
    up_px = np.where(is_up, tk["price"].to_numpy(), 1 - tk["price"].to_numpy())
    hit_up = (is_up & ~buy) | (~is_up & buy)
    tk["side_up"] = hit_up.astype(np.int8)
    tk["q"] = np.where(hit_up, up_px, 1 - up_px).astype(np.float32)
    tk["up_px"] = up_px
    tk["taker_buy"] = buy.astype(np.int8)
    tk["size_p"] = tk["size"].astype(np.float32)
    # last clean print (cluster tx removed) on the window strictly before the print
    tk["clean"] = tk["y"] == 0
    tk = tk.sort_values(["cid", "ts"], kind="stable").reset_index(drop=True)
    dq = np.full(len(tk), np.nan, np.float32)
    for cid, idx in tk.groupby("cid", sort=False).indices.items():
        g = tk.iloc[idx]
        c = g[g["clean"]]
        j = np.searchsorted(c["ts"].to_numpy(), g["ts"].to_numpy(), side="left") - 1
        lu = np.where(j >= 0, c["up_px"].to_numpy()[np.clip(j, 0, None)] if len(c) else np.nan, np.nan)
        ls = np.where(g["side_up"].to_numpy() == 1, lu, 1 - lu)
        dq[idx] = g["q"].to_numpy() - ls
    tk["dq_last"] = dq
    tk = tk[(tk["ts"] >= tk["start_ts"]) & (tk["ts"] < tk["end_ts"])]
    keep = (tk["y"] == 1) | (rng.random(len(tk)) < neg_frac)
    tk = tk[keep].copy()
    tk["wt"] = np.where(tk["y"] == 1, 1.0, 1.0 / neg_frac).astype(np.float32)
    tk["rel_p"] = (tk["ts"] - tk["start_ts"]).astype(np.int32)
    tk["rel"] = (tk["rel_p"] // 10 * 10).astype(np.int32)
    tk["widx"] = tk["cid"].map(dict(zip(wd["cid"], range(len(wd))))).astype(np.int32)
    f, _ = fair_up(sp, tk["start_ts"].to_numpy(), tk["end_ts"].to_numpy(), tk["ts"].to_numpy() - 2)
    tk["fair_p"] = np.where(tk["side_up"] == 1, f, 1 - f).astype(np.float32)
    tk["edge_p"] = tk["fair_p"] - tk["q"]
    pan = pan.drop(columns=["y"], errors="ignore")
    cols = ["cid", "rel", "side_up"] + [c for c in BINF if c not in ("rel", "side_up")]
    tk = tk.merge(pan[cols], on=["cid", "rel", "side_up"], how="left")
    tk["day"] = d
    return tk[["cid", "widx", "day", "start_ts", "end_ts", "ts", "y", "wt"] + [c for c in dict.fromkeys(F_ALL)]], pan, wd


def rotated(tk: pd.DataFrame, pan: pd.DataFrame, wd: pd.DataFrame, sp: Spot, k: int) -> pd.DataFrame:
    n = len(wd)
    r = tk.copy()
    sh = k * 300
    widx2 = (r["widx"].to_numpy() + k) % n
    shift = (widx2 - r["widx"].to_numpy()) * 300
    f, _ = fair_up(sp, r["start_ts"].to_numpy() + shift, r["end_ts"].to_numpy() + shift, r["ts"].to_numpy() - 2 + shift)
    r["fair_p"] = np.where(r["side_up"] == 1, f, 1 - f).astype(np.float32)
    r["edge_p"] = r["fair_p"] - r["q"]
    cid2 = wd["cid"].to_numpy()[widx2]
    sc = [c for c in SPOTCOLS if c != "edge_s"]
    rp = pan[["cid", "rel", "side_up", "fair_s"] + [c for c in sc if c != "fair_s"]].rename(columns={"cid": "cid2"})
    r = r.drop(columns=sc).assign(cid2=cid2).merge(rp, on=["cid2", "rel", "side_up"], how="left")
    r["edge_s"] = r["fair_s"] - r["last_s"]
    del sh
    return r


def strata(df: pd.DataFrame, npb: int, ntb: int, by_window: bool) -> np.ndarray:
    pr = df["q"].to_numpy()
    edges = np.unique(np.quantile(pr, np.linspace(0, 1, npb + 1)[1:-1]))
    pb = np.searchsorted(edges, pr, side="right")
    tb = np.floor(df["rel_p"].to_numpy() / 300 * ntb).astype(int)
    cols = [pb, tb, df["side_up"].to_numpy()]
    if by_window:
        cols.append(pd.factorize(df["cid"])[0])
    return pd.MultiIndex.from_arrays(cols).factorize()[0]


def wauc(s, y, w, g=None):
    """Weighted AUC pooled within strata g (sum of within-stratum Mann-Whitney numerators / denominators)."""
    df = pd.DataFrame({"g": np.zeros(len(s), int) if g is None else g, "s": s, "pos": (y == 1).astype(float),
                       "negw": np.where(y == 1, 0.0, w)})
    a = df.groupby(["g", "s"], sort=True).agg(pos=("pos", "sum"), negw=("negw", "sum")).reset_index()
    a["cum"] = a.groupby("g")["negw"].cumsum() - a["negw"]
    a["num"] = a["pos"] * (a["cum"] + 0.5 * a["negw"])
    t = a.groupby("g").agg(num=("num", "sum"), pos=("pos", "sum"), neg=("negw", "sum"))
    t = t[(t["pos"] > 0) & (t["neg"] > 0)]
    return float(t["num"].sum() / (t["pos"] * t["neg"]).sum()) if len(t) else float("nan")


def main(n_perm: int = 10) -> None:
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    mk_tx = set(fills.loc[fills["role"] == "maker", "tx"])
    cw = set(WALLETS.values())
    days = sorted(int(f.stem.split("_")[-1]) for f in OUT.glob("panel2_day_*.parquet"))
    rng = np.random.default_rng(11)
    tr = pd.concat([day_prints(d, w, sp, mk_tx, cw, 0.10, rng)[0] for d in days if d < VAL0], ignore_index=True)
    res = {"build_prints_sampled": len(tr), "build_pos": int(tr["y"].sum()), "build_days": [d for d in days if d < VAL0]}
    models, theta = {}, {}
    for nm, fs in (("all", F_ALL), ("activity", F_ACT)):
        models[nm] = lgb.train(PARAMS, lgb.Dataset(tr[fs], tr["y"], weight=tr["wt"]), 300)
        s = models[nm].predict(tr[fs])
        # threshold: top 15% of BUILD prints (weighted)
        o = np.argsort(-s)
        cw_ = np.cumsum(tr["wt"].to_numpy()[o]) / tr["wt"].sum()
        theta[nm] = float(s[o][np.searchsorted(cw_, 0.15)])
        res[f"imp_{nm}"] = dict(sorted(zip(fs, models[nm].feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:10])
        models[nm].save_model(str(HERE / f"selection2_{nm}.txt"))
    res["theta"] = theta
    del tr
    rng = np.random.default_rng(12)
    te_all, null_g, null_w = [], [[] for _ in range(n_perm)], [[] for _ in range(n_perm)]
    vdays = [d for d in days if d >= VAL0]
    for d in vdays:
        te, pan, wd = day_prints(d, w, sp, mk_tx, cw, 0.25, rng)
        for nm, fs in (("all", F_ALL), ("activity", F_ACT)):
            te["s_" + nm] = models[nm].predict(te[fs])
        te_all.append(te[["cid", "day", "y", "wt", "q", "rel_p", "side_up", "s_all", "s_activity"]])
        prng = np.random.default_rng(100 + d % 1000)
        for i in range(n_perm):
            k = int(prng.integers(1, len(wd)))
            r = rotated(te, pan, wd, sp, k)
            r = r.sort_values(["cid", "ts"]).reset_index(drop=True)
            null_g[i].append(pd.DataFrame({"cid": (r["day"] // 86400 * 1000 + r["widx"]).astype(np.int64), "y": r["y"].astype(np.int8), "wt": r["wt"], "q": r["q"], "rel_p": r["rel_p"],
                                           "side_up": r["side_up"], "s": models["all"].predict(r[F_ALL]).astype(np.float32)}))
        print("day", d, len(te), int(te["y"].sum()), flush=True)
    te = pd.concat(te_all, ignore_index=True)
    gg, gw = strata(te, 50, 40, False), strata(te, 10, 10, True)
    out = {}
    for nm in ("all", "activity"):
        s = te["s_" + nm].to_numpy()
        flag = s >= theta[nm]
        rec = float(flag[te["y"] == 1].mean())
        prec = float(np.sum(flag & (te["y"] == 1)) / np.sum(te["wt"] * flag))
        base = float(te["y"].sum() / te["wt"].sum())
        out[nm] = {"auc": wauc(s, te["y"].to_numpy(), te["wt"].to_numpy()),
                   "auc_strat_global": wauc(s, te["y"].to_numpy(), te["wt"].to_numpy(), gg),
                   "auc_strat_window": wauc(s, te["y"].to_numpy(), te["wt"].to_numpy(), gw),
                   "recall_at_theta": rec, "lift_at_theta": prec / base, "flag_share": float(np.sum(te["wt"] * flag) / te["wt"].sum())}
    nul_g, nul_w = [], []
    for i in range(n_perm):
        r = pd.concat(null_g[i], ignore_index=True)
        nul_g.append(wauc(r["s"].to_numpy(), r["y"].to_numpy(), r["wt"].to_numpy(), strata(r, 50, 40, False)))
        nul_w.append(wauc(r["s"].to_numpy(), r["y"].to_numpy(), r["wt"].to_numpy(), strata(r, 10, 10, True)))
    out["all"]["null_strat_global"] = {"mean": float(np.mean(nul_g)), "max": float(np.max(nul_g)), "n": n_perm}
    out["all"]["null_strat_window"] = {"mean": float(np.mean(nul_w)), "max": float(np.max(nul_w)), "n": n_perm}
    out["all"]["perm_p"] = float((1 + max(sum(x >= out["all"]["auc_strat_global"] for x in nul_g),
                                          sum(x >= out["all"]["auc_strat_window"] for x in nul_w))) / (n_perm + 1))
    res["validate"] = out
    res["val_prints_sampled"] = len(te)
    res["val_pos"] = int(te["y"].sum())
    print(json.dumps(res, indent=1, default=str))
    (HERE.parent / "results_iter2_selection.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
