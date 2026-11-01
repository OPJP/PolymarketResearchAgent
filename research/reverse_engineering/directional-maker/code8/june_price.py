"""Iteration 8 (A5 / X73): B3 at the true decision time. Limit price of each June cluster maker BUY order (BTC 5m) at its
signing ms S against a Binance digital fair value evaluated at S - lag (spot and futures; strike = the same venue's
mean over [start-60, start), the Binance-consistent TWAP strike; sigma = 1.4 x the 300-s 1-s realised vol; tau = end -
t), lag = -1,000..+3,000 ms (positive = reference before signing). Reports corr(q, fair) and MAD(q - fair - median) by
lag, by venue; the best lag is the engine's effective reference delay at the decision.
    python code8/june_price.py 2026-06-12
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
J = ROOT / ".cache/re/directional-maker/june"
OUT = ROOT / "research/reverse_engineering/directional-maker/results"
LAGS = [-1000, -500, -250, 0, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000]


def grid(kind, d):
    s = pd.read_parquet(J / f"{kind}50_{d}.parquet")
    b0, b1 = int(s.b50.min()), int(s.b50.max())
    px = np.full(b1 - b0 + 1, np.nan)
    px[s.b50.to_numpy() - b0] = s.px.to_numpy()
    return b0, pd.Series(px).ffill().bfill().to_numpy()


def main(d):
    from polyrea.analysis.updown import windows_from_markets
    from polyrea.workflows.updown_study import fetch_windows, window_slugs
    a = int(pd.Timestamp(d, tz="UTC").timestamp())
    b = a + 86400
    raw = fetch_windows(window_slugs("btc", "5m", a, b))
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
    o["st"] = o.token.map(lambda t: tok[t][0])
    o["en"] = o.token.map(lambda t: tok[t][1])
    o["up"] = o.token.map(lambda t: tok[t][2])
    o["q"] = o.mk.astype(float) / o.tk.astype(float)
    o = o[(o.q > 0.02) & (o.q < 0.98)]
    res = {"orders": int(len(o)), "windows": int(o.st.nunique())}
    for kind in ("spot", "fut"):
        b0, px = grid(kind, d)
        lp = np.log(px)
        sec_px = px[::20]  # 1-s grid (every 20th 50-ms bin)
        r1 = np.r_[0.0, np.diff(np.log(sec_px))]
        def at(ms):
            return px[np.clip(ms // 50 - b0, 0, len(px) - 1)]
        Kb = {}
        for st in o.st.unique():
            i0 = (st - 60) * 20 - b0 + 0
            i0 = max(int((st - 60) * 1000 // 50 - b0), 0)
            i1 = max(int(st * 1000 // 50 - b0), 1)
            Kb[st] = float(np.mean(px[i0:i1]))
        S = o.sign_ms.to_numpy(np.int64)
        isec = np.clip(S // 1000 - b0 // 20, 1, len(r1) - 1)
        sig = np.array([np.std(r1[max(i - 300, 0):i]) for i in isec]) * 1.4
        K = o.st.map(Kb).to_numpy(dtype=float)
        prof = {}
        for lag in LAGS:
            t = S - lag
            tau = np.maximum(o.en.to_numpy(dtype=float) - t / 1000, 1.0)
            fu = norm.cdf(np.log(at(t) / K) / (sig * np.sqrt(tau)))
            f = np.where(o.up.to_numpy(dtype=float) == 1, fu, 1 - fu)
            r = o.q.to_numpy() - f
            ok = np.isfinite(r)
            prof[lag] = {"corr": round(float(np.corrcoef(o.q.to_numpy()[ok], f[ok])[0, 1]), 4),
                         "median_q_minus_fair": round(float(np.median(r[ok])), 4),
                         "mad": round(float(np.median(np.abs(r[ok] - np.median(r[ok])))), 4)}
        best = max(prof, key=lambda L: prof[L]["corr"])
        res[kind] = {"by_lag_ms": prof, "best_lag_ms": int(best)}
    (OUT / f"iter8_june_price_{d}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: (v if not isinstance(v, dict) else {"best_lag_ms": v["best_lag_ms"],
                                                            "corr_by_lag": {L: v["by_lag_ms"][L]["corr"] for L in LAGS},
                                                            "mad_by_lag": {L: v["by_lag_ms"][L]["mad"] for L in LAGS}})
                      for k, v in res.items()}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
