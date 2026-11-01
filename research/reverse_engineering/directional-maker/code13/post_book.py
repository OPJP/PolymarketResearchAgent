"""X130 (panel iter12 information I12-1, strong form at the decision unit): race Polymarket's own book state against the
Chainlink posture at the POST time of every cluster filled order (development block 10-31 14-18, dm_clob_raw).

For each post (code13/fills_posts.parquet: the add that put the filled order in the book), the Up book just BEFORE the
post's price_change message is applied: best bid / ask, depth at the touch and within 3 ticks on each side (the cluster's
own identified orders are not removable here except the posted order itself, which is not yet in the book), microprice.
Inputs: Chainlink edge F_up(L = 1250 ms) - mid, book pressure microprice - mid, depth imbalance. Side = the outcome of the
filled order. Fit (logistic, standardised) on posts before 16:00 UTC, score after; market-only (book) and Chainlink-only
models reported separately; per class (i) quote move / (ii) market came.
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


def main():
    o = pd.read_parquet(OUT / "fills_posts.parquet")
    o = o[o.post_ms.notna()].copy()
    o["post_ms"] = o.post_ms.astype(np.int64)
    want = {}
    for w, s in zip(o.w, o.post_ms):
        want.setdefault(w, set()).add(int(s))
    snaps = {}
    book = {}
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
                    if s in want.get(w, ()) and (w, s) not in snaps:
                        bids = sorted(((p, z) for p, z in bw[1].items() if z > 1e-9), reverse=True)
                        asks = sorted((p, z) for p, z in bw[0].items() if z > 1e-9)
                        if bids and asks:
                            bb, bz = bids[0]
                            ba, az = asks[0]
                            bd3 = sum(z for p, z in bids if p >= bb - 0.025)
                            ad3 = sum(z for p, z in asks if p <= ba + 0.025)
                            snaps[(w, s)] = (bb, ba, bz, az, bd3, ad3)
                    for row in r["c"]:
                        sd, p, z = row[0], round(row[1], 3), row[2]
                        if sd < 2:
                            bw[sd][p] = z
        except (zlib.error, EOFError, OSError) as e:
            print("read error", h, repr(e)[:60])
    S = pd.Series(snaps)
    o["snap"] = [snaps.get((w, int(s))) for w, s in zip(o.w, o.post_ms)]
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
    clv = cl_source.cl_values(sorted(set(((o.post_ms - L) // 1000).astype(int))), allow_sealed=False, fetch=False)
    sp = spot(int(o.post_ms.min() // 1000) - 7200, int(o.post_ms.max() // 1000) + 5)
    cl = ((o.post_ms - L) // 1000).map(clv).to_numpy(float)
    sig = sp.sigma((o.post_ms // 1000).to_numpy(), look=300) * 1.4
    tau = np.maximum(o.end.to_numpy() - o.post_ms.to_numpy() / 1000, 1.0)
    o["F"] = norm.cdf(np.log(cl / o.K.to_numpy(float)) / (sig * np.sqrt(tau)))
    o = o[o.F.notna()].copy()
    o["e_cl"] = o.F - o.mid
    o["e_mp"] = o.micro - o.mid
    o["y"] = (o.is_up == 1).astype(int)
    from sklearn.linear_model import LogisticRegression
    fit = (o.post_ms < 1793462400000).to_numpy()
    feats = {"chainlink_only": ["e_cl"], "book_only": ["e_mp", "imb_top", "imb3"], "both": ["e_cl", "e_mp", "imb_top", "imb3"]}
    res = {"n_posts": int(len(o)), "fit_n": int(fit.sum()), "test_n": int((~fit).sum())}
    for cls_name, cm in (("all", np.ones(len(o), bool)), ("class_i", (o.post_at_touch == 1).to_numpy()), ("class_ii", (o.post_at_touch == 0).to_numpy())):
        r = {"n_test": int((~fit & cm).sum()),
             "posture_sign_test": float(((o.e_cl > 0).astype(int) == o.y)[~fit & cm].mean()),
             "micro_sign_test": float(((o.e_mp > 0).astype(int) == o.y)[~fit & cm].mean()),
             "imb3_sign_test": float(((o.imb3 > 0).astype(int) == o.y)[~fit & cm].mean()),
             "cheaper_test": float(((o.mid < 0.5).astype(int) == o.y)[~fit & cm].mean())}
        for nm, fs in feats.items():
            X = o[fs].to_numpy(float)
            mu, sd = X[fit & cm].mean(0), X[fit & cm].std(0) + 1e-9
            m = LogisticRegression(C=1.0).fit((X[fit & cm] - mu) / sd, o.y[fit & cm])
            p = m.predict((X[~fit & cm] - mu) / sd)
            r[nm] = {"acc_test": float((p == o.y[~fit & cm]).mean()), "coef": [round(float(c), 3) for c in m.coef_[0]]}
        res[cls_name] = r
    print(json.dumps(res, indent=1))
    (HERE.parent / "results/iter13_post_book.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
