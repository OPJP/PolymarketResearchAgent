"""Iteration 13 (X130 follow-up, examinable form; with --exclude-own the filled order itself is removed from its level
before the book features are computed, X144 step 0): the side of each cluster filled order from inputs available at its MATCH
time without knowing its post: the Chainlink edge F_up(L = 1250 ms) - mid and the Up book's lean (microprice - mid,
top-of-book and 3-tick depth imbalance) just before the fill's trade message (dm_clob_raw full depth, 10-31 14-18; the
same quantities exist in the shared recorder's top-10 'q' books). Fit on fills before 16:00 UTC, test after; reported
for all fills and by the (unobservable at fill time) post class.
"""
from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
import live  # noqa: E402
import cl_source  # noqa: E402
from tracer_laws import spot  # noqa: E402

OUT = ROOT / ".cache/re/directional-maker/it13"


def feats(bw, own=None):
    b1, b0 = dict(bw[1]), dict(bw[0])
    if own is not None:
        sd, p, z = own
        d_ = b1 if sd == 1 else b0
        if p in d_:
            d_[p] = max(d_[p] - z, 0.0)
    bids = sorted(((p, z) for p, z in b1.items() if z > 1e-9), reverse=True)
    asks = sorted((p, z) for p, z in b0.items() if z > 1e-9)
    if not bids or not asks:
        return None
    bb, bz = bids[0]
    ba, az = asks[0]
    bd3 = sum(z for p, z in bids if p >= bb - 0.025)
    ad3 = sum(z for p, z in asks if p <= ba + 0.025)
    return (bb, ba, bz, az, bd3, ad3)


def main():
    o = pd.read_parquet(OUT / "fills_posts.parquet")
    o = o.sort_values("fill_ms")
    EX = "--exclude-own" in sys.argv
    o = o.reset_index(drop=True)
    pend = {}
    for w, g in o.groupby("w"):
        pend[w] = sorted(zip(g.fill_ms.astype(int), g.index))
    snaps, book = {}, {}
    H0, H1 = 1793455200, 1793469600
    for h in range(H0, H1, 3600):
        try:
            for r in live.iter_live("dm_clob_raw", h, min(h + 3600, H1)):
                k = r.get("k")
                if k == "bk":
                    bw = {1: {}, 0: {}}
                    for p, z in r.get("b", []):
                        bw[1][round(p, 3)] = z
                    for p, z in r.get("o", []):
                        bw[0][round(p, 3)] = z
                    book[r["w"]] = bw
                elif k == "pc":
                    w = r["w"]
                    bw = book.get(w)
                    if bw is None:
                        continue
                    s = int(r["s"])
                    q = pend.get(w)
                    while q and q[0][0] <= s:
                        fm, ix = q.pop(0)
                        r_ = o.loc[ix]
                        f = feats(bw, (int(r_.sd), round(float(r_.bp), 3), float(r_.orig)) if EX else None)
                        if f:
                            snaps[ix] = f
                    for row in r["c"]:
                        sd, p, z = row[0], round(row[1], 3), row[2]
                        if sd < 2:
                            bw[sd][p] = z
        except (zlib.error, EOFError, OSError) as e:
            print("read error", h, repr(e)[:60])
    o["snap"] = [snaps.get(ix) for ix in o.index]
    o = o[o.snap.notna()].copy()
    o[["bb", "ba", "bz", "az", "bd3", "ad3"]] = pd.DataFrame(o.snap.tolist(), index=o.index)
    o["mid"] = (o.bb + o.ba) / 2
    o["micro"] = (o.bb * o.az + o.ba * o.bz) / (o.az + o.bz)
    o["imb_top"] = (o.bz - o.az) / (o.bz + o.az)
    o["imb3"] = (o.bd3 - o.ad3) / (o.bd3 + o.ad3)
    from polyrea.workflows.updown_study import fetch_windows
    K = {}
    for m in fetch_windows(sorted(set(o.w))).values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    o["K"] = o.w.map(K)
    o["start"] = o.w.str.rsplit("-", n=1).str[1].astype(int)
    o["end"] = o.start + np.where(o.w.str.contains("-15m-"), 900, 300)
    L = 1250
    clv = cl_source.cl_values(sorted(set(((o.fill_ms - L) // 1000).astype(int))), allow_sealed=False, fetch=False)
    sp = spot(int(o.fill_ms.min() // 1000) - 7200, int(o.fill_ms.max() // 1000) + 5)
    cl = ((o.fill_ms - L) // 1000).map(clv).to_numpy(float)
    sig = sp.sigma((o.fill_ms // 1000).to_numpy(), look=300) * 1.4
    tau = np.maximum(o.end.to_numpy() - o.fill_ms.to_numpy() / 1000, 1.0)
    o["F"] = norm.cdf(np.log(cl / o.K.to_numpy(float)) / (sig * np.sqrt(tau)))
    o = o[o.F.notna()].copy()
    o["e_cl"] = o.F - o.mid
    o["e_mp"] = o.micro - o.mid
    o["y"] = (o.is_up == 1).astype(int)
    from sklearn.linear_model import LogisticRegression
    fit = (o.fill_ms < 1793462400000).to_numpy()
    sets = {"chainlink_only": ["e_cl"], "book_only": ["e_mp", "imb_top", "imb3"], "both": ["e_cl", "e_mp", "imb_top", "imb3"]}
    res = {"n_fills": int(len(o)), "fit_n": int(fit.sum()), "test_n": int((~fit).sum())}
    models = {}
    for nm, fs in sets.items():
        X = o[fs].to_numpy(float)
        mu, sd = X[fit].mean(0), X[fit].std(0) + 1e-9
        m = LogisticRegression(C=1.0).fit((X[fit] - mu) / sd, o.y[fit])
        models[nm] = (m, mu, sd, fs)
        res[nm + "_coef"] = [round(float(c), 3) for c in m.coef_[0]]
    for cls_name, cm in (("all", np.ones(len(o), bool)), ("class_i", (o.post_at_touch == 1).to_numpy()), ("class_ii", (o.post_at_touch == 0).to_numpy())):
        t = ~fit & cm
        r = {"n_test": int(t.sum()), "posture_sign": float(((o.e_cl > 0).astype(int) == o.y)[t].mean()) if t.any() else None,
             "cheaper": float(((o.mid < 0.5).astype(int) == o.y)[t].mean()) if t.any() else None}
        for nm, (m, mu, sd, fs) in models.items():
            p = m.predict((o[fs].to_numpy(float)[t] - mu) / sd)
            r[nm] = float((p == o.y[t]).mean()) if t.any() else None
        res[cls_name] = r
    res["per_wallet_both_test"] = {}
    m, mu, sd, fs = models["both"]
    for wname, g in o[~fit].groupby("maker"):
        p = m.predict((g[fs].to_numpy(float) - mu) / sd)
        res["per_wallet_both_test"][wname[:10]] = [int(len(g)), float((p == g.y).mean()), float(((g.e_cl > 0).astype(int) == g.y).mean())]
    print(json.dumps(res, indent=1))
    (HERE.parent / ("results/iter13_match_book_exown.json" if EX else "results/iter13_match_book.json")).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
