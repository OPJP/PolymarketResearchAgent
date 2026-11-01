"""Iteration 14 point-in-time check of the quote-unit side: (a) stamp lag 1,432 ms (p90 publish delay, R8's convention)
on the rebuilt 10-31 14-18 quote unit; (b) the exact public publish ms of each report (dy_rtds 'P', from 17:29) on the
posts of 17:29-18:00, against the stamp-lag rules on the same posts."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE))
from lagged_quote import fut_mid, sec_sigma, cl_source, live
a, b = 1793455200, 1793469600
A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet"); A = A[A.mid_prev.notna() & A.dz.isin([500.0, 1000.0])]
E, M = fut_mid(a, b); sig = sec_sigma(E, M, 300)
clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=False)
from polyrea.workflows.updown_study import fetch_windows
raw = fetch_windows(sorted(set(A.w))); K = {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
t = A.s.to_numpy(np.int64); st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300); tau = np.maximum(en - t / 1000, 1.0)
s0 = sig.reindex(t // 1000).to_numpy(float); kk = A.w.map(K).to_numpy(float); mid = A.mid_prev.to_numpy(float); y = (A.sd == 1).to_numpy(float)
half = t < (a + (b - a) // 2) * 1000
def acc_for(cl, k, m):
    F = norm.cdf((cl - kk) / (k * s0 * np.sqrt(tau))); P = (F > mid).astype(float); ok = np.isfinite(F) & m
    return [round(float((P[ok] == y[ok]).mean()), 4) if ok.sum() else None, int(ok.sum())]
out = {}
for L in (1000, 1250, 1432):
    cl = clv.reindex((t - L) // 1000).to_numpy(float)
    for k in (1.0, 1.4):
        out[f"L{L}_k{k}"] = {"fit": acc_for(cl, k, half), "test": acc_for(cl, k, ~half)}
# exact publish ms from dy_rtds (btc chainlink)
pub = []
for r in live.iter_live("dy_rtds", 1793467740, b):
    if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
        pub.append((int(r["P"]), int(r["ts"]) // 1000, float(r["v"])))
P_ = pd.DataFrame(pub, columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts")
P_ = P_.sort_values("P")
pm, pv = P_.P.to_numpy(np.int64), P_.v.to_numpy(float)
i = np.searchsorted(pm, t, side="right") - 1
cl_pub = np.where(i >= 0, pv[np.clip(i, 0, None)], np.nan)
late = t >= int(P_.P.min()) + 5000 if len(P_) else np.zeros(len(t), bool)
d = (P_.P - P_.ts * 1000)
out["publish_delay_ms_q"] = np.percentile(d, [10, 50, 90]).round(0).tolist() if len(P_) else None
for k in (1.0, 1.4):
    out[f"exact_publish_k{k}_17:29-18:00"] = acc_for(cl_pub, k, late)
    for L in (1000, 1250, 1432):
        out[f"L{L}_k{k}_17:29-18:00"] = acc_for(clv.reindex((t - L) // 1000).to_numpy(float), k, late)
print(json.dumps(out)); (HERE.parent / "results/iter14_qu_pit.json").write_text(json.dumps(out, indent=1))
# split of the exact-publish span: 17:29-17:41 vs 17:41-18:00 (dx_clob covers only the second)
for nm, m_ in (("17:29-17:41", late & (t < 1793468460000)), ("17:41-18:00", late & (t >= 1793468460000))):
    out[f"exact_publish_k1.0_{nm}"] = acc_for(cl_pub, 1.0, m_)
    out[f"L1000_k1.0_{nm}"] = acc_for(clv.reindex((t - 1000) // 1000).to_numpy(float), 1.0, m_)
print(json.dumps({k: v for k, v in out.items() if "17:" in k})); (HERE.parent / "results/iter14_qu_pit.json").write_text(json.dumps(out, indent=1))
