"""iteration 15 (post hoc, X160 follow-up): does the engine price with the CHAINLINK stream's own volatility?
Per block, the 300-s sd of 1-s Chainlink changes vs the 300-s sd of 1-s Binance USD-M mid changes, and the quote-unit side
(pure non-extreme 500 posts, exact publish clock where dy_rtds exists, else stamp lag 1,432 ms) with sigma = k x the
Chainlink sigma300 against sigma = k x the futures sigma300, on 10-31 14-18 and 11-01 07-08."""
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
    clv = cl_source.cl_values(list(range(a - 900, b + 1)), allow_sealed=False, fetch=False)
    secs = np.arange(a - 900, b + 1); cl = clv.reindex(secs).ffill()
    scl = pd.Series(np.diff(cl.to_numpy(), prepend=np.nan), index=secs).rolling(300, min_periods=150).std().shift(1)
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
    if pub:
        Pb = pd.DataFrame(pub, columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts").sort_values("P")
        pm, pv = Pb.P.to_numpy(np.int64), Pb.v.to_numpy(float)
        i = np.searchsorted(pm, t, side="right") - 1
        S = np.where((i >= 0) & (t >= pm.min() + 5000), pv[np.clip(i, 0, None)], np.nan)
    else:
        S = np.full(len(t), np.nan)
    S = np.where(np.isfinite(S), S, clv.reindex((t - 1432) // 1000).to_numpy(float))
    st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy(); en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300)
    tau = np.maximum(en - t / 1000, 1.0); kk = A.w.map(K).to_numpy(float); mid = A.mid_prev.to_numpy(float); y = (A.sd == 1).to_numpy(float)
    s_f = sf.reindex(t // 1000).to_numpy(float); s_c = scl.reindex(t // 1000).to_numpy(float)
    r = {"n": int(len(A)), "sigma_ratio_cl_over_fut_median": round(float(np.nanmedian(s_c / s_f)), 3),
         "sigma_fut_median": round(float(np.nanmedian(s_f)), 3), "sigma_cl_median": round(float(np.nanmedian(s_c)), 3),
         "cheaper": round(float(((mid < 0.5) == (y == 1)).mean()), 3)}
    half = t < (a + (b - a) // 2) * 1000
    for nm, sg in (("fut", s_f), ("cl", s_c)):
        for k in (0.5, 0.7, 1.0, 1.4, 2.0):
            F = norm.cdf((S - kk) / (k * sg * np.sqrt(tau))); ok = np.isfinite(F) & np.isfinite(mid)
            P = (F > mid)
            r[f"{nm}_k{k}"] = [round(float((P[ok] == (y[ok] == 1)).mean()), 3), round(float((P[ok & half] == (y[ok & half] == 1)).mean()), 3), round(float((P[ok & ~half] == (y[ok & ~half] == 1)).mean()), 3)]
    out[f"{a}_{b}"] = r
    print(a, b, r, flush=True)
(HERE.parent / "results/iter15_cl_sigma.json").write_text(json.dumps(out, indent=1))
