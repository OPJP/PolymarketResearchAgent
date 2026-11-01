"""Iteration 14: per filled order (it14_fills_lq.parquet from code14/lagged_quote.py, 10-31 14-18), the posture at the
post and at the match for Chainlink stamp lag L and sigma multiplier k (futures-mid sigma300), fit 14-16 / test 16-18."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE))
from lagged_quote import fut_mid, sec_sigma, cl_source
a, b = 1793455200, 1793469600
o = pd.read_parquet(ROOT / ".cache/re/directional-maker/it14_fills_lq.parquet")
E, M = fut_mid(a, b); sig = sec_sigma(E, M, 300)
clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=False)
from polyrea.workflows.updown_study import fetch_windows
raw = fetch_windows(sorted(set(o.w))); K = {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
st = o.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy(); en = st + np.where(o.w.str.contains("-15m-").to_numpy(), 900, 300)
kk = o.w.map(K).to_numpy(float); y = o.y.to_numpy(float)
out = {}
for when, tcol, mcol in (("post", "post_ms", "mid_post"), ("fill", "fill_ms", "mid_fill")):
    t = o[tcol].to_numpy(np.int64); mid = o[mcol].to_numpy(float); s0 = sig.reindex(t // 1000).to_numpy(float); tau = np.maximum(en - t / 1000, 1.0)
    for L in (500, 750, 1000, 1250, 1500):
        for k in (0.7, 1.0, 1.4):
            cl = clv.reindex((t - L) // 1000).to_numpy(float)
            F = norm.cdf((cl - kk) / (k * s0 * np.sqrt(tau))); P = (F > mid).astype(float); ok = np.isfinite(F) & np.isfinite(mid)
            r = {}
            for h in ("fit", "test"):
                for c in ("i", "ii", "all"):
                    m_ = ok & (o.half == h).to_numpy() & ((o.cls == c).to_numpy() if c != "all" else True)
                    r[f"{h}_{c}"] = round(float((P[m_] == y[m_]).mean()), 3)
            out[f"{when}_L{L}_k{k}"] = r
for k_, v in out.items():
    if k_.endswith(("L1250_k1.4", "L1000_k1.0", "L750_k1.0", "L1000_k0.7")):
        print(k_, v)
(HERE.parent / "results/iter14_fill_lag.json").write_text(json.dumps(out, indent=1))
