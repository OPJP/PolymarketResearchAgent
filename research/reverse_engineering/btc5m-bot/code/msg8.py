"""Iteration 8, X52 (panel-mechanics iter7 P4): one triggering message per decision?
Per-series arrival lags L_v = the peak bin (+25 ms, bin centre) of the iteration-7 50-ms directional-excess kernels, fitted on
14:50-16:04 (results/kernel7_1793458200.json; never refit here). For each taker match m of a LATER interval, every
microprice tick (|change| > 0.002 bp between consecutive records) of every lab series v gets an effective time T + L_v; the
trigger = the tick with the latest effective time in [m - W, m] (W = 150 ms); side = its direction. Scored against the frozen
ten-series vote, by vote strength, on 16:04-16:33 and 16:33-17:55 (lab feed btc5m_venues2). Writes results/msg8.json."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lag7 import micro_series, mv
from live8 import fills_for, OWN

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
K7 = json.load(open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "kernel7_1793458200.json")))["series"]
LAG = {tuple(k.split("_")): -(v["peak_bin_ms"] + 25) for k, v in K7.items() if v.get("peak_directional_excess", 0) > 0.02}


def run(own, a, b, W=150):
    d, tok, trades = fills_for(own, a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[d.role == "T"].drop_duplicates(["tx", "token"]).copy(); tk["m"] = tk.tx.map(mt); tk = tk[tk.m.notna()]
    tk = tk[(tk.m >= a * 1000 + 5000) & (tk.m < b * 1000)]
    S = micro_series("btc5m_venues2", a, b); keys = sorted(S)
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool)
    Q = np.vstack([mv(S, k, m - 600, m - 100) for k in keys]); cov = np.isfinite(Q).any(axis=0)
    vote = np.where(cov, np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0), 0)
    # ticks per series with effective times
    eff_t, eff_s = [], []
    for k in keys:
        if k not in LAG:
            continue
        T, p, sc = S[k]
        r = np.r_[0.0, (p[1:] / p[:-1] - 1) * 1e4 / sc]
        sel = np.abs(r) > 0.002
        eff_t.append(T[sel] + LAG[k]); eff_s.append(np.sign(r[sel]))
    et = np.concatenate(eff_t); es = np.concatenate(eff_s); o = np.argsort(et, kind="stable"); et, es = et[o], es[o]
    i = np.searchsorted(et, m, "right") - 1
    trig = np.where((i >= 0) & (et[np.clip(i, 0, None)] >= m - W), es[np.clip(i, 0, None)], 0)
    okv = (vote > 0) == up; okt = (trig > 0) == up; av = np.abs(vote)
    out = {"n": int(len(m)), "lags_ms": {f"{k[0]}_{k[1]}": int(v) for k, v in LAG.items()}, "trigger_cover": round(float((trig != 0).mean()), 3),
           "trigger_agree": round(float(okt[trig != 0].mean()), 3) if (trig != 0).any() else None}
    for nm, s in (("strong_3plus", av >= 3), ("weak_1_2", (av >= 1) & (av <= 2)), ("no_vote", av == 0)):
        kt = s & (trig != 0)
        out[nm] = {"n": int(s.sum()), "vote_agree": round(float(okv[s & (av > 0)].mean()), 3) if (s & (av > 0)).any() else None,
                   "trigger_cover": round(float(kt.sum() / max(s.sum(), 1)), 3), "trigger_agree": round(float(okt[kt].mean()), 3) if kt.any() else None}
    return out


if __name__ == "__main__":
    res = {}
    for key in ("B", "C"):
        own, a, b = OWN[key]
        for W in (100, 150, 250):
            r = run(own, a, b, W); res[f"{key}_W{W}"] = r
            print(key, W, json.dumps({k: v for k, v in r.items() if k != "lags_ms"}), flush=True)
    res["lags_ms"] = {f"{k[0]}_{k[1]}": int(v) for k, v in LAG.items()}
    json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "msg8.json"), "w"), indent=1)
