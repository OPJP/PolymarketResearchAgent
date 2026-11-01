"""iteration 15 (X160 replication, X170 classes): the quote-unit side on the current development block 11-01 07:00-
(Sunday, BTC 5m resumed at 07:00 with 500 orders per calldata), exact publish clock (dy_rtds P) and the safe lag,
k 1.0 and 1.4 x futures sigma300, by class (500 non-extreme / extreme, others), by family and by time left."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE.parent / "code14"))
from lagged_quote import fut_mid, sec_sigma, cl_source, live
a, b = int(sys.argv[1]), int(sys.argv[2])
A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet"); A = A[A.mid_prev.notna()].reset_index(drop=True)
E, M = fut_mid(a - 600, b); sig = sec_sigma(E, M, 300)
from polyrea.workflows.updown_study import fetch_windows
raw = fetch_windows(sorted(set(A.w))); K = {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
pub = []
for r in live.iter_live("dy_rtds", a - 60, b):
    if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
        pub.append((int(r["P"]), int(r["ts"]) // 1000, float(r["v"])))
Pb = pd.DataFrame(pub, columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts").sort_values("P")
pm, pv = Pb.P.to_numpy(np.int64), Pb.v.to_numpy(float)
clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=False)
t = A.s.to_numpy(np.int64); st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300); tau = np.maximum(en - t / 1000, 1.0)
s0 = sig.reindex(t // 1000).to_numpy(float); kk = A.w.map(K).to_numpy(float); mid = A.mid_prev.to_numpy(float); y = (A.sd == 1).to_numpy(float)
bid = np.where(A.sd == 1, A.p, 1 - A.p)
cls = np.where(A.dz == 500, np.where((bid > 0.03) & (bid < 0.97), "500_mid", "500_extreme"), A.dz.astype(int).astype(str))
i = np.searchsorted(pm, t, side="right") - 1; cl_pub = np.where(i >= 0, pv[np.clip(i, 0, None)], np.nan)
cl_safe = clv.reindex((t - 1432) // 1000).to_numpy(float)
out = {"n_posts": int(len(A)), "classes": pd.Series(cls).value_counts().to_dict()}
for ck, cl in (("exact_publish", cl_pub), ("safe1432", cl_safe)):
    for k in (1.0, 1.4):
        F = norm.cdf((cl - kk) / (k * s0 * np.sqrt(tau))); P = (F > mid).astype(float); ok = np.isfinite(F) & np.isfinite(mid)
        row = {}
        for c in ("500_mid", "500_extreme", "1000", "250", "62"):
            m = ok & (cls == c); row[c] = [round(float((P[m] == y[m]).mean()), 3) if m.sum() else None, int(m.sum())]
        for fam in ("-5m-", "-15m-"):
            m = ok & (cls == "500_mid") & A.w.str.contains(fam).to_numpy(); row["500_mid" + fam.strip("-")] = [round(float((P[m] == y[m]).mean()), 3) if m.sum() else None, int(m.sum())]
        for lo, hi in ((0, 60), (60, 120), (120, 300), (300, 901)):
            m = ok & (cls == "500_mid") & (tau > lo) & (tau <= hi); row[f"500_mid_tau{lo}-{hi}"] = [round(float((P[m] == y[m]).mean()), 3) if m.sum() else None, int(m.sum())]
        m = ok & (cls == "500_mid"); row["500_mid_cheaper"] = round(float((((mid < 0.5) == (y == 1)))[m].mean()), 3) if m.sum() else None
        row["500_mid_always_up"] = round(float(y[m].mean()), 3) if m.sum() else None
        out[f"{ck}_k{k}"] = row
print(json.dumps(out, indent=1))
(HERE.parent / "results" / f"iter15_qu_today_{a}_{b}.json").write_text(json.dumps(out, indent=1))
