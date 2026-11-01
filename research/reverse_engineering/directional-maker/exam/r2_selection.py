"""Examiner round 2: selection (R2's print score, BTC 5m) on lot f1 with a 2-h-block window-rotation null of 2,000 draws.

Population and features: the rule's own print table built inside the frozen evaluate() (sel2.day_prints, captured as
ev/sel_te_<day>.parquet; negatives subsampled 10%, weight 10). Scores: selection2_all.txt (rule) and
selection2_activity.txt (the RE's activity baseline), THETA_SEL from final_rule. Examiner baseline: a LightGBM with the
rule's selection PARAMS and 300 rounds fitted on the rule's BUILD days (sel2: days < 10-16, the RE's development files) on
F_ACT plus activity-only print features (|q - 0.5|, log size, round-dollar notional).
Null: in each 2-h block (by window start) every window takes the Binance path of the window k_b places later in that
block (k_b != 0 drawn per block); print fair_p / edge_p are recomputed on that path and the bin-level spot columns come
from the partner window's panel row (same rel, side), edge_s = fair_s(partner) - last_s(own). p = (1 + #null >= obs) /
(n + 1), one-sided, on the global (price 50 x time 40 x side) and within-window (window x price 10 x time 10 x side)
stratified AUCs; the larger p counts. Gains over the baselines with a 2-h block bootstrap (2,000).
"""
from __future__ import annotations

import json
import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from r2_common import CLUSTER, EXC, RES, WS

import final_rule as fr  # noqa: E402
import sel2  # noqa: E402
from features2 import Spot, fair_up  # noqa: E402

EV = EXC / "ev"
CODE = WS / "code"
CUT = json.loads((RES / "exam_r2_step0.json").read_text())["cut_ts"]
NDRAW = 2000


def wauc(s, y, w, g=None):
    """my weighted Mann-Whitney AUC pooled within strata g (ties count 1/2)."""
    g = np.zeros(len(s), int) if g is None else np.asarray(g)
    o = np.lexsort((s, g))
    s, y, w, g = np.asarray(s)[o], np.asarray(y)[o], np.asarray(w)[o], g[o]
    num = den = 0.0
    starts = np.r_[0, np.nonzero(np.diff(g))[0] + 1, len(g)]
    for a, b in zip(starts[:-1], starts[1:]):
        ss, yy, ww = s[a:b], y[a:b], w[a:b]
        P = yy == 1
        if not P.any() or P.all():
            continue
        negw = np.where(P, 0.0, ww)
        # group ties
        u, inv = np.unique(ss, return_inverse=True)
        nw = np.bincount(inv, weights=negw, minlength=len(u))
        pc = np.bincount(inv, weights=P.astype(float), minlength=len(u))
        cum = np.cumsum(nw) - nw
        num += float(np.sum(pc * (cum + 0.5 * nw)))
        den += float(pc.sum() * nw.sum())
    return num / den if den else float("nan")


def ext(df):
    d = df.copy()
    d["q_dist"] = (d["q"] - 0.5).abs().astype(np.float32)
    d["log_size"] = np.log1p(d["size_p"]).astype(np.float32)
    usd = d["q"] * d["size_p"]
    d["round_usd"] = (np.abs(usd - np.round(usd)) < 0.02).astype(np.int8)
    return d


F_EX = sel2.F_ACT + ["q_dist", "log_size", "round_usd"]


def fit_examiner_baseline():
    f = EXC / "models" / "exam_sel_activity_ext.txt"
    if f.exists():
        return lgb.Booster(model_file=str(f))
    from panel2 import OUT, WALLETS
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    mk_tx = set(fills.loc[fills["role"] == "maker", "tx"])
    cw = set(WALLETS.values())
    days = sorted(int(x.stem.split("_")[-1]) for x in OUT.glob("panel2_day_*.parquet"))
    rng = np.random.default_rng(11)
    tr = pd.concat([sel2.day_prints(d, w, sp, mk_tx, cw, 0.10, rng)[0] for d in days if d < sel2.VAL0], ignore_index=True)
    tr = ext(tr)
    m = lgb.train(sel2.PARAMS, lgb.Dataset(tr[F_EX], tr["y"], weight=tr["wt"]), 300)
    m.save_model(str(f))
    s = m.predict(tr[F_EX])
    o = np.argsort(-s)
    cw_ = np.cumsum(tr["wt"].to_numpy()[o]) / tr["wt"].sum()
    theta = float(s[o][np.searchsorted(cw_, 0.15)])
    (EXC / "models" / "exam_sel_theta.json").write_text(json.dumps({"theta": theta, "build_prints": int(len(tr)), "build_pos": int(tr["y"].sum())}))
    del tr
    return m


