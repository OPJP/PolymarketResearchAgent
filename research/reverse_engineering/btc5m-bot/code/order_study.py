"""Iteration 2: order-level lead-lag (chain + Binance 1-s only; diagnostics may look at non-PIT seconds, never used in
a frozen rule). For each cluster order (orderHash) the first fill's block second s, role and side; agreement of the
side with the sign of the Binance return of kline s+k, for k = -12..+3; and per-k agreement among orders with no
visible move in klines s-4..s-2.
Usage: python order_study.py A B"""
import os, sys, glob, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from spot import Spot
from build_fills import load_fills
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"

if __name__ == "__main__":
    A, B = int(sys.argv[1]), int(sys.argv[2])
    f = load_fills(); f = f[(f.ts >= A) & (f.ts < B) & f.cid.notna()]
    sp = Spot(); lp = np.log(sp.px)
    r1 = lambda t: (lp[t - sp.s0 + 1] - lp[t - sp.s0]) * 1e4  # return of kline t: close(t) - close(t-1)
    o = f.sort_values(["block", "li"]).groupby("oh").agg(ts=("ts", "first"), role=("role", "first"), wallet=("wallet", "first"),
        is_up=("is_up", "first"), cid=("cid", "first"), rel=("rel", "first"), n=("ts", "size"), shares=("shares", "sum"),
        roles=("role", lambda x: "".join(sorted(set(x)))), price=("price", "first"), span=("ts", lambda x: int(x.max() - x.min()))).reset_index()
    o = o[(o.rel >= 0) & (o.rel < 300)]
    sg = np.where(o.is_up, 1.0, -1.0)
    s = o.ts.to_numpy().astype(np.int64)
    res = {"orders": int(len(o)), "kinds": o.roles.value_counts(normalize=True).round(3).to_dict()}
    # kline s+k return is [s+k-1 close -> s+k close] in this indexing: use r(t) = close(t) - close(t-1), i.e. move during second t
    rk = {k: (lp[s + k - sp.s0] - lp[s + k - 1 - sp.s0]) * 1e4 for k in range(-12, 4)}
    for kind, sel in [("T_first", o.role == "T"), ("M_first", o.role == "M")]:
        sel = sel.to_numpy(); d = {}
        for k, r in rk.items():
            nz = sel & (r != 0)
            d[k] = [round(float((np.sign(r[nz]) == sg[nz]).mean()), 4), round(float(nz.sum() / max(sel.sum(), 1)), 3)]
        res[f"agree_by_k_{kind}"] = d
        vis = rk[-2] + rk[-3] + rk[-4]          # visible at s: klines s-2 (ends s-1), s-3, s-4
        quiet = sel & (np.abs(vis) < 0.5)
        d2 = {}
        for k in (-6, -5, -4, -3, -2, -1, 0, 1):
            nz = quiet & (rk[k] != 0)
            d2[k] = [round(float((np.sign(rk[k][nz]) == sg[nz]).mean()), 4), int(nz.sum())]
        res[f"quiet_visible_{kind}"] = {"share_quiet": round(float(quiet.sum() / max(sel.sum(), 1)), 3), "agree_by_k": d2}
        for lo, hi in [(0, 0.5), (0.5, 1), (1, 2), (2, 4), (4, 1e9)]:
            m = sel & (np.abs(vis) >= lo) & (np.abs(vis) < hi) & (vis != 0)
            res.setdefault(f"agree_vis3_{kind}", {})[f"{lo}-{hi}bp"] = [round(float((np.sign(vis[m]) == sg[m]).mean()), 4), round(float(m.sum() / max(sel.sum(), 1)), 3)]
    # events: unique (cid, is_up, ts) over wallets for taker-first orders
    ev = o[o.role == "T"].groupby(["cid", "is_up", "ts"]).agg(n_orders=("oh", "size"), n_wallets=("wallet", "nunique")).reset_index()
    res["taker_events"] = {"n": int(len(ev)), "mean_orders": round(float(ev.n_orders.mean()), 2), "share_3_wallets": round(float((ev.n_wallets == 3).mean()), 3)}
    json.dump(res, open(f"{R}/results_order_leadlag_iter2.json", "w"), indent=1)
    print(json.dumps(res)[:3000])
    o.to_parquet(f"{C}/orders.parquet", index=False)
