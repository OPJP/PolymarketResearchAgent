"""iteration 16, T3 = X179 (information panel I15-3): the latency-corrected Chainlink nowcast on the pure non-extreme
500 posts at the touch (rebuilt quote tables, code14/qu_oos.py).
S_now(t) = CL_i + F(t - 50 ms) - F(ts_i): CL_i the report in force on the safe clock (stamped <= t - 1,432 ms; cl_source)
or on the exact publish clock (dy_rtds P, from 10-31 17:29), ts_i its value stamp, F the Binance USD-M bookTicker mid
(dm_bnf, Binance event ms). Posture = 1[Phi((S - K) / (k sigma300_fut sqrt(tau))) > Up mid just before the post].
k frozen on 10-31 14-18 (safe clock) from {1.0, 1.4}; scored per hour on 11-01. Also: the futures-move rule (the
outcome that rose over [t - 500, t - 50] ms when |dF| >= $2) and its combination with the nowcast.
    python nowcast.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code14"))
from lagged_quote import fut_mid, at, sec_sigma, cl_source, live  # noqa: E402

BLOCKS = [(1793455200, 1793469600), (1793516400, 1793524500)]


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
    pub = []
    for r in live.iter_live("dy_rtds", a - 900, b):
        if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
            pub.append((int(r["P"]), int(r["ts"]), float(r["v"])))
    Pb = pd.DataFrame(pub, columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts").sort_values("P")
    clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=False)
    t = A.s.to_numpy(np.int64)
    st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
    en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300)
    tau = np.maximum(en - t / 1000, 1.0)
    s0 = sig.reindex(t // 1000).to_numpy(float)
    kk = A.w.map(K).to_numpy(float)
    mid = A.mid_prev.to_numpy(float)
    y = (A.sd == 1).to_numpy(float)
    ss = (t - 1432) // 1000
    cl_safe = clv.reindex(ss).to_numpy(float)
    f50 = at(E, M, t - 50)
    now_safe = cl_safe + f50 - at(E, M, ss * 1000)
    pm, pv, pts = Pb.P.to_numpy(np.int64), Pb.v.to_numpy(float), Pb.ts.to_numpy(np.int64)
    i = np.searchsorted(pm, t, side="right") - 1
    ii = np.clip(i, 0, None)
    has = (i >= 0) & (len(pm) > 0)
    cl_ex = np.where(has, pv[ii] if len(pv) else np.nan, np.nan)
    now_ex = np.where(has, cl_ex + f50 - at(E, M, pts[ii] if len(pts) else t), np.nan)
    dF = f50 - at(E, M, t - 500)
    return dict(A=A, t=t, tau=tau, s0=s0, kk=kk, mid=mid, y=y, cl_safe=cl_safe, now_safe=now_safe, cl_ex=cl_ex,
                now_ex=now_ex, dF=dF)


def post(S, D, k):
    F = norm.cdf((S - D["kk"]) / (k * D["s0"] * np.sqrt(D["tau"])))
    return np.where(np.isfinite(F) & np.isfinite(D["mid"]), (F > D["mid"]).astype(float), np.nan)


def acc(P, y, m):
    ok = m & np.isfinite(P)
    return [round(float((P[ok] == y[ok]).mean()), 3) if ok.sum() else None, int(ok.sum())]


out = {}
D0 = load(*BLOCKS[0])
m0 = np.ones(len(D0["y"]), bool)
cal = {}
for k in (1.0, 1.4):
    cal[f"report_safe_k{k}"] = acc(post(D0["cl_safe"], D0, k), D0["y"], m0)
    cal[f"nowcast_safe_k{k}"] = acc(post(D0["now_safe"], D0, k), D0["y"], m0)
kf = 1.0 if cal["nowcast_safe_k1.0"][0] >= cal["nowcast_safe_k1.4"][0] else 1.4
out["calibration_1031_14_18_safe"] = cal
out["k_frozen"] = kf
for (a, b), D in ((BLOCKS[0], D0), (BLOCKS[1], None)):
    if D is None:
        D = load(a, b)
    y = D["y"]
    hr = (D["t"] // 3600000) * 3600
    mv = np.abs(D["dF"]) >= 2.0
    rose = np.where(mv, (D["dF"] > 0).astype(float), np.nan)
    blk = {}
    for h in list(np.unique(hr)) + ["all"]:
        m = (hr == h) if h != "all" else np.ones(len(y), bool)
        row = {"n": int(m.sum())}
        for k in (1.0, 1.4, 2.0):
            row[f"report_safe_k{k}"] = acc(post(D["cl_safe"], D, k), y, m)
            row[f"nowcast_safe_k{k}"] = acc(post(D["now_safe"], D, k), y, m)
            row[f"report_exact_k{k}"] = acc(post(D["cl_ex"], D, k), y, m)
            row[f"nowcast_exact_k{k}"] = acc(post(D["now_ex"], D, k), y, m)
        row["cheaper"] = acc((D["mid"] < 0.5).astype(float), y, m)
        row["fut_rose_on_moving"] = acc(rose, y, m)
        row["moving_share"] = round(float(mv[m].mean()), 3) if m.sum() else None
        nk = post(D["now_safe"], D, kf)
        row["rose_else_nowcast_safe_kf"] = acc(np.where(mv, rose, nk), y, m)
        row["nowcast_safe_kf_on_still"] = acc(nk, y, m & ~mv)
        rk = post(D["cl_safe"], D, kf)
        row["report_safe_kf_on_still"] = acc(rk, y, m & ~mv)
        row["cheaper_on_still"] = acc((D["mid"] < 0.5).astype(float), y, m & ~mv)
        # disagreement subset report vs nowcast (safe, kf)
        dis = m & np.isfinite(nk) & np.isfinite(rk) & (nk != rk)
        row["disagree_n"] = int(dis.sum())
        row["disagree_nowcast_right"] = round(float((nk[dis] == y[dis]).mean()), 3) if dis.sum() else None
        key = time.strftime("%m-%d %H", time.gmtime(int(h))) if h != "all" else "all"
        blk[key] = row
    out[f"{a}_{b}"] = blk
print(json.dumps(out, indent=1)[:6000])
(HERE.parent / "results/iter16_nowcast.json").write_text(json.dumps(out, indent=1))
