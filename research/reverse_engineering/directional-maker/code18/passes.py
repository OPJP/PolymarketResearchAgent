"""iteration 18, T19 = X202 light (mechanics panel iter16 P-pass; pre-registered in NOTES.md 13:31 UTC 11-01): one engine
pass for all markets? Posts: every at-touch schedule add (62 / 250 / 500 / 1000) in the full-depth tables of 11-01
07:00-12:00 (BTC 5m current + next, BTC 15m current). A post is in a multi-window pass if another window has a post within
+-25 ms. Null: each window's post times shifted by a random +-1-5 s (50 draws). Reported: the multi-window share vs the
null; side agreement across windows inside passes (same Up/Down direction); the trigger of passes (a publish with
|u| >= $1 within 150 ms before, a futures move >= $2 over 0.5 s, neither) against single-window posts. Reading: share >= 2 x
null -> passes exist; side agreement >= 0.8 -> one input re-sides all markets in a pass."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import event_law as el  # noqa: E402

C = el.C
FILES = ["it14_qu_rebuilt_1793516400_1793524500.parquet", "it14_qu_rebuilt_1793524500_1793534400.parquet"]
A0, B0 = 1793516400, 1793534400


def multi(t, w, tol=25):
    o = np.argsort(t, kind="stable")
    ts, ws = t[o], w[o]
    flag = np.zeros(len(t), bool)
    j0 = 0
    for i in range(len(ts)):
        while ts[i] - ts[j0] > tol:
            j0 += 1
        j = j0
        while j < len(ts) and ts[j] - ts[i] <= tol:
            if ws[j] != ws[i]:
                flag[i] = True
                break
            j += 1
    out = np.zeros(len(t), bool)
    out[o] = flag
    return out


def main():
    q = pd.concat([pd.read_parquet(C / f) for f in FILES], ignore_index=True)
    q = q[(q.s >= A0 * 1000) & (q.s < B0 * 1000)].sort_values("s").reset_index(drop=True)
    t = q.s.to_numpy(np.int64)
    w = q.w.to_numpy(object)
    m = multi(t, w)
    rng = np.random.default_rng(0)
    nulls = []
    wins = np.unique(w)
    for _ in range(50):
        tt = t.copy()
        for x in wins:
            k = w == x
            tt[k] = t[k] + int(rng.choice([-1, 1]) * rng.integers(1000, 5000))
        nulls.append(multi(tt, w).mean())
    out = {"posts": int(len(q)), "windows": int(len(wins)), "multi_share": round(float(m.mean()), 4),
           "null_mean": round(float(np.mean(nulls)), 4), "null_p95": round(float(np.quantile(nulls, 0.95)), 4)}
    # side agreement across windows in a pass: for each multi post, the direction (Up post +1) of the nearest other-window post
    up = np.where(q.sd == 1, 1, -1)
    o = np.argsort(t, kind="stable")
    agree = []
    for i in np.flatnonzero(m):
        lo = np.searchsorted(t[o], t[i] - 25, side="left")
        hi = np.searchsorted(t[o], t[i] + 25, side="right")
        idx = [o[k] for k in range(lo, hi) if w[o[k]] != w[i]]
        if idx:
            agree.append(float(np.mean(up[idx] == up[i])))
    out["side_agreement_in_pass"] = round(float(np.mean(agree)), 4) if agree else None
    # triggers
    E, M = el.fut_mid(A0 - 120, B0 + 60)
    E0, M0 = el.fut_mid(el.FIT[0] - 120, el.FIT[1] + 60)
    secs, cl, P = el.publishes(*el.FIT)
    X = el.design(E0, M0, secs)
    y = np.array([cl[s] - cl[s - 1] for s in secs])
    ok = np.all(np.isfinite(X), axis=1)
    beta, *_ = np.linalg.lstsq(np.c_[np.ones(ok.sum()), X[ok]], y[ok], rcond=None)
    sc, clb, Pb = el.publishes(A0, B0)
    Xb = el.design(E, M, sc)
    yb = np.array([clb[s] - clb[s - 1] for s in sc])
    okb = np.all(np.isfinite(Xb), axis=1)
    u = yb - np.where(okb, np.c_[np.ones(len(Xb)), np.nan_to_num(Xb)] @ beta, np.nan)
    order = np.argsort([Pb[s] for s in sc])
    Pm = np.array([Pb[s] for s in sc], np.int64)[order]
    um = u[order]
    trig = np.full(len(t), "none", dtype=object)
    dF = el.at(E, M, t - 50) - el.at(E, M, t - 500)
    for k, tk in enumerate(t):
        j = np.searchsorted(Pm, tk, side="right") - 1
        while j >= 0 and Pm[j] > tk - 150:
            if np.isfinite(um[j]) and abs(um[j]) >= 1.0:
                trig[k] = "publish_u"
                break
            j -= 1
        if trig[k] == "none" and np.isfinite(dF[k]) and abs(dF[k]) >= 2.0:
            trig[k] = "futures_move"
    out["trigger_share"] = {lab: {x: round(float((trig[mm] == x).mean()), 3) for x in ("publish_u", "futures_move", "none")}
                            for lab, mm in (("multi_window", m), ("single_window", ~m))}
    out["reading"] = {"passes_exist": bool(out["multi_share"] >= 2 * out["null_mean"]),
                      "one_input_resides_all": bool(out["side_agreement_in_pass"] is not None and out["side_agreement_in_pass"] >= 0.8)}
    (HERE.parent / "results" / "iter18_passes.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
