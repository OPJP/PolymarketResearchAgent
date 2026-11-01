"""X213 uncensored form: the same identity test on the BUILD-live add bursts (iteration-12 slot_vrel_rows: V_after =
its validated own top after each add burst on the recorded book, 10-31 12-18). Pairs = a map-book add burst and a
match-book add burst of the same event on the same team's token within 50 ms. Per (event, map, token) with >= 4 pairs:
OLS line, residual SD, share within 1c; null = map bursts paired with match V_after at random moments >= 30 s away.
Output: results/series_identity_live.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
d = pd.read_parquet(OUT / "iter12/slot_vrel_rows.parquet")
d = d[(d.kind == "add") & d.V_after.notna()].copy()
d["event"] = d.slug.str.replace(r"-game\d$", "", regex=True)
d["book"] = np.where(d.slug.str.contains(r"-game\d$"), d.slug.str.extract(r"-game(\d)$")[0], "match")
rng = np.random.default_rng(0)
rows = []
for (ev, oi), g in d.groupby(["event", "oi"]):
    m = g[g.book == "match"].sort_values("t")
    if len(m) < 4:
        continue
    mt, mv = m.t.to_numpy(float), m.V_after.to_numpy(float)
    for bk, h in g[g.book != "match"].groupby("book"):
        ht, hv = h.t.to_numpy(float), h.V_after.to_numpy(float)
        k = np.searchsorted(mt, ht)
        P = []
        for i in range(len(ht)):
            for kk in (k[i] - 1, k[i]):
                if 0 <= kk < len(mt) and abs(mt[kk] - ht[i]) <= 50:
                    P.append((hv[i], mv[kk], ht[i]))
                    break
        if len(P) < 4:
            continue
        P = np.array(P)
        if np.std(P[:, 0]) < 1e-9:
            continue
        b, a = np.polyfit(P[:, 0], P[:, 1], 1)
        r = P[:, 1] - (a + b * P[:, 0])
        N = []
        for x, _, t in P:
            far = np.where(np.abs(mt - t) >= 30000)[0]
            if len(far):
                N.append((x, mv[far[rng.integers(len(far))]]))
        N = np.array(N)
        if len(N) >= 4 and np.std(N[:, 0]) > 1e-9:
            bn, an = np.polyfit(N[:, 0], N[:, 1], 1)
            rn = N[:, 1] - (an + bn * N[:, 0])
        else:
            rn = np.array([np.nan])
        rows.append({"event": ev, "map": bk, "oi": int(oi), "pairs": int(len(P)), "sd_c": float(np.std(r) * 100),
                     "within1c": float(np.mean(np.abs(r) <= 0.01 + 1e-9)), "slope": float(b),
                     "null_sd_c": float(np.nanstd(rn) * 100), "null_within1c": float(np.nanmean(np.abs(rn) <= 0.01 + 1e-9)),
                     "map_range_c": float((P[:, 0].max() - P[:, 0].min()) * 100)})
R = pd.DataFrame(rows)
out = {"units": int(len(R)), "pairs": int(R.pairs.sum()) if len(R) else 0}
if len(R):
    w = R.pairs.to_numpy(float)
    out.update({"median_sd_c": round(float(R.sd_c.median()), 2), "median_null_sd_c": round(float(R.null_sd_c.median()), 2),
                "pairs_weighted_within1c": round(float(np.average(R.within1c, weights=w)), 3),
                "null_within1c_mean": round(float(R.null_within1c.mean()), 3),
                "units_sd_below_0p6c": int((R.sd_c <= 0.6).sum()), "units": R.round(3).to_dict("records")})
(RES / "series_identity_live.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "units"}, indent=1)); print(R.round(2).to_string() if len(R) else "no units")