def strata(df, npb, ntb, by_window):
    pr = df["q"].to_numpy()
    edges = np.unique(np.quantile(pr, np.linspace(0, 1, npb + 1)[1:-1]))
    pb = np.searchsorted(edges, pr, side="right")
    tb = np.floor(df["rel_p"].to_numpy() / 300 * ntb).astype(int)
    cols = [pb, tb, df["side_up"].to_numpy()]
    if by_window:
        cols.append(pd.factorize(df["cid"])[0])
    return pd.MultiIndex.from_arrays(cols).factorize()[0]


def main():
    t0 = time.time()
    m_ex = fit_examiner_baseline()
    th_ex = json.loads((EXC / "models" / "exam_sel_theta.json").read_text())["theta"]
    print("examiner baseline ready", round(time.time() - t0, 1), flush=True)
    models = {nm: lgb.Booster(model_file=str(CODE / f"selection2_{nm}.txt")) for nm in ("all", "activity")}
    te = pd.concat([pd.read_parquet(f) for f in sorted(EV.glob("sel_te_*.parquet"))], ignore_index=True)
    te = ext(te)
    pan = pd.read_parquet(EV / "panel5.parquet")
    spd = pd.read_parquet(EV / "spot_btc.parquet")
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    te["s_all"] = models["all"].predict(te[sel2.F_ALL])
    te["s_act"] = models["activity"].predict(te[sel2.F_ACT])
    te["s_ex"] = m_ex.predict(te[F_EX])
    y, wt = te["y"].to_numpy(), te["wt"].to_numpy()
    gg, gw = strata(te, 50, 40, False), strata(te, 10, 10, True)
    base = y.sum() / wt.sum()

    def rl(s, th, m=None):
        m = np.ones(len(s), bool) if m is None else m
        flag = s >= th
        b = y[m].sum() / wt[m].sum()
        return float(flag[m & (y == 1)].mean()), float(np.sum(flag[m] & (y[m] == 1)) / np.sum(wt[m] * flag[m]) / b) if flag[m].any() else float("nan")
    out = {"prints_sampled": int(len(te)), "wallet_prints": int(y.sum()), "windows": int(te["cid"].nunique())}
    for nm, col, th in (("rule", "s_all", fr.THETA_SEL["all"]), ("re_activity", "s_act", fr.THETA_SEL["activity"]), ("examiner_activity", "s_ex", th_ex)):
        s = te[col].to_numpy()
        r_, l_ = rl(s, th)
        out[nm] = {"auc": wauc(s, y, wt), "auc_check_sel2": sel2.wauc(s, y, wt), "auc_strat_global": wauc(s, y, wt, gg),
                   "auc_strat_window": wauc(s, y, wt, gw), "recall_at_theta": r_, "lift_at_theta": l_}
        for h, m in (("early", te["start_ts"].to_numpy() < CUT), ("late", te["start_ts"].to_numpy() >= CUT)):
            r2, l2 = rl(s, th, m)
            out[nm][h] = {"auc": wauc(s[m], y[m], wt[m]), "recall": r2, "lift": l2}
    print(json.dumps(out, indent=0)[:1500], flush=True)
    # per wallet: label = the print's transaction holds a maker fill of that wallet
    mk = pd.read_parquet(EV / "mk5.parquet")
    t2 = pd.read_parquet(EV / "w5.parquet")
    for addr, nm in CLUSTER.items():
        # te has no tx column: a print labelled y = 1 counts for the wallet if that wallet had a maker fill in the same
        # window, block second and side
        mkw = mk[mk["wallet"] == addr]
        side_of = {**{t: (c, 1) for t, c in zip(t2.up_token.astype(str), t2.cid)}, **{t: (c, 0) for t, c in zip(t2.down_token.astype(str), t2.cid)}}
        keys = set((side_of[str(t)][0], side_of[str(t)][1], int(ts)) for t, ts in zip(mkw.token_id, mkw.ts) if str(t) in side_of)
        yw = np.array([int(yy == 1 and (c, su, int(ts)) in keys) for yy, c, su, ts in zip(y, te.cid, te.side_up, te.ts)])
        keep = (y == 0) | (yw == 1)
        s = te["s_all"].to_numpy()
        out[f"wallet_{nm}"] = {"prints": int(yw.sum()), "auc": wauc(s[keep], yw[keep], wt[keep]),
                               "auc_re_activity": wauc(te["s_act"].to_numpy()[keep], yw[keep], wt[keep]),
                               "recall_at_theta": float((s[yw == 1] >= fr.THETA_SEL["all"]).mean()) if yw.sum() else None}
    # gains with a 2-h block bootstrap
    blk = (te["start_ts"] // 7200).astype(int).to_numpy()
    ub = np.unique(blk)
    idx = {u: np.nonzero(blk == u)[0] for u in ub}
    rng = np.random.default_rng(3)
    gains = {"re_activity": [], "examiner_activity": []}
    for _ in range(2000):
        ii = np.concatenate([idx[u] for u in rng.choice(ub, len(ub))])
        a = wauc(te["s_all"].to_numpy()[ii], y[ii], wt[ii])
        gains["re_activity"].append(a - wauc(te["s_act"].to_numpy()[ii], y[ii], wt[ii]))
        gains["examiner_activity"].append(a - wauc(te["s_ex"].to_numpy()[ii], y[ii], wt[ii]))
    for k, g in gains.items():
        g = np.array(g)
        out[f"gain_over_{k}"] = {"gain": out["rule"]["auc"] - out[k]["auc"], "ci95": [float(np.quantile(g, 0.025)), float(np.quantile(g, 0.975))],
                                 "p_le0": float((np.sum(g <= 0) + 1) / (len(g) + 1))}
    print("gains", {k: out[f"gain_over_{k}"] for k in gains}, round(time.time() - t0, 1), flush=True)
    # rotation null within 2-h blocks: precompute every (window, partner) score
    W = pd.read_parquet(EV / "w5.parquet").sort_values("start_ts").reset_index(drop=True)
    W["blk"] = (W["start_ts"] // 7200).astype(int)
    sc = [c for c in sel2.SPOTCOLS if c != "edge_s"]
    pr = pan[["cid", "rel", "side_up"] + sc].rename(columns={"cid": "cid2"})
    st_of = dict(zip(W.cid, W.start_ts))
    te["row"] = np.arange(len(te))
    pair_scores = {}  # (cid, partner) -> scores of cid's prints in te order of rows
    blocks = {}
    for b, g in W.groupby("blk"):
        cids = g["cid"].tolist()
        blocks[b] = cids
        for i, c in enumerate(cids):
            ti = te[te["cid"] == c]
            if not len(ti):
                continue
            for j, c2 in enumerate(cids):
                if j == i:
                    continue
                sh = int(st_of[c2] - st_of[c])
                r = ti.copy()
                f, _ = fair_up(sp, r["start_ts"].to_numpy() + sh, r["end_ts"].to_numpy() + sh, r["ts"].to_numpy() - 2 + sh)
                r["fair_p"] = np.where(r["side_up"] == 1, f, 1 - f).astype(np.float32)
                r["edge_p"] = r["fair_p"] - r["q"]
                r = r.drop(columns=sc).assign(cid2=c2).merge(pr, on=["cid2", "rel", "side_up"], how="left")
                r["edge_s"] = r["fair_s"] - r["last_s"]
                pair_scores[(c, c2)] = (ti["row"].to_numpy(), models["all"].predict(r[sel2.F_ALL]).astype(np.float32))
        print("block", b, len(cids), round(time.time() - t0, 1), flush=True)
    obs_g, obs_w = out["rule"]["auc_strat_global"], out["rule"]["auc_strat_window"]
    rng = np.random.default_rng(2026)
    ng, nw = [], []
    for k in range(NDRAW):
        s = np.full(len(te), np.nan, np.float32)
        for b, cids in blocks.items():
            n = len(cids)
            kb = int(rng.integers(1, n))
            for i, c in enumerate(cids):
                v = pair_scores.get((c, cids[(i + kb) % n]))
                if v is not None:
                    s[v[0]] = v[1]
        ok = np.isfinite(s)
        ng.append(wauc(s[ok], y[ok], wt[ok], gg[ok]))
        nw.append(wauc(s[ok], y[ok], wt[ok], gw[ok]))
        if k % 250 == 0:
            print("draw", k, round(time.time() - t0, 1), flush=True)
    ng, nw = np.array(ng), np.array(nw)
    out["rotation_null_2h"] = {"n_draws": NDRAW, "global_mean": float(ng.mean()), "global_sd": float(ng.std(ddof=1)), "global_max": float(ng.max()),
                               "window_mean": float(nw.mean()), "window_sd": float(nw.std(ddof=1)), "window_max": float(nw.max()),
                               "p_global": float((1 + np.sum(ng >= obs_g)) / (NDRAW + 1)), "p_window": float((1 + np.sum(nw >= obs_w)) / (NDRAW + 1)),
                               "z_global": float((obs_g - ng.mean()) / ng.std(ddof=1)), "z_window": float((obs_w - nw.mean()) / nw.std(ddof=1))}
    out["rotation_null_2h"]["p"] = max(out["rotation_null_2h"]["p_global"], out["rotation_null_2h"]["p_window"])
    out["secs"] = round(time.time() - t0, 1)
    (RES / "exam_r2_selection.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)[:5000])


if __name__ == "__main__":
    main()
