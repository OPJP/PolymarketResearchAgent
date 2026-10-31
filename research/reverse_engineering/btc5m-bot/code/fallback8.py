"""Iteration 8: a FULL-COVERAGE live side rule. The frozen vote abstains when no series moved in [m - 600, m - 100) ms
(32% of decisions on the six exam series). Fallback found on interval A (pmside8: weak / no-vote decisions buy the outcome
whose Polymarket ask FELL, 56-59% vs placebo 45-55%): side = vote if any series voted; else the outcome whose ask fell over
[m - 600, m - 100) (Up ask = ba; Down ask = 1 - bb); else the outcome whose ask fell over [m - 3000, m - 100); else the
favourite (ask > 0.5) [pre-registered order of fallbacks, 10-31 18:14 UTC, before scoring interval C].
Scored on the later development interval C (16:33-17:55; never used to choose the rule) with the exam feeds (six series,
btc5m_xven + btc5m_xclob) and the lab feeds (ten series, btc5m_venues2 + btc5m_clob_raw2). Writes results/fallback8.json."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
from lag7 import micro_series, mv
from gate8 import raw_touch
from live8 import fills_for, OWN


def run(own, a, b, vf, cf, venues):
    d, tok, trades = fills_for(own, a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[d.role == "T"].drop_duplicates(["tx", "token"]).copy(); tk["m"] = tk.tx.map(mt); tk = tk[tk.m.notna()]
    tk = tk[(tk.m >= a * 1000 + 5000) & (tk.m < b * 1000)]
    S = micro_series(vf, a, b); keys = [k for k in sorted(S) if k[0] in venues]
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool); stt = tk.start.to_numpy()
    Q = np.vstack([mv(S, k, m - 600, m - 100) for k in keys])
    vote = np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0)
    R = raw_touch(cf, a, b)
    sig = {W: np.zeros(len(m)) for W in (600, 3000)}; ask_up = np.full(len(m), np.nan)
    for s0, rg in R.groupby("m"):
        sel = np.where(stt == s0)[0]
        if not len(sel):
            continue
        rs = rg.s.to_numpy(np.int64); ba = rg.ba.to_numpy(float); bb = rg.bb.to_numpy(float)
        def at(x, tt):
            i = np.searchsorted(rs, tt, "right") - 1
            o = x[np.clip(i, 0, None)].astype(float); o[i < 0] = np.nan
            return o
        ask_up[sel] = at(ba, m[sel] - 100)
        for W in (600, 3000):
            dU = at(ba, m[sel] - 100) - at(ba, m[sel] - W)          # Up ask change (fell < 0 -> buy Up)
            dD = -(at(bb, m[sel] - 100) - at(bb, m[sel] - W))       # Down ask change = -(Up bid change)
            s = np.where((dU < -0.005) & ~(dD < -0.005), 1, np.where((dD < -0.005) & ~(dU < -0.005), -1, 0))
            sig[W][sel] = s
    pred = np.where(vote > 0, 1, np.where(vote < 0, -1, 0)).astype(float)
    src = np.where(pred != 0, "vote", "")
    for W in (600, 3000):
        k = (pred == 0) & (sig[W] != 0)
        pred[k] = sig[W][k]; src = np.where(k, f"pm_ask_fell_{W}", src)
    k = (pred == 0) & np.isfinite(ask_up)
    pred[k] = np.where(ask_up[k] > 0.5, 1, -1); src = np.where(k, "favourite", src)
    ok = (pred > 0) == up
    out = {"n": int(len(m)), "series": [f"{x}_{y}" for x, y in keys], "full_coverage_accuracy": round(float(ok[pred != 0].mean()), 4),
           "covered": round(float((pred != 0).mean()), 4)}
    for s in ("vote", "pm_ask_fell_600", "pm_ask_fell_3000", "favourite"):
        kk = src == s
        out[s] = [round(float(ok[kk].mean()), 3) if kk.any() else None, int(kk.sum())]
    wal = tk.wallet.to_numpy()
    out["by_wallet"] = {w: [round(float(ok[(wal == w) & (pred != 0)].mean()), 3), int(((wal == w) & (pred != 0)).sum())] for w in ("DS", "GF", "XM") if (wal == w).any()}
    return out


if __name__ == "__main__":
    res = {}
    own, a, b = OWN["C"]
    res["C_exam_six_series"] = run(own, a, b, "btc5m_xven", "btc5m_xclob", ("bf", "bs", "ok"))
    print(json.dumps(res["C_exam_six_series"]), flush=True)
    res["C_lab_ten_series"] = run(own, a, b, "btc5m_venues2", "btc5m_clob_raw2", ("bf", "bs", "ok", "by", "hl"))
    print(json.dumps(res["C_lab_ten_series"]), flush=True)
    res["C_lab_eight_series_no_hl"] = run(own, a, b, "btc5m_venues2", "btc5m_clob_raw2", ("bf", "bs", "ok", "by"))
    print(json.dumps(res["C_lab_eight_series_no_hl"]), flush=True)
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "fallback8.json"), "w"), indent=1)
