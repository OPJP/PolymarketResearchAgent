"""iteration 18, T20 = E7 on the residual of law E2 (pre-registered in NOTES.md 13:37 UTC 11-01): do the posts that E2 gets
wrong still coincide across windows once the futures and publish events are absorbed? 11-01 07:00-09:15 and 09:15-12:00
(full depth), at-touch 500/1000 posts 0.10-0.90; misses vs hits of E2 (T3's frozen beta); residual_clustering with
delta 0.5 s and 2 s, period 900 s (5m + 15m), 1,000 draws. Reading (brief): synchrony only with p <= 0.01, ratio >= 1.5
and a miss ratio at least 0.3 above the hit ratio."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import event_law as el  # noqa: E402
import indicators as ind  # noqa: E402


def e2_labels(name, beta, need_posture=False):
    a, b, qf = el.BLOCKS[name]
    q = pd.read_parquet(el.C / qf)
    q = q[(q.s >= a * 1000) & (q.s < b * 1000) & (q.p >= 0.10) & (q.p <= 0.90) & q.dz.isin([500.0, 1000.0])].sort_values("s").reset_index(drop=True)
    E, M = el.fut_mid(a - 120, b + 60)
    sc, clb, Pb = el.publishes(a, b)
    Xb = el.design(E, M, sc)
    yb = np.array([clb[s] - clb[s - 1] for s in sc])
    okb = np.all(np.isfinite(Xb), axis=1)
    u = yb - np.where(okb, np.c_[np.ones(len(Xb)), np.nan_to_num(Xb)] @ beta, np.nan)
    o = np.argsort([Pb[s] for s in sc])
    Pm = np.array([Pb[s] for s in sc], np.int64)[o]
    um = u[o]
    t = q.s.to_numpy(np.int64)
    F = q.F.to_numpy(float)
    mp = q.mid_prev.to_numpy(float)
    post = np.where(np.isfinite(F) & np.isfinite(mp), (F > mp).astype(float), np.nan)
    dF = el.at(E, M, t - 50) - el.at(E, M, t - 500)
    law = np.where(np.abs(dF) >= 2.0, (dF > 0).astype(float), post)
    for k, tk in enumerate(t):
        j = np.searchsorted(Pm, tk, side="right") - 1
        while j >= 0 and Pm[j] > tk - 150:
            if np.isfinite(um[j]) and abs(um[j]) >= 1.0:
                law[k] = float(um[j] > 0)
                break
            j -= 1
    y = (q.sd == 1).to_numpy(float)
    ok = np.isfinite(law) & (np.isfinite(post) if need_posture else True)
    if need_posture:
        return t[ok], (law[ok] == y[ok]), (post[ok] == y[ok])
    return t[ok] / 1000.0, q.w.to_numpy(object)[ok], (law[ok] == y[ok])


def main():
    E0, M0 = el.fut_mid(el.FIT[0] - 120, el.FIT[1] + 60)
    secs, cl, P = el.publishes(*el.FIT)
    X = el.design(E0, M0, secs)
    y = np.array([cl[s] - cl[s - 1] for s in secs])
    ok = np.all(np.isfinite(X), axis=1)
    beta, *_ = np.linalg.lstsq(np.c_[np.ones(ok.sum()), X[ok]], y[ok], rcond=None)
    out = {}
    for name in ("freeze_1101_0700_0915", "confirm_1101_0915_1200"):
        ts, mk, hit = e2_labels(name, beta)
        rec = {"posts": int(len(ts)), "miss_share": round(float((~hit).mean()), 3)}
        for dl in (0.5, 2.0):
            rm = ind.residual_clustering(ts[~hit], mk[~hit], delta_s=dl, n_null=1000, period_s=900)
            rh = ind.residual_clustering(ts[hit], mk[hit], delta_s=dl, n_null=1000, period_s=900)
            rec[f"delta{dl}"] = {"miss": {"ratio": rm.get("ratio"), "p": rm.get("p"), "n": int((~hit).sum())},
                                 "hit": {"ratio": rh.get("ratio"), "p": rh.get("p"), "n": int(hit.sum())}}
            mr, hr = rm.get("ratio") or 0, rh.get("ratio") or 0
            rec[f"delta{dl}"]["synchrony"] = bool((rm.get("p") or 1) <= 0.01 and mr >= 1.5 and mr >= hr + 0.3)
        out[name] = rec
    (HERE.parent / "results" / "iter18_e7_e2.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
