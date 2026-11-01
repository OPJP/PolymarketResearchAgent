"""iteration 15 (post hoc): quote-unit posture accuracy by |F - mid| band on 10-31 14-18 (Chainlink noise regime, CL/futures
1-s sd ratio 8.2) and 11-01 07-08 (clean stream, ratio 0.92): is the rule the same and only the edge distribution
different? Pure non-extreme 500 posts, exact publish clock where recorded else stamp lag 1,432 ms, k 1.0 x futures sigma300."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE.parent / "code14"))
from lagged_quote import fut_mid, sec_sigma, cl_source, live
out = {}
for a, b in ((1793455200, 1793469600), (1793516400, 1793520000)):
    A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet"); A = A[A.mid_prev.notna()].reset_index(drop=True)
    bid = np.where(A.sd == 1, A.p, 1 - A.p); A = A[(A.dz == 500) & (bid > 0.03) & (bid < 0.97)].reset_index(drop=True)
    E, M = fut_mid(a - 900, b); sf = sec_sigma(E, M, 300)
    clv = cl_source.cl_values(list(range(a - 60, b + 1)), allow_sealed=False, fetch=False)
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
    t = A.s.to_numpy(np.int64)
    S = clv.reindex((t - 1432) // 1000).to_numpy(float)
    if pub:
        Pb = pd.DataFrame(pub, columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts").sort_values("P")
        pm, pv = Pb.P.to_numpy(np.int64), Pb.v.to_numpy(float)
        i = np.searchsorted(pm, t, side="right") - 1
        S = np.where((i >= 0) & (t >= pm.min() + 5000), pv[np.clip(i, 0, None)], S)
    st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy(); en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300)
    tau = np.maximum(en - t / 1000, 1.0); kk = A.w.map(K).to_numpy(float); mid = A.mid_prev.to_numpy(float); y = (A.sd == 1).to_numpy(float)
    F = norm.cdf((S - kk) / (sf.reindex(t // 1000).to_numpy(float) * np.sqrt(tau))); ok = np.isfinite(F) & np.isfinite(mid)
    e = np.abs(F - mid); P = F > mid
    r = {"n": int(ok.sum())}
    for lo, hi in ((0, 0.02), (0.02, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 1.01)):
        m = ok & (e >= lo) & (e < hi)
        r[f"edge_{lo}-{hi}"] = [round(float((P[m] == (y[m] == 1)).mean()), 3) if m.sum() else None, int(m.sum()), round(float(m.sum() / ok.sum()), 3)]
    out[f"{a}_{b}"] = r; print(a, b, r, flush=True)
(HERE.parent / "results/iter15_edge_bands.json").write_text(json.dumps(out, indent=1))
