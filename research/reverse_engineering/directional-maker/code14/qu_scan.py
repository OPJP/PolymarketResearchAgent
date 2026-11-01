"""directional-maker iteration 14 (X146 follow-up): where does the uncensored quote's side depart from the posture?
Quote unit = the rebuilt at-touch schedule-size posts of 10-31 14-18 (code14/qu_oos.py table). Posture parameters
scanned on 14-16 (fit) and scored on 16-18 (test): Chainlink stamp lag L, sigma multiplier k (futures-mid sigma300);
accuracy by |F - mid| for the frozen form (L 1250 ms, k 1.4), by family and by time left.
    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/qu_scan.py 1793455200 1793469600
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from lagged_quote import fut_mid, sec_sigma, cl_source  # noqa: E402


def main(a, b):
    A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet")
    A = A[A.mid_prev.notna()].copy()
    E, M = fut_mid(a, b)
    sig = sec_sigma(E, M, 300)
    clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=False)
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows(sorted(set(A.w)))
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    t = A.s.to_numpy(np.int64)
    st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
    en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300)
    kk = A.w.map(K).to_numpy(float)
    tau = np.maximum(en - t / 1000, 1.0)
    s0 = sig.reindex(t // 1000).to_numpy(float)
    y = (A.sd == 1).to_numpy(float)
    half = np.where(t < (a + (b - a) // 2) * 1000, "fit", "test")
    big = A.dz.isin([500.0, 1000.0]).to_numpy()
    mid = A.mid_prev.to_numpy(float)

    def Fof(L, k):
        cl = clv.reindex((t - L) // 1000).to_numpy(float)
        return norm.cdf((cl - kk) / (k * s0 * np.sqrt(tau)))

    grid = {}
    for L in (250, 500, 750, 1000, 1250, 1500, 2000, 3000):
        for k in (0.7, 1.0, 1.4, 2.0):
            F = Fof(L, k)
            P = (F > mid).astype(float); ok = np.isfinite(F) & big
            grid[f"L{L}_k{k}"] = {h: round(float((P[ok & (half == h)] == y[ok & (half == h)]).mean()), 4) for h in ("fit", "test")}
    best = max(grid, key=lambda g: grid[g]["fit"])
    F = Fof(1250, 1.4); P = (F > mid).astype(float); ok = np.isfinite(F) & big
    e = np.abs(F - mid)
    by_edge = {}
    for lo, hi in ((0, 0.01), (0.01, 0.02), (0.02, 0.05), (0.05, 0.1), (0.1, 1.01)):
        m_ = ok & (e >= lo) & (e < hi)
        by_edge[f"{lo}-{hi}"] = {"n": int(m_.sum()), "share": round(float(m_.sum() / ok.sum()), 3),
                                 "acc": round(float((P[m_] == y[m_]).mean()), 3) if m_.sum() else None}
    left = en - t / 1000
    by_left = {}
    for lo, hi in ((0, 60), (60, 120), (120, 300), (300, 600), (600, 900)):
        m_ = ok & (left >= lo) & (left < hi)
        by_left[f"{lo}-{hi}"] = {"n": int(m_.sum()), "acc": round(float((P[m_] == y[m_]).mean()), 3) if m_.sum() else None}
    fam = {f: round(float((P[ok & m_] == y[ok & m_]).mean()), 3) for f, m_ in
           (("5m", A.w.str.contains("-5m-").to_numpy()), ("15m", A.w.str.contains("-15m-").to_numpy()))}
    out = {"n_500": int(ok.sum()), "grid": grid, "best_on_fit": [best, grid[best]], "frozen_L1250_k1.4": grid["L1250_k1.4"],
           "by_abs_edge": by_edge, "by_time_left_s": by_left, "by_family": fam}
    (HERE.parent / "results" / f"iter14_qu_scan_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "grid"}, indent=1))
    print({g: v for g, v in grid.items() if g.endswith("k1.4") or g.startswith("L1250")})


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
