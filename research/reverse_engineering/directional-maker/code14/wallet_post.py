"""Iteration 14: per-wallet post-time posture of the filled orders (10-31 14-18) under the quote form (L 1.0 s, k 1.0)
and the R8 form (L 1.25 s, k 1.4), by class (i quote move / ii resting rung)."""
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
NAMES = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
o["wal"] = o.maker.str.lower().map(NAMES)
st = o.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy(); en = st + np.where(o.w.str.contains("-15m-").to_numpy(), 900, 300)
t = o.post_ms.to_numpy(np.int64); tau = np.maximum(en - t / 1000, 1.0); s0 = sig.reindex(t // 1000).to_numpy(float)
kk = o.w.map(K).to_numpy(float); mid = o.mid_post.to_numpy(float); y = o.y.to_numpy(float)
out = {}
for nm, L, k in (("quote_form", 1000, 1.0), ("r8_form", 1250, 1.4)):
    cl = clv.reindex((t - L) // 1000).to_numpy(float)
    F = norm.cdf((cl - kk) / (k * s0 * np.sqrt(tau))); P = (F > mid).astype(float); ok = np.isfinite(F) & np.isfinite(mid)
    r = {}
    for w_ in ("bosona", "almach", "momoney"):
        for c in ("i", "ii", "all"):
            m_ = ok & (o.wal == w_).to_numpy() & ((o.cls == c).to_numpy() if c != "all" else True)
            r[f"{w_}_{c}"] = [round(float((P[m_] == y[m_]).mean()), 3), int(m_.sum())]
    out[nm] = r
print(json.dumps(out)); (HERE.parent / "results/iter14_wallet_post.json").write_text(json.dumps(out, indent=1))
