"""iteration 18, T11 (exploratory, on blocks already used by T3: 11-01 07:00-09:15 and 09:15-12:00, full-depth posts): what
sets the side of the at-touch 500/1000 posts that law E2 leaves to the posture (no publish innovation |u| >= $1 within
150 ms, no futures move >= $2 over [t - 500, t - 50] ms)? Candidate rules scored on those posts only; the best is
pre-registered as the third branch of law E3 for the next development blocks (11-01 18-24, 11-02 00-06, 11-02 12-18)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import event_law as el  # noqa: E402

C = el.C


def main():
    E0, M0 = el.fut_mid(el.FIT[0] - 120, el.FIT[1] + 60)
    secs, cl, P = el.publishes(*el.FIT)
    X = el.design(E0, M0, secs)
    y = np.array([cl[s] - cl[s - 1] for s in secs])
    ok = np.all(np.isfinite(X), axis=1)
    beta, *_ = np.linalg.lstsq(np.c_[np.ones(ok.sum()), X[ok]], y[ok], rcond=None)
    out = {}
    for name in ("freeze_1101_0700_0915", "confirm_1101_0915_1200"):
        a, b, qf = el.BLOCKS[name]
        q = pd.read_parquet(C / qf)
        q = q[(q.s >= a * 1000) & (q.s < b * 1000) & (q.p >= 0.10) & (q.p <= 0.90) & q.dz.isin([500.0, 1000.0])].copy()
        q = q.sort_values("s").reset_index(drop=True)
        E, M = el.fut_mid(a - 120, b + 60)
        sc, clb, Pb = el.publishes(a, b)
        Xb = el.design(E, M, sc)
        yb = np.array([clb[s] - clb[s - 1] for s in sc])
        okb = np.all(np.isfinite(Xb), axis=1)
        u = yb - np.where(okb, np.c_[np.ones(len(Xb)), np.nan_to_num(Xb)] @ beta, np.nan)
        order = np.argsort([Pb[s] for s in sc])
        Pm = np.array([Pb[s] for s in sc], np.int64)[order]
        um = u[order]
        dcl = yb[order]
        t = q.s.to_numpy(np.int64)
        yv = (q.sd == 1).to_numpy(float)
        F = q.F.to_numpy(float)
        mp = q.mid_prev.to_numpy(float)
        post = np.where(np.isfinite(F) & np.isfinite(mp), (F > mp).astype(float), np.nan)
        dF500 = el.at(E, M, t - 50) - el.at(E, M, t - 500)
        ev = np.abs(dF500) >= 2.0
        for k, tk in enumerate(t):
            j = np.searchsorted(Pm, tk, side="right") - 1
            while j >= 0 and Pm[j] > tk - 150:
                if np.isfinite(um[j]) and abs(um[j]) >= 1.0:
                    ev[k] = True
                    break
                j -= 1
        m = ~ev & np.isfinite(post)
        cand = {"posture": post, "cheaper": (mp < 0.5).astype(float), "opposite_last_hit": 1 - q.hit.to_numpy(float),
                "last_hit": q.hit.to_numpy(float)}
        for W, thr in ((1000, 1.0), (2000, 1.0), (5000, 2.0), (500, 0.5)):
            d = el.at(E, M, t - 50) - el.at(E, M, t - W)
            cand[f"fut_move_{W}ms_ge{thr}"] = np.where(np.abs(d) >= thr, (d > 0).astype(float), np.nan)
            cand[f"fut_move_{W}ms_ge{thr}_else_posture"] = np.where(np.abs(d) >= thr, (d > 0).astype(float), post)
        # latest publish within 1 s: sign of u (any size >= 0.25) and of the raw report change
        lu = np.full(len(t), np.nan)
        lc = np.full(len(t), np.nan)
        since = np.full(len(t), np.nan)
        for k, tk in enumerate(t):
            j = np.searchsorted(Pm, tk, side="right") - 1
            if j >= 0 and tk - Pm[j] <= 1000:
                if np.isfinite(um[j]) and abs(um[j]) >= 0.25:
                    lu[k] = float(um[j] > 0)
                if dcl[j] != 0:
                    lc[k] = float(dcl[j] > 0)
            if j >= 0:
                since[k] = tk - Pm[j]
        cand["last_publish_u_within_1s"] = lu
        cand["last_publish_change_within_1s"] = lc
        rec = {"posts": int(len(q)), "non_event": int(m.sum())}
        for nm, pr in cand.items():
            mm = m & np.isfinite(pr)
            rec[nm] = [round(float((pr[mm] == yv[mm]).mean()), 4) if mm.any() else None, int(mm.sum())]
        rec["since_last_publish_ms_median"] = float(np.nanmedian(since[m]))
        out[name] = rec
    (HERE.parent / "results" / "iter18_nonevent.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
