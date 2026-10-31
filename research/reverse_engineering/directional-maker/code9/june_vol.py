"""Iteration 9 (mechanics M1 step 4 = X79): which sigma makes a Binance digital fair closest to the June engine's limit
prices at their true signing ms? June cluster maker BUY orders in BTC 5m (code8/june_fetch.py), reference at the signing
ms (lag 0, the best lag in iteration 8), strike = the venue's mean over [start-60, start), sigma from the venue's 1-s log
returns: realised v_L (L 120/300/900/1800/3600), EWMA half-life 300/900/1800, scale k 0.8-2.0. Metric: corr(q, fair)
and MAD(q - fair - median); also within-window demeaned corr (removes the per-window level).
    python code9/june_vol.py 2026-06-12 fut
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import lfilter
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
J = ROOT / ".cache/re/directional-maker/june"
OUT = HERE.parent / "results"


def main(d, kind):
    from polyrea.workflows.updown_study import fetch_windows, window_slugs
    a = int(pd.Timestamp(d, tz="UTC").timestamp())
    raw = fetch_windows(window_slugs("btc", "5m", a, a + 86400))
    tok = {}
    for m in raw.values():
        try:
            st = int(str(m.get("slug")).rsplit("-", 1)[1])
            ids = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
            outs = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        for tid, oc in zip(ids, outs):
            tok[str(tid)[-12:]] = (st, st + 300, 1 if str(oc).lower() == "up" else 0)
    o = pd.read_parquet(J / f"orders_{d}.parquet")
    o = o[(o.cl == True) & (o.role == "maker") & (o.sign_ms > 0) & (o.oside == 0) & o.slug.str.startswith("btc-updown-5m", na=False)]
    o = o[o.token.isin(tok.keys())].copy()
    o["st"] = o.token.map(lambda t: tok[t][0]); o["en"] = o.token.map(lambda t: tok[t][1]); o["up"] = o.token.map(lambda t: tok[t][2])
    o["q"] = o.mk.astype(float) / o.tk.astype(float)
    o = o[(o.q > 0.02) & (o.q < 0.98)]
    s = pd.read_parquet(J / f"{kind}50_{d}.parquet")
    b0, b1 = int(s.b50.min()), int(s.b50.max())
    px = np.full(b1 - b0 + 1, np.nan); px[s.b50.to_numpy() - b0] = s.px.to_numpy()
    px = pd.Series(px).ffill().bfill().to_numpy()
    sec_px = px[::20]
    r = np.r_[0.0, np.diff(np.log(sec_px))]
    r2 = r * r
    cs = np.r_[0.0, np.cumsum(r2)]
    S = o.sign_ms.to_numpy(np.int64)
    isec = np.clip((S // 50 - b0) // 20, 1, len(r) - 1)
    def rv(L):
        lo = np.maximum(isec - L, 0)
        return np.sqrt((cs[isec] - cs[lo]) / np.maximum(isec - lo, 1))
    cand = {f"v{L}": rv(L) for L in (120, 300, 900, 1800, 3600)}
    for hl in (300, 900, 1800):
        lam = 0.5 ** (1 / hl)
        e, _ = lfilter([1 - lam], [1, -lam], r2, zi=[lam * r2[:3600].mean()])
        cand[f"e{hl}"] = np.sqrt(e[isec - 1])
    Kb = {st: float(np.mean(px[max(int((st - 60) * 20 - b0), 0):max(int(st * 20 - b0), 1)])) for st in o.st.unique()}
    K = o.st.map(Kb).to_numpy(float)
    spot = px[np.clip(S // 50 - b0, 0, len(px) - 1)]
    tau = np.maximum(o.en.to_numpy(float) - S / 1000, 1.0)
    q = o.q.to_numpy()
    first_hour = isec < 3600
    win = o.st.to_numpy()
    res = {"orders": int(len(o)), "orders_after_first_hour": int((~first_hour).sum())}
    rows = []
    keep = ~first_hour
    for nm, sg in cand.items():
        for k in (0.8, 1.0, 1.2, 1.4, 1.7, 2.0):
            fu = norm.cdf(np.log(spot / K) / (k * sg * np.sqrt(tau)))
            f = np.where(o.up.to_numpy() == 1, fu, 1 - fu)
            rr = q - f
            ok = keep & np.isfinite(rr)
            dq = q[ok] - pd.Series(q[ok]).groupby(win[ok]).transform("mean").to_numpy()
            df_ = f[ok] - pd.Series(f[ok]).groupby(win[ok]).transform("mean").to_numpy()
            rows.append(dict(cand=nm, k=k, corr=float(np.corrcoef(q[ok], f[ok])[0, 1]), mad=float(np.median(np.abs(rr[ok] - np.median(rr[ok])))),
                             corr_within=float(np.corrcoef(dq, df_)[0, 1])))
    R = pd.DataFrame(rows)
    best = R.sort_values("mad").groupby("cand").head(1).sort_values("mad")
    print(d, kind, res)
    print(best.round(4).to_string(index=False))
    res["best_per_cand"] = best.to_dict("records")
    res["ref_v300_k1.4"] = R[(R.cand == "v300") & (R.k == 1.4)].iloc[0].to_dict()
    (OUT / f"iter9_june_vol_{d}_{kind}.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
