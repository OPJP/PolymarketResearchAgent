"""Iteration 10 (A1 = X97): is the Chainlink posture a stable rule? A sigma-free test on a historical match clock.
Pre-registered (code10/a1_stamps.py docstring, 22:46 UTC): T_hat = clip(taker sign_ms + 620, block_ms - 3000, block_ms -
1500) (block_ms - 2285 without a usable sign_ms); report stamp = floor((T_hat - 1432)/1000); strike K = Gamma
priceToBeat; market favourite from (a) the last clean print at the block clock (vol_hist's mid_up, ts <= b - 3) and (b)
diagnostic only, the fill's own price where |p - 0.5| > 0.05. Region D = sign(ln(CL/K)) disagrees with the market
favourite; score P(bought the Chainlink favourite) there. Also the frozen posture (1.4 x v300, Binance 1-s vol) with S =
Chainlink. Calibration first on 10-31 14:06-16:30 (live1031 taker sign_ms, the recorder's match ms, the book mid, the
recorded Chainlink): the proxies must reproduce the match-clock truth. Usage: a1_score.py live | lot"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
UPIDX = int(sys.argv[2]) if len(sys.argv) > 2 else 0
CLU = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
NAME = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
        "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney", "bosona": "bosona", "almach": "almach", "momoney": "momoney", "mo-money": "momoney"}


def that(sign_ms, bms):
    sign_ms = np.asarray(sign_ms, dtype=float)
    bms = np.asarray(bms, dtype=float)
    ok = np.isfinite(sign_ms) & (sign_ms > 0) & (bms - sign_ms < 60000) & (bms - sign_ms > -1000)
    return np.where(ok, np.clip(np.nan_to_num(sign_ms) + 620, bms - 3000, bms - 1500), bms - 2285)


def score(df, mid_col, cl_col, K_col="K"):
    """region D accuracy and coverage. df has is_up (bought Up), mid_up proxy, cl, K."""
    x = np.log(df[cl_col].to_numpy(float) / df[K_col].to_numpy(float))
    m = df[mid_col].to_numpy(float)
    ok = np.isfinite(x) & np.isfinite(m) & (np.abs(m - 0.5) > 0.0) & (x != 0)
    if mid_col == "mid_fill":
        ok &= np.abs(m - 0.5) > 0.05
    clfav_up = x > 0
    mkfav_up = m > 0.5
    D = ok & (clfav_up != mkfav_up)
    y = df["is_up"].to_numpy() == 1
    acc_D = float(np.mean((clfav_up == y)[D])) if D.any() else None
    return {"n_ok": int(ok.sum()), "n_D": int(D.sum()), "share_D": float(D.sum() / max(ok.sum(), 1)), "acc_D_bought_cl_favourite": acc_D,
            "acc_A_bought_common_favourite": float(np.mean((clfav_up == y)[ok & ~D])) if (ok & ~D).any() else None}


def posture(df, mid_col, cl_col, sig):
    x = np.log(df[cl_col].to_numpy(float) / df["K"].to_numpy(float))
    f = norm.cdf(x / (sig * np.sqrt(df["tau"].to_numpy(float))))
    m = df[mid_col].to_numpy(float)
    ok = np.isfinite(f) & np.isfinite(m)
    y = df["is_up"].to_numpy() == 1
    return {"n": int(ok.sum()), "acc": float(np.mean(((f > m) == y)[ok])) if ok.any() else None}


def live():
    a, b = 1793455560, 1793464200
    d = pd.read_parquet(C / "it9/side_D_1793448000_1793469600.parquet")
    d = d[(d["T"] >= a * 1000) & (d["T"] < b * 1000)].copy()
    xs = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "it6" / "x_*.parquet"))]).drop_duplicates(["h", "s", "ai", "p", "z"])
    xs["h"] = xs.h.str.lower()
    first = xs.groupby("h").s.min()
    s2h = {int(s): h for h, s in first.items()}
    d["tx"] = d["T"].map(lambda t: s2h.get(int(t)))
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
    cd["tx"] = cd.tx.str.lower()
    cd["maker"] = cd.maker.str.lower()
    tk = cd[(cd.role == "taker") & ~cd.maker.isin(CLU)].drop_duplicates("tx").set_index("tx")
    act = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_1793455200_*.parquet"))])
    act["tx"] = act.transactionHash.str.lower()
    bts = act.drop_duplicates("tx").set_index("tx").timestamp
    d["sign_ms"] = d.tx.map(tk.sign_ms)
    d["bts"] = d.tx.map(bts)
    d = d.dropna(subset=["bts", "K"])
    d["bms"] = d.bts.astype(float) * 1000
    d["T_hat"] = that(d.sign_ms, d.bms)
    d["T_blk"] = d.bms - 2285
    stamps = np.unique(np.r_[((d.T_hat - 1432) // 1000).astype(np.int64), ((d.T_blk - 1432) // 1000).astype(np.int64), d.bts.astype(np.int64) - 4])
    clv = cl_source.cl_values(stamps, fetch=False)
    d["cl_hat"] = ((d.T_hat - 1432) // 1000).astype(np.int64).map(clv)
    d["cl_blk"] = ((d.T_blk - 1432) // 1000).astype(np.int64).map(clv)
    d["cl_b4"] = (d.bts.astype(np.int64) - 4).map(clv)
    # proxy (a): last clean trade matched before (b - 3) s on the block clock = s <= (b - 3) * 1000 - 2285
    clean = xs[~xs.h.isin(set(act.tx))].copy()
    up_tok = {}
    ws = pd.read_parquet(C / "it9/act_1793448000_1793469600.parquet") if (C / "it9/act_1793448000_1793469600.parquet").exists() else None
    # map asset -> (window start, is_up) via the window table used by final_rule
    sys.path.insert(0, str(ROOT))
    import final_rule as F
    w = pd.concat([F._windows(a - 900, b + 900), F._windows15(a - 900, b + 900)], ignore_index=True)
    for r in w.itertuples(index=False):
        up_tok[str(r.up_token)] = (int(r.start_ts), int(r.end_ts), 1)
        up_tok[str(r.down_token)] = (int(r.start_ts), int(r.end_ts), 0)
    clean = clean[clean.w.str.startswith("btc-updown-")]
    clean["st"] = clean.w.str.split("-").str[-1].astype(np.int64)
    clean["en"] = clean.st + np.where(clean.w.str.contains("-15m-"), 900, 300)
    clean["pup"] = np.where(clean.ai == UPIDX, clean.p.astype(float), 1 - clean.p.astype(float))
    G = {k: (g.s.to_numpy(), g.pup.to_numpy()) for k, g in clean.sort_values("s").groupby(["st", "en"])}
    mids = []
    for r in d.itertuples(index=False):
        g = G.get((int(r.st), int(r.en)))
        if g is None:
            mids.append(np.nan)
            continue
        j = np.searchsorted(g[0], (r.bts - 3) * 1000 - 2285, side="right") - 1
        mids.append(g[1][j] if j >= 0 else np.nan)
    d["mid_a"] = mids
    # proxy (b): the fill's own price -> Up mid; the fill price is the order's limit; side_D has no price, use mid_up as truth
    d["tau"] = np.maximum(d.en - d["T"] / 1000.0, 1.0)
    out = {"n": int(len(d)), "sign_ms_coverage": float(d.sign_ms.notna().mean()), "T_hat_abs_err_ms_median": float((d.T_hat - d["T"]).abs().median()),
           "T_hat_abs_err_ms_q75": float((d.T_hat - d["T"]).abs().quantile(0.75)), "T_blk_abs_err_ms_median": float((d.T_blk - d["T"]).abs().median()),
           "cl_hat_coverage": float(d.cl_hat.notna().mean())}
    out["truth_matchclock_book_mid"] = score(d, "mid_up", "cl")
    out["T_hat_cl__book_mid"] = score(d, "mid_up", "cl_hat")
    out["T_hat_cl__mid_a"] = score(d, "mid_a", "cl_hat")
    out["T_blk_cl__mid_a"] = score(d, "mid_a", "cl_blk")
    out["b4_cl__mid_a"] = score(d, "mid_a", "cl_b4")
    # fill-price proxy needs the fill price: take it from the live activity of the wallet in that tx
    ap = act[["tx", "price", "asset"]].copy()
    ap["asset"] = ap.asset.astype(str)
    pr = []
    apg = {k: g for k, g in ap.groupby("tx")}
    for r in d.itertuples(index=False):
        g = apg.get(r.tx)
        pr.append(float(g.price.iloc[0]) if g is not None else np.nan)
    d["pfill"] = pr
    d["mid_fill"] = np.where(d.is_up == 1, d.pfill + 0.01, 1 - d.pfill - 0.01)
    out["T_hat_cl__mid_fill_diag"] = score(d, "mid_fill", "cl_hat")
    out["truth_cl__mid_fill_diag"] = score(d, "mid_fill", "cl")
    sp = pd.read_parquet(C / f"it9/spot1s_rest_{1793448000 - 7200}_{1793469600}.parquet").sort_values("sec")
    px = sp.set_index("sec").px
    lr = np.log(px).diff()
    v300 = np.sqrt((lr ** 2).rolling(300).mean())
    d["v300"] = (d.bts.astype(np.int64) - 3).map(v300)
    sig = 1.4 * d.v300.to_numpy(float)
    out["posture_truth"] = posture(d, "mid_up", "cl", sig)
    out["posture_T_hat_cl_mid_a"] = posture(d, "mid_a", "cl_hat", sig)
    out["posture_b4_cl_mid_a"] = posture(d, "mid_a", "cl_b4", sig)
    out["per_wallet_truth_D"] = {NAME[w]: score(g, "mid_up", "cl")["acc_D_bought_cl_favourite"] for w, g in d.groupby("wallet")}
    out["per_wallet_hat_a_D"] = {NAME[w]: score(g, "mid_a", "cl_hat")["acc_D_bought_cl_favourite"] for w, g in d.groupby("wallet")}
    # M5 (X96): the posture at the taker's arrival (sign_ms + b - lambda), pre-registered grid b in {0, 190} ms, lambda in
    # {0, 100, 150} ms, against the match-clock posture on the same fills (book mid at the match in both).
    e = d[d.sign_ms.notna() & (d.bms - d.sign_ms < 60000) & (d.bms - d.sign_ms > 0)].copy()
    y = e.is_up.to_numpy() == 1
    sig_e = 1.4 * e.v300.to_numpy(float)
    f_T = norm.cdf(np.log(e.cl.to_numpy(float) / e.K.to_numpy(float)) / (sig_e * np.sqrt(e.tau.to_numpy(float))))
    base = (f_T > e.mid_up.to_numpy(float)) == y
    m5 = {"n": int(len(e)), "match_clock": float(np.mean(base))}
    for bb in (0, 190):
        for lam in (0, 100, 150):
            stp = ((e.sign_ms + bb - lam - 1432) // 1000).astype(np.int64)
            cv = cl_source.cl_values(np.unique(stp), fetch=False)
            c2 = stp.map(cv).to_numpy(float)
            tau2 = np.maximum(e.en.to_numpy() - (e.sign_ms.to_numpy() + bb - lam) / 1000.0, 1.0)
            f2 = norm.cdf(np.log(c2 / e.K.to_numpy(float)) / (sig_e * np.sqrt(tau2)))
            ok = np.isfinite(f2)
            acc2 = (f2 > e.mid_up.to_numpy(float)) == y
            flip = ok & ((f2 > e.mid_up.to_numpy(float)) != (f_T > e.mid_up.to_numpy(float)))
            m5[f"b{bb}_l{lam}"] = {"acc": float(np.mean(acc2[ok])), "acc_match_same_rows": float(np.mean(base[ok])), "share_flip": float(flip.mean()),
                                   "acc_arrival_where_flip": float(np.mean(acc2[flip])) if flip.any() else None,
                                   "acc_match_where_flip": float(np.mean(base[flip])) if flip.any() else None}
    out["m5_cancel_race"] = m5
    return out


def lot():
    ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
    K = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
    clv_all = cl_source._cache()
    out = {}
    for sp, fn in (("study", "b1_takers_study"), ("validate", "b1_takers_valid")):
        v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "wallet", "b", "st", "en", "is_up", "price", "mid_up", "v300", "day", "token", "age", "S", "K"])
        v = v.rename(columns={"K": "K_bn"})
        t = pd.read_parquet(C / f"{fn}.parquet", columns=["tx", "sign_ms"])
        t["tx"] = t.tx.str.lower()
        t = t.drop_duplicates("tx").set_index("tx")
        v["txh"] = v.txh.str.lower()
        v["sign_ms"] = v.txh.map(t.sign_ms)
        bms = v.b.astype(float) * 1000
        v["T_hat"] = that(v.sign_ms, bms)
        v["stamp"] = ((v.T_hat - 1432) // 1000).astype(np.int64)
        v["cl"] = v.stamp.map(lambda s: clv_all.get(int(s), np.nan))
        v["K"] = v.st.map(K)
        v["mid_fill"] = np.where(v.is_up == 1, v.price + 0.01, 1 - v.price - 0.01)
        v["tau"] = np.maximum(v.en - v.T_hat / 1000.0, 1.0)
        # order class from the calldata original size (M1): schedule-size posture rungs vs the rest (pairing bids etc.)
        ob = pd.read_parquet(C / ("b1_cluster_orders_study.parquet" if sp == "study" else "b1_cluster_orders_valid.parquet"), columns=["tx", "w", "token_id", "taker_amount", "oside", "role"])
        ob = ob[(ob.role == "maker") & (ob.oside == 0)].copy()
        ob["tx"] = ob.tx.str.lower()
        ob["orig"] = (ob.taker_amount / 1e6).round(2)
        ob["key"] = ob.tx + "|" + ob.w.astype(str) + "|" + ob.token_id.astype(str)
        om = ob.drop_duplicates("key").set_index("key").orig
        v["key"] = v.txh + "|" + v.wallet.astype(str).str.lower().map(lambda a: NAME.get(a, a)) + "|" + v.token.astype(str) if "token" in v.columns else None
        h = v.dropna(subset=["cl", "K"]).copy()
        o = {"n_fills": int(len(v)), "n_with_cl": int(len(h)), "share_with_cl": float(len(h) / len(v))}
        if "key" in h.columns and h["key"].notna().any():
            h["orig"] = h["key"].map(om)
            STD = {500, 1000, 250, 125, 100, 62, 50, 12, 300, 40, 200, 2000, 25, 31, 20, 10, 5}
            h["sched"] = h.orig.isin(STD)
            o["class_join_share"] = float(h.orig.notna().mean())
            hs = h[h.sched]
            o["SCHEDULE_ONLY_D_mid_a"] = score(hs, "mid_up", "cl")
            o["NONSCHEDULE_D_mid_a"] = score(h[h.orig.notna() & ~h.sched], "mid_up", "cl")
            o["SCHEDULE_ONLY_posture_frozen"] = posture(hs, "mid_up", "cl", 1.4 * hs.v300.to_numpy(float))
            if "age" in h.columns:
                fresh = hs[hs.age <= 3]
                o["SCHEDULE_fresh_print_D_mid_a"] = score(fresh, "mid_up", "cl")
        o["D_mid_a"] = score(h, "mid_up", "cl")
        o["D_mid_fill_diag"] = score(h, "mid_fill", "cl")
        o["posture_frozen_cl_mid_a"] = posture(h, "mid_up", "cl", 1.4 * h.v300.to_numpy(float))
        # region D split by the strength of the disagreement: |fair_cl - mid| with the frozen sigma (1.4 x v300)
        x = np.log(h.cl.to_numpy(float) / h.K.to_numpy(float))
        fcl = norm.cdf(x / (1.4 * h.v300.to_numpy(float) * np.sqrt(h.tau.to_numpy(float))))
        m = h.mid_up.to_numpy(float)
        yy = h.is_up.to_numpy() == 1
        Dm = np.isfinite(m) & ((x > 0) != (m > 0.5)) & (x != 0)
        gap = np.abs(fcl - m)
        o["D_by_gap"] = {f"{lo}-{hi}": {"n": int((Dm & (gap >= lo) & (gap < hi)).sum()),
                                        "acc": float(np.mean(((x > 0) == yy)[Dm & (gap >= lo) & (gap < hi)])) if (Dm & (gap >= lo) & (gap < hi)).any() else None}
                         for lo, hi in ((0, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 1.01))}
        o["all_by_gap_frozen_posture"] = {f"{lo}-{hi}": {"n": int(((gap >= lo) & (gap < hi)).sum()),
                                                         "acc": float(np.mean(((fcl > m) == yy)[(gap >= lo) & (gap < hi)])) if ((gap >= lo) & (gap < hi)).any() else None}
                                          for lo, hi in ((0, 0.03), (0.03, 0.1), (0.1, 0.2), (0.2, 1.01))}
        # in Chainlink-region D: which reference does the cluster follow? Binance (spot b-3 vs the Binance TWAP strike)
        xb = np.log(h.S.to_numpy(float) / h.K_bn.to_numpy(float))
        okb = Dm & np.isfinite(xb) & (xb != 0)
        o["in_CL_D_binance_agrees_with_CL"] = float(np.mean(((xb > 0) == (x > 0))[okb])) if okb.any() else None
        o["in_CL_D_bought_binance_favourite"] = float(np.mean(((xb > 0) == yy)[okb])) if okb.any() else None
        agree = okb & ((xb > 0) == (x > 0))
        dis = okb & ((xb > 0) != (x > 0))
        o["in_CL_D_when_BN_agrees_with_CL_acc"] = [int(agree.sum()), float(np.mean(((x > 0) == yy)[agree])) if agree.any() else None]
        o["in_CL_D_when_BN_sides_with_market_acc_CL"] = [int(dis.sum()), float(np.mean(((x > 0) == yy)[dis])) if dis.any() else None]
        o["D_by_gap_bn"] = {}
        for lo, hi in ((0, 0.05), (0.05, 0.1), (0.1, 1.01)):
            k_ = okb & (gap >= lo) & (gap < hi)
            o["D_by_gap_bn"][f"{lo}-{hi}"] = {"n": int(k_.sum()),
                                              "bn_sides_with_market": float(np.mean(((xb > 0) != (x > 0))[k_])) if k_.any() else None,
                                              "acc_cl": float(np.mean(((x > 0) == yy)[k_])) if k_.any() else None,
                                              "acc_cl_when_bn_agrees": float(np.mean(((x > 0) == yy)[k_ & ((xb > 0) == (x > 0))])) if (k_ & ((xb > 0) == (x > 0))).any() else None}
        o["per_day_D_mid_a_n"] = {int(dd): score(g, "mid_up", "cl")["n_D"] for dd, g in h.groupby("day")}
        o["per_day_D_mid_a"] = {int(dd): score(g, "mid_up", "cl")["acc_D_bought_cl_favourite"] for dd, g in h.groupby("day")}
        if sp == "study":
            o["per_wallet_D_mid_a"] = {NAME.get(str(w).lower(), str(w)): score(g, "mid_up", "cl")["acc_D_bought_cl_favourite"] for w, g in h.groupby("wallet")}
        out[sp] = o
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    res = live() if mode == "live" else lot()
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(ROOT / f"research/reverse_engineering/directional-maker/results/iter10_a1_{mode}.json", "w"), indent=1, default=str)
