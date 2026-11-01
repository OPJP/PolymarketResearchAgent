"""X213 (mechanics panel iter-14 P5): exactness of the map -> match relation at same-ms co-repricings, a feed-class
fingerprint (competing explanation 7 of iteration 15). In a Bo3 the match probability is LINEAR in the current map's
probability p at a fixed series state and future-map strength q (map 1 at 0-0: P = q^2 + 2q(1-q) p; map 2 at 1-0:
q + (1-q) p; at 0-1: q p; map 3: p). So if the bot holds one map value and computes the match quote itself, every
co-repricing pair (map burst top, match burst top on the same team's token, signed within 50 ms; at least 4 pairs) of one (event, map,
token) lies on one line up to the whole-cent rounding of both quotes (residual SD about 0.4c). An odds feed with its own
match line would scatter. Null: the same map bursts paired with match bursts of the same (event, map, token) taken at
random other moments (>= 30 s away), same counts. Historical filled maker orders 16-22 Oct (orders.parquet), CS2 and
Dota, BUILD and VALIDATE pooled (descriptive; no rule is fitted).
Output: results/series_identity.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def bursts(g):
    g = g.sort_values("sign_ms")
    s, p = g.sign_ms.to_numpy(float), g.price.to_numpy(float)
    rows, i = [], 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] - s[j] <= 50:
            j += 1
        rows.append((s[i], float(p[i:j + 1].max())))
        i = j + 1
    return np.array(rows) if rows else np.zeros((0, 2))


def fit_sd(x, y):
    if len(x) < 4 or np.std(x) < 1e-9:
        return None
    b, a = np.polyfit(x, y, 1)
    r = y - (a + b * x)
    return float(np.std(r)), float(np.mean(np.abs(r) <= 0.01 + 1e-9)), float(b)


def main():
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "cid", "oi", "smt", "event", "role"])
    o = o[(o.role == "maker") & (o.sign_ms > 1.7e12)]
    mk = json.load(open(OUT / "markets_dev.json"))
    mapno = {c: int(m.group(1)) for c, x in mk.items() if (m := re.search(r"Map (\d)", x.get("question", "")))}
    rng = np.random.default_rng(0)
    res_rows = []
    for ev, g in o.groupby("event"):
        mt = g[g.smt == "moneyline"]
        if mt.empty:
            continue
        for oi in (0, 1):
            B_match = bursts(mt[mt.oi == oi])
            if len(B_match) < 5:
                continue
            for cid, h in g[(g.smt == "child_moneyline") & (g.oi == oi)].groupby("cid"):
                Bm = bursts(h)
                if len(Bm) < 5:
                    continue
                k = np.searchsorted(B_match[:, 0], Bm[:, 0])
                pairs = []
                for i, t in enumerate(Bm[:, 0]):
                    best = None
                    for kk in (k[i] - 1, k[i]):
                        if 0 <= kk < len(B_match) and abs(B_match[kk, 0] - t) <= 50:
                            best = kk
                    if best is not None:
                        pairs.append((Bm[i, 1], B_match[best, 1], t))
                if len(pairs) < 4:
                    continue
                P = np.array(pairs)
                # null: same map bursts, match bursts drawn from moments >= 30 s away within the map's active span
                lo, hi = P[:, 2].min(), P[:, 2].max()
                cand = B_match[(B_match[:, 0] >= lo - 60000) & (B_match[:, 0] <= hi + 60000)]
                nul = []
                for x, _, t in P:
                    far = cand[np.abs(cand[:, 0] - t) >= 30000]
                    if len(far):
                        nul.append((x, far[rng.integers(len(far)), 1]))
                N = np.array(nul) if nul else np.zeros((0, 2))
                f = fit_sd(P[:, 0], P[:, 1])
                fn = fit_sd(N[:, 0], N[:, 1]) if len(N) >= 4 else None
                if f is None:
                    continue
                res_rows.append({"event": ev, "cid": cid[:10], "map": mapno.get(cid), "oi": oi, "pairs": int(len(P)),
                                 "sd_c": f[0] * 100, "within1c": f[1], "slope": f[2],
                                 "null_sd_c": fn[0] * 100 if fn else np.nan, "null_within1c": fn[1] if fn else np.nan,
                                 "map_range_c": float((P[:, 0].max() - P[:, 0].min()) * 100)})
    R = pd.DataFrame(res_rows)
    R5 = R[R.map_range_c >= 5]  # units where the map value actually moved
    out = {"units": int(len(R)), "units_map_moved_5c": int(len(R5)), "pairs": int(R.pairs.sum())}
    for nm, X in (("all", R), ("map_moved_5c", R5)):
        w = X.pairs.to_numpy(float)
        out[nm] = {"median_sd_c": round(float(X.sd_c.median()), 2), "median_null_sd_c": round(float(X.null_sd_c.median()), 2),
                   "pairs_weighted_within1c": round(float(np.average(X.within1c, weights=w)), 3),
                   "pairs_weighted_null_within1c": round(float(np.nanmean(X.null_within1c)), 3),
                   "units_sd_below_0p6c": int((X.sd_c <= 0.6).sum()), "units_sd_below_null": int((X.sd_c < X.null_sd_c).sum()),
                   "slope_by_map": {str(k): round(float(v), 3) for k, v in X.groupby("map").slope.median().items()}}
    R.to_parquet(OUT / "iter15" / "series_identity_units.parquet", index=False)
    (RES / "series_identity.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
