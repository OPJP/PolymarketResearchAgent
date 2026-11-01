"""Iteration 12, X116 (information I11-3) / X119 (mechanics P1) step 1 on the only recorded development block: the
engine's volatility multiplier read off its own quote, not its fills. Development live block 10-31 14:06-16:30 UTC (own raw
recorder; exact-500 adds, it6/ev_*), BTC 5m and 15m current windows. Each second t with cluster-class top rungs on both
sides of the Up book (highest exact-500 bid add and lowest exact-500 ask add in the last 1.5 s, as code8/m1_invert.py):
ladder center F = (q_up + a_up) / 2; where |F - 0.5| > 0.05 and tau > 60 s, k(t) = z / Phi^-1(F) with z = ln(CL / K) /
(v300 sqrt(tau)), CL = Chainlink stamped floor((t - 1.432 s)), K = RTDS TWAP-60 at the window start, v300 = 300-s sd of
1-s futures log returns (the posture's unit; the frozen posture uses k = 1.4). Median per minute and overall, with a
window bootstrap; compared with the fill-level best k on the same block (iter12_live_k_grid: 1.4).
    python code12/quote_k.py 1793455600 1793464202
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(HERE.parent / "code6"))
sys.path.insert(0, str(HERE.parent / "code8"))
from pres_live import load_ref  # noqa: E402
from m1_invert import top_rungs  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"


def main(a, b):
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet", columns=["s", "w", "side", "p", "d"])
    ev = ev[ev.d == 500.0]
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    groups = {w: g.sort_values("s") for w, g in ev.groupby("w")}
    rows = []
    for t in range((a // 300 + 1) * 300 + 5, b - 1):
        for fam, L in (("5m", 300), ("15m", 900)):
            st = (t // L) * L
            w = f"btc-updown-{fam}-{st}"
            tau = st + L - t
            if tau < 60 or w not in groups:
                continue
            K = tw.get(st)
            if K is None:
                continue
            T = t * 1000
            rr = top_rungs(groups[w], T)
            if rr is None:
                continue
            qu, au = rr
            if au <= qu:
                continue
            F = (qu + au) / 2
            if abs(F - 0.5) <= 0.05 or not (0.03 < F < 0.97):
                continue
            jj = np.searchsorted(sec, t)
            sig = np.std(r1[max(jj - 300, 0):jj])
            k_ = np.searchsorted(cls, (T - 1432) // 1000, side="right") - 1
            if not sig > 0 or k_ < 0:
                continue
            z = np.log(clv[k_] / K) / (sig * np.sqrt(tau))
            kq = z / norm.ppf(F)
            rows.append((fam, st, t, F, z, kq, (au - qu) / 2))
    D = pd.DataFrame(rows, columns=["fam", "st", "t", "F", "z", "k", "h"])
    out = {"block": [a, b]}
    for fam, g in D.groupby("fam"):
        ok = g[(g.k > 0) & np.isfinite(g.k)]
        neg = float((g.k <= 0).mean())
        per_min = ok.groupby(ok.t // 60).k.median()
        rng = np.random.default_rng(12)
        sts = ok.st.unique()
        bs = []
        for _ in range(1000):
            pick = rng.choice(sts, len(sts), replace=True)
            bs.append(float(np.median(np.concatenate([ok.k[ok.st == s].to_numpy() for s in pick]))))
        out[fam] = {"seconds": int(len(g)), "windows": int(g.st.nunique()), "share_k_nonpositive (F and Chainlink disagree on the side)": round(neg, 4),
                    "k_median": round(float(ok.k.median()), 3), "k_iqr": [round(float(ok.k.quantile(.25)), 3), round(float(ok.k.quantile(.75)), 3)],
                    "k_median_window_boot95": [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                    "per_minute_median_q": per_min.quantile([.1, .25, .5, .75, .9]).round(3).to_dict(),
                    "per_window_median": ok.groupby("st").k.median().round(3).to_dict(),
                    "half_spread_median": round(float(g.h.median()), 4)}
    (HERE.parent / "results" / f"iter12_quote_k_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: ({kk: vv for kk, vv in v.items() if kk != "per_window_median"} if isinstance(v, dict) else v) for k, v in out.items()}, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
