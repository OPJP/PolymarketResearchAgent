"""iteration 17, T8 = X198 part 1 (pre-registered in NOTES.md 11:15 UTC): nowcast basis lag L in {0, 0.5, 0.75} s.
S_L(t) = CL_i + F(t - 50 ms) - F(ts_i - L) on the safe clock (report stamped <= t - 1,432 ms), k 1.0, pure non-extreme 500
posts; L chosen on 10-31 14-18, scored on 11-01 07:00-09:15 per hour; plus each L's error predicting the next report."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code14"))
from lagged_quote import fut_mid, at, sec_sigma, cl_source  # noqa: E402

BLOCKS = [(1793455200, 1793469600), (1793516400, 1793524500)]
LS = (0.0, 0.5, 0.75)


def load(a, b):
    A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet")
    A = A[A.mid_prev.notna()].reset_index(drop=True)
    bid = np.where(A.sd == 1, A.p, 1 - A.p)
    A = A[(A.dz == 500) & (bid > 0.03) & (bid < 0.97)].reset_index(drop=True)
    E, M = fut_mid(a - 900, b)
    sig = sec_sigma(E, M, 300)
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows(sorted(set(A.w)))
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=False)
    t = A.s.to_numpy(np.int64)
    st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
    en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300)
    D = dict(t=t, tau=np.maximum(en - t / 1000, 1.0), s0=sig.reindex(t // 1000).to_numpy(float),
             kk=A.w.map(K).to_numpy(float), mid=A.mid_prev.to_numpy(float), y=(A.sd == 1).to_numpy(float))
    ss = (t - 1432) // 1000
    cl = clv.reindex(ss).to_numpy(float)
    f50 = at(E, M, t - 50)
    D["S"] = {L: cl + f50 - at(E, M, (ss * 1000 - int(L * 1000))) for L in LS}
    D["mv"] = np.abs(f50 - at(E, M, t - 500)) >= 2.0
    # information only: each L's error predicting the next report's change (report-to-report)
    sec = np.array(sorted(clv.dropna().index.astype(int)))
    v = clv.reindex(sec).to_numpy(float)
    chg = np.r_[False, np.diff(v) != 0]
    ps = sec[chg]
    pv = v[chg]
    err = {}
    if len(ps) > 3:
        prev_s, prev_v, nxt_s, nxt_v = ps[:-1], pv[:-1], ps[1:], pv[1:]
        for L in LS:
            pred = prev_v + at(E, M, nxt_s * 1000) - at(E, M, prev_s * 1000 - int(L * 1000))
            e = np.abs(pred - nxt_v)
            err[str(L)] = round(float(np.nanmedian(e)), 3)
        err["no_move"] = round(float(np.nanmedian(np.abs(prev_v - nxt_v))), 3)
    D["err"] = err
    return D


def acc(D, L, m):
    F = norm.cdf((D["S"][L] - D["kk"]) / (D["s0"] * np.sqrt(D["tau"])))
    P = np.where(np.isfinite(F) & np.isfinite(D["mid"]), (F > D["mid"]).astype(float), np.nan)
    ok = m & np.isfinite(P)
    return [round(float((P[ok] == D["y"][ok]).mean()), 4) if ok.sum() else None, int(ok.sum())]


out = {}
D0 = load(*BLOCKS[0])
all0 = np.ones(len(D0["y"]), bool)
cal = {str(L): acc(D0, L, all0) for L in LS}
Lf = max(LS, key=lambda L: cal[str(L)][0])
out["calibration_1031"] = cal
out["L_frozen"] = Lf
out["next_report_abs_err_1031"] = D0["err"]
D1 = load(*BLOCKS[1])
hr = (D1["t"] // 3600000) * 3600
res = {}
for h in list(np.unique(hr)) + ["all"]:
    m = (hr == h) if h != "all" else np.ones(len(D1["y"]), bool)
    res[str(h)] = {f"L{L}": acc(D1, L, m) for L in LS}
    res[str(h)].update({f"L{L}_still": acc(D1, L, m & ~D1["mv"]) for L in LS})
out["score_1101"] = res
out["next_report_abs_err_1101"] = D1["err"]
out["reading_met"] = bool(res["all"][f"L{Lf}"][0] - res["all"]["L0.0"][0] >= 0.02) if Lf != 0.0 else False
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "iter17_nowcast_lag.json").write_text(json.dumps(out, indent=1))
