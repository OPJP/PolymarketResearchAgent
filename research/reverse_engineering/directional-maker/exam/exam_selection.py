"""Examiner: selection test of the frozen rule on the holdout, with the methodology's null (docs/methodology.md):
spot paths rotated between windows of the same 2-hour block (k_b != 0 drawn per block), 200 draws, stratified AUC on
global strata (price 50 x time 40 x side) and within-window strata (window x price 10 x time 10 x side), p = the larger
of the two; recall and lift at the frozen threshold THETA_SEL; market-activity-only score as the co-occurrence baseline.

Print table and scores: the rule's code (sel2.day_prints on the holdout panels, frozen selection2_*.txt models).
AUCs, strata, rotation and tests: own code here. Negatives subsampled 10% (fixed seed) with weight 10.

python exam_selection.py N_PERM   -> results/exam_selection_holdout.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CODE = HERE.parent / "code"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa: E402
import sel2  # noqa: E402
from final_rule import THETA_SEL  # noqa: E402
from exam_panel import CLUSTER, EX, txint  # noqa: E402

RES = HERE.parent / "results"
FWD0 = 1793318400


def wauc_strat(s, y, wt, g) -> float:
    s, y, wt, g = (np.asarray(x) for x in (s, y, wt, g))
    o = np.lexsort((s, g))
    s, y, wt, g = s[o], y[o].astype(bool), wt[o].astype(float), g[o]
    negw = np.where(y, 0.0, wt)
    pos = y.astype(float)
    newg = np.r_[True, g[1:] != g[:-1]]
    newt = newg | np.r_[True, s[1:] != s[:-1]]
    tid = np.cumsum(newt) - 1
    gid = np.cumsum(newg) - 1
    t_neg = np.bincount(tid, weights=negw)
    t_pos = np.bincount(tid, weights=pos)
    t_g = gid[newt]
    cum = np.cumsum(t_neg)
    g_start = np.r_[0, np.cumsum(np.bincount(t_g))[:-1]]  # first tie group of each stratum
    before = cum - t_neg - np.r_[0, cum][g_start[t_g]]
    num_g = np.bincount(t_g, weights=t_pos * (before + 0.5 * t_neg))
    P = np.bincount(t_g, weights=t_pos)
    N = np.bincount(t_g, weights=t_neg)
    ok = (P > 0) & (N > 0)
    return float(num_g[ok].sum() / (P[ok] * N[ok]).sum()) if ok.any() else float("nan")


def strata(q, rel_p, side, cid, npb, ntb, by_window):
    edges = np.unique(np.quantile(q, np.linspace(0, 1, npb + 1)[1:-1]))
    pb = np.searchsorted(edges, q, side="right")
    tb = np.clip(np.floor(rel_p / 300 * ntb).astype(int), 0, ntb - 1)
    cols = [pb, tb, side] + ([pd.factorize(cid)[0]] if by_window else [])
    return pd.MultiIndex.from_arrays(cols).factorize()[0]


def main(n_perm: int) -> None:
    w = pd.read_parquet(EX / "windows_5m.parquet").sort_values("start_ts").reset_index(drop=True)
    days = sorted(int(f.stem.split("_")[-1]) for f in EX.glob("panel_day_*.parquet"))
    spd = pd.read_parquet(EX / "spot_btc_1s.parquet")
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    f = pd.read_parquet(EX / "fills_holdout.parquet")
    mk_tx = set(f.loc[f["role"] == "maker", "tx"])
    cw = set(CLUSTER)
    models = {nm: lgb.Booster(model_file=str(CODE / f"selection2_{nm}.txt")) for nm in ("all", "activity")}
    rng = np.random.default_rng(2026)
    te_all, pans = [], []
    for d in days:
        tk = pd.read_parquet(EX / f"taker5m_day_{d}.parquet")
        tk["tx"] = txint(tk["tx"])
        pan = pd.read_parquet(EX / f"panel_day_{d}.parquet")
        te, pan_d, _ = sel2.day_prints(d, w, sp, mk_tx, cw, 0.10, rng, tk=tk, pan=pan)
        te = te.reset_index(drop=True)
        te["s_all"] = models["all"].predict(te[sel2.F_ALL]).astype(np.float32)
        te["s_activity"] = models["activity"].predict(te[sel2.F_ACT]).astype(np.float32)
        te_all.append(te)
        pans.append(pan_d[["cid", "rel", "side_up"] + [c for c in sel2.SPOTCOLS if c != "edge_s"]])
        print("day", d, len(te), int(te["y"].sum()), flush=True)
        del tk, pan
    te = pd.concat(te_all, ignore_index=True)
    pan = pd.concat(pans, ignore_index=True)
    del te_all, pans
    y, wt = te["y"].to_numpy(), te["wt"].to_numpy()
    q, relp, side, cid = te["q"].to_numpy(), te["rel_p"].to_numpy(), te["side_up"].to_numpy(), te["cid"].to_numpy()
    gg = strata(q, relp, side, cid, 50, 40, False)
    gw = strata(q, relp, side, cid, 10, 10, True)
    g0 = np.zeros(len(te), int)
    base = float(y.sum() / wt.sum())
    out = {"prints_sampled": int(len(te)), "wallet_prints": int(y.sum()), "base_rate": base, "neg_frac": 0.10}
    for nm in ("all", "activity"):
        s = te["s_" + nm].to_numpy()
        flag = s >= THETA_SEL[nm]
        out[nm] = {"auc": wauc_strat(s, y, wt, g0), "auc_strat_global": wauc_strat(s, y, wt, gg),
                   "auc_strat_window": wauc_strat(s, y, wt, gw), "recall_at_theta": float(flag[y == 1].mean()),
                   "lift_at_theta": float((flag & (y == 1)).sum() / (wt * flag).sum() / base), "flag_share": float((wt * flag).sum() / wt.sum())}
    fw = te["start_ts"].to_numpy() >= FWD0
    if fw.any():
        s = te["s_all"].to_numpy()
        out["forward_days_all_auc"] = wauc_strat(s[fw], y[fw], wt[fw], g0[fw])
    # rotation null within 2-hour blocks
    wi = w.set_index("cid")
    st = te["start_ts"].to_numpy()
    blk = st // 7200
    wb = w.assign(b=w["start_ts"] // 7200)
    wb["pos"] = wb.groupby("b").cumcount()
    nb = wb.groupby("b")["cid"].transform("size")
    pos_of = dict(zip(wb["cid"], wb["pos"]))
    nb_of = dict(zip(wb["cid"], nb))
    by_b = {b: g["cid"].to_numpy() for b, g in wb.groupby("b")}
    bstart = {b: g["start_ts"].to_numpy() for b, g in wb.groupby("b")}
    posv = np.array([pos_of[c] for c in cid])
    nbv = np.array([nb_of[c] for c in cid])
    ub = np.unique(blk)
    prng = np.random.default_rng(7)
    sc = [c for c in sel2.SPOTCOLS if c != "edge_s"]
    pan_i = pan.set_index(["cid", "rel", "side_up"])[sc]
    base_cols = te.drop(columns=sc + ["fair_p", "edge_p"])
    ng, nw_ = [], []
    for i in range(n_perm):
        kb = {b: int(prng.integers(1, len(by_b[b]))) if len(by_b[b]) >= 4 else 0 for b in ub}
        k = np.array([kb[b] for b in blk])
        tpos = (posv + k) % nbv
        cid2 = np.array([by_b[b][t] for b, t in zip(blk, tpos)])
        shift = np.array([bstart[b][t] for b, t in zip(blk, tpos)]) - st
        fz, _ = fair_up(sp, st + shift, te["end_ts"].to_numpy() + shift, te["ts"].to_numpy() - 2 + shift)
        r = base_cols.copy()
        r["fair_p"] = np.where(side == 1, fz, 1 - fz).astype(np.float32)
        r["edge_p"] = r["fair_p"] - r["q"]
        rr = pan_i.reindex(pd.MultiIndex.from_arrays([cid2, te["rel"].to_numpy(), side])).reset_index(drop=True)
        for c in sc:
            r[c] = rr[c].to_numpy()
        r["edge_s"] = r["fair_s"] - r["last_s"]
        s = models["all"].predict(r[sel2.F_ALL])
        ng.append(wauc_strat(s, y, wt, gg))
        nw_.append(wauc_strat(s, y, wt, gw))
        if i % 20 == 0:
            print("perm", i, round(ng[-1], 4), round(nw_[-1], 4), flush=True)
        del r, rr
    ng, nw_ = np.array(ng), np.array(nw_)
    a = out["all"]
    a["rotation_null_2h_blocks"] = {"n_perm": n_perm, "global_mean": float(ng.mean()), "global_sd": float(ng.std(ddof=1)), "global_max": float(ng.max()),
                                    "window_mean": float(nw_.mean()), "window_sd": float(nw_.std(ddof=1)), "window_max": float(nw_.max())}
    a["p_global"] = float((1 + (ng >= a["auc_strat_global"]).sum()) / (n_perm + 1))
    a["p_window"] = float((1 + (nw_ >= a["auc_strat_window"]).sum()) / (n_perm + 1))
    a["p"] = max(a["p_global"], a["p_window"])
    a["z_global"] = float((a["auc_strat_global"] - ng.mean()) / ng.std(ddof=1))
    a["z_window"] = float((a["auc_strat_window"] - nw_.mean()) / nw_.std(ddof=1))
    a["criterion"] = {"auc_ge_0.80": a["auc"] >= 0.80, "recall_ge_0.50": a["recall_at_theta"] >= 0.5, "lift_ge_3": a["lift_at_theta"] >= 3,
                      "p_lt_0.01": a["p"] < 0.01}
    (RES / "exam_selection_holdout.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
