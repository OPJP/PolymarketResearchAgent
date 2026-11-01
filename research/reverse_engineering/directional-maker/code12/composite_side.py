"""Iteration 12, PR12-F (EXPLORATORY: designed at 02:30 UTC after the per-type VALIDATE aggregates of PR12-C were seen):
the decoded side state machine per fill, with and without own state, on the lot (it12/typed_fills.parquet from
code12/typed_side.py).
  (i)   decided window (|mid_up - 0.5| > 0.4 at b - 3): the cheaper token (public);
  (ii)  no own inventory in the window before the fill (entry): the real-Chainlink posture (Binance stand-in if missing);
  (iii) own inventory and the filled order is an imbalance pairing bid (calldata original size not a schedule size,
        within 2% of |inventory|): the under-held outcome (own state + the order's own size);
  (iv)  otherwise: the held outcome (own state).
No-own-state version: (i), else the posture. Baselines: cheaper, favourite, held-only, posture-only.
Per fill and per order (first fill of each order), STUDY and VALIDATE (aggregate), per wallet and half.
    python code12/composite_side.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
STD = {500, 1000, 250, 125, 100, 62, 50, 12, 300, 40, 200, 2000, 25, 31, 20, 10, 5}
HALF_V = 1793232000


def main():
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet")
    y = (V.is_up == 1).to_numpy()
    mid = V.mid_up.to_numpy()
    post = np.where(np.isfinite(V.f_cl) & np.isfinite(mid), V.f_cl > mid, V.f_bn > mid)
    dec = np.abs(mid - 0.5) > 0.4
    cheap = mid < 0.5
    inv = V.inv.to_numpy()
    imb = np.abs(V.inv_first.to_numpy())
    orig = V.orig.to_numpy()
    pair = (~np.isin(orig, list(STD))) & (imb > 0) & (np.abs(orig - imb) <= 0.02 * imb)
    held = inv > 0
    comp = np.where(dec, cheap, np.where(inv == 0, post, np.where(pair, V.inv_first.to_numpy() < 0, held)))
    comp_nopair = np.where(dec, cheap, np.where(inv == 0, post, held))
    noown = np.where(dec, cheap, post)
    rules = {"composite_own": comp, "composite_own_no_size": comp_nopair, "no_own_state": noown, "posture": post,
             "cheaper": cheap, "favourite": ~cheap, "held_only": np.where(inv != 0, held, post)}
    first = ((V.b == V.first_b) & ~V.duplicated("oid")).to_numpy()
    out = {}
    for sp in ("study", "validate"):
        ms = (V.sp == sp).to_numpy() & np.isfinite(mid)
        rec = {"n": int(ms.sum()), "share_decided": round(float(dec[ms].mean()), 4), "share_entry": round(float((~dec & (inv == 0))[ms].mean()), 4),
               "share_pair": round(float((~dec & (inv != 0) & pair)[ms].mean()), 4)}
        for rn, r in rules.items():
            a = (r == y)
            rr = {"fill": round(float(a[ms].mean()), 4), "order": round(float(a[ms & first].mean()), 4)}
            for w in ("almach", "bosona", "momoney"):
                mw = ms & (V.w == w).to_numpy()
                rr[w] = round(float(a[mw].mean()), 4)
            if sp == "validate":
                h1 = (V.b < HALF_V).to_numpy()
                rr["halves"] = [round(float(a[ms & h1].mean()), 4), round(float(a[ms & ~h1].mean()), 4)]
            rr["by_branch"] = {"decided": round(float(a[ms & dec].mean()), 4), "entry": round(float(a[ms & ~dec & (inv == 0)].mean()), 4),
                               "pair": round(float(a[ms & ~dec & (inv != 0) & pair].mean()), 4),
                               "rest": round(float(a[ms & ~dec & (inv != 0) & ~pair].mean()), 4)}
            rec[rn] = rr
        by_day = {}
        for d in sorted(V.day[ms].unique()):
            md = ms & (V.day == d).to_numpy()
            by_day[str(pd.to_datetime(d, unit="s").date())] = {rn: round(float((r == y)[md].mean()), 3) for rn, r in rules.items()}
        rec["by_day"] = by_day
        out[sp] = rec
    (HERE.parent / "results" / "iter12_composite_side.json").write_text(json.dumps(out, indent=1))
    for sp in ("study", "validate"):
        r = out[sp]
        print(sp, r["n"], "decided", r["share_decided"], "entry", r["share_entry"], "pair", r["share_pair"])
        for rn in rules:
            print("  ", rn, r[rn]["fill"], r[rn]["order"], {k: r[rn][k] for k in ("almach", "bosona", "momoney")}, r[rn].get("halves"), r[rn]["by_branch"])
        print("  by day", {d: (v["composite_own"], v["no_own_state"], v["cheaper"]) for d, v in r["by_day"].items()})


if __name__ == "__main__":
    main()
