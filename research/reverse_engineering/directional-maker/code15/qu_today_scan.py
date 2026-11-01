"""iteration 15 (post hoc diagnostic of the X160 replication failure on 11-01 07:00-): reference x k scan on the
non-extreme 500 posts at the touch. References: the Chainlink report published before the post (exact clock); the Binance
USD-M mid 50 ms before the post minus its rolling 600-s median basis to Chainlink (point in time). Market-only: the
outcome whose Polymarket mid fell over 1 s; cheaper token. Per window: majority side vs the window's posture."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE.parent / "code14"))
from lagged_quote import fut_mid, at, sec_sigma, live
a, b = int(sys.argv[1]), int(sys.argv[2])
A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet"); A = A[A.mid_prev.notna()].reset_index(drop=True)
bid = np.where(A.sd == 1, A.p, 1 - A.p); A = A[(A.dz == 500) & (bid > 0.03) & (bid < 0.97)].reset_index(drop=True)
E, M = fut_mid(a - 900, b); sig = sec_sigma(E, M, 300)
from polyrea.workflows.updown_study import fetch_windows
raw = fetch_windows(sorted(set(A.w))); K = {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
pub = []
for r in live.iter_live("dy_rtds", a - 900, b):
    if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
        pub.append((int(r["P"]), int(r["ts"]), float(r["v"])))
Pb = pd.DataFrame(pub, columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts").sort_values("P")
pm, pv, pts = Pb.P.to_numpy(np.int64), Pb.v.to_numpy(float), Pb.ts.to_numpy(np.int64)
# basis: futures mid at each report stamp minus the report value; rolling median over the previous 600 s of publishes
fb = at(E, M, pts) - pv
basis = pd.Series(fb).rolling(600, min_periods=60).median().shift(1).to_numpy()
t = A.s.to_numpy(np.int64); st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300); tau = np.maximum(en - t / 1000, 1.0)
s0 = sig.reindex(t // 1000).to_numpy(float); kk = A.w.map(K).to_numpy(float); mid = A.mid_prev.to_numpy(float); y = (A.sd == 1).to_numpy(float)
i = np.searchsorted(pm, t, side="right") - 1; ii = np.clip(i, 0, None)
cl_pub = np.where(i >= 0, pv[ii], np.nan); bas = np.where(i >= 0, basis[ii], np.nan)
fut = at(E, M, t - 50) - bas
out = {"n": int(len(A)), "windows": int(A.w.nunique()), "always_up": round(float(y.mean()), 3),
       "cheaper": round(float(((mid < 0.5) == (y == 1)).mean()), 3)}
for nm, S in (("cl_exact", cl_pub), ("fut_minus_basis", fut)):
    for k in (0.3, 0.5, 0.7, 1.0, 1.4, 2.0, 3.0):
        F = norm.cdf((S - kk) / (k * s0 * np.sqrt(tau))); ok = np.isfinite(F)
        out[f"{nm}_k{k}"] = round(float(((F > mid) == (y == 1))[ok].mean()), 3)
    F = S > kk; out[f"{nm}_itm"] = round(float((F == (y == 1))[np.isfinite(S)].mean()), 3)
out["fav_buy"] = round(float(((mid > 0.5) == (y == 1)).mean()), 3)
# per window
A["y"] = y; A["Fk1"] = norm.cdf((cl_pub - kk) / (s0 * np.sqrt(tau))); A["post"] = (A.Fk1 > mid).astype(float)
wv = A.groupby("w").agg(n=("y", "size"), up_share=("y", "mean"), post_up=("post", "mean"), mid=("mid_prev", "mean"))
out["per_window"] = wv.round(3).reset_index().to_dict("records")
print(json.dumps(out, indent=1)[:3500])
(HERE.parent / "results" / f"iter15_qu_today_scan_{a}_{b}.json").write_text(json.dumps(out, indent=1))
