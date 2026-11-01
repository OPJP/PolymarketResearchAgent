"""iteration 15, X172 (mechanics P5, crude form): mo-money's class-(ii) fills re-scored with the Chainlink posture taken
L ms before the fill (L = each wallet's own cancel latency candidate: 0, 73, 118, 312, 500, 1000 ms), on the filled
orders of 10-31 14-18 (it14_fills_lq: class i = posted at/above the touch < ~1 s before the fill, ii = resting rung).
Crude: the market side of the posture uses the mid just before the fill (mid_fill) for every L; the reference is the
latest report published before fill - L (stamp lag 1,432 ms, point-in-time safe), k 1.0 x futures sigma300."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE.parent / "code14"))
from lagged_quote import fut_mid, sec_sigma, cl_source
a, b = 1793455200, 1793469600
o = pd.read_parquet(ROOT / ".cache/re/directional-maker/it14_fills_lq.parquet")
E, M = fut_mid(a - 600, b); sig = sec_sigma(E, M, 300)
clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=False)
from polyrea.workflows.updown_study import fetch_windows
raw = fetch_windows(sorted(set(o.w))); K = {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
NAMES = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
o["wal"] = o.maker.str.lower().map(NAMES)
st = o.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy(); en = st + np.where(o.w.str.contains("-15m-").to_numpy(), 900, 300)
kk = o.w.map(K).to_numpy(float); y = o.y.to_numpy(float); mid = o.mid_fill.to_numpy(float)
out = {}
for L in (0, 73, 118, 312, 500, 1000, 2000):
    t = o.fill_ms.to_numpy(np.int64) - L
    tau = np.maximum(en - t / 1000, 1.0); s0 = sig.reindex(t // 1000).to_numpy(float)
    cl = clv.reindex((t - 1432) // 1000).to_numpy(float)
    F = norm.cdf((cl - kk) / (s0 * np.sqrt(tau))); P = (F > mid).astype(float); ok = np.isfinite(F) & np.isfinite(mid)
    r = {}
    for w_ in ("bosona", "almach", "momoney"):
        for c in ("i", "ii"):
            m_ = ok & (o.wal == w_).to_numpy() & (o.cls == c).to_numpy()
            r[f"{w_}_{c}"] = [round(float((P[m_] == y[m_]).mean()), 3), int(m_.sum())]
    out[f"L{L}"] = r
for k, v in out.items(): print(k, v)
(HERE.parent / "results/iter15_cancel_lag.json").write_text(json.dumps(out, indent=1))
