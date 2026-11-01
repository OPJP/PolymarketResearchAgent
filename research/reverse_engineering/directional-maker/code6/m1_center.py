"""Iteration 6, panel iter5 mechanics M1 (X30) + information I2 (X27): the ladder's common center F* and a race of
information inputs on it (development live block, BTC 5m; descriptive).

Every second t of a window where both books carry an exact-500 add within the last 1.5 s: top Up rung q_u = highest
bid-side +500 add, lowest ask-side +500 add a_u (= 1 - the top Down rung as a BUY Down price). Center F* = (q_u + a_u)/2,
half-spread h* = (a_u - q_u)/2, skew = F* - Up mid (touch series). Candidate inputs X: Binance USD-M futures bookTicker
mid and the Chainlink 1-s price (RTDS, by its own timestamp; strike = RTDS TWAP-60 stamped at the window start), each as
a digital fair of Up (realised futures 1-s vol of the last 300 s x 1.4, time left), at lags 0-2 s. Regress the skew on
(fair_X - mid): R^2 and slope on live BUILD (< 15:00 UTC), held-out R^2 on live VALIDATE (>= 15:00 UTC); own inventory
is not used here (the information panel found corr 0.005).
    python code6/m1_center.py <start_ts> <end_ts>
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
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
SPLIT = 1793458800


def main(a, b):
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet")
    ev = ev[ev.w.str.contains("btc-updown-5m") & (ev.d == 500.0)]
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 400, b) if r["r"][0] == "b" and r["r"][2]]
    fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s").drop_duplicates("s", keep="last")
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cl, tw = {}, {}
    for r in iter_dm("dm_rtds", a - 400, b + 60):
        try:
            j = json.loads(r["m"])
        except ValueError:
            continue
        for x in (j.get("payload") or {}).get("data", []) or []:
            (cl if r["q"] == "crypto_prices_chainlink" else tw)[int(x["timestamp"]) // 1000] = float(x["value"])
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    out_rows = []
    for w, g in ev.groupby("w"):
        st = int(w.split("-")[-1])
        if st < a or st + 300 > b:
            continue
        K_f = ms_sec[np.searchsorted(sec, st - 60):np.searchsorted(sec, st)].mean()
        K_c = tw.get(st)
        # futures strike mapped from the true (Chainlink TWAP-60) strike with the futures/Chainlink basis at the start
        kc0 = np.searchsorted(cls, st, side="right") - 1 if len(cls) else -1
        K_fb = (K_c * ms_sec[min(np.searchsorted(sec, st), len(ms_sec) - 1)] / clv[kc0]) if (K_c is not None and kc0 >= 0) else np.nan
        tw_ = tch[tch.w == w].sort_values("s")
        ts_, bb_, ba_ = tw_.s.to_numpy(), tw_.bb.to_numpy(), tw_.ba.to_numpy()
        gb, ga = g[g.side == 1], g[g.side == 0]
        for t in range(st + 5, st + 270):
            T = t * 1000
            mb = gb[(gb.s > T - 1500) & (gb.s <= T)]
            ma = ga[(ga.s > T - 1500) & (ga.s <= T)]
            if not len(mb) or not len(ma):
                continue
            qu, au = float(mb.p.max()), float(ma.p.min())
            if au <= qu:
                continue
            i = np.searchsorted(ts_, T, side="right") - 1
            if i < 0:
                continue
            mid = (bb_[i] + ba_[i]) / 2
            row = {"t": t, "w": w, "Fstar": (qu + au) / 2, "h": (au - qu) / 2, "mid": mid, "spread": ba_[i] - bb_[i], "rel": t - st}
            jj = np.searchsorted(sec, t)
            sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4
            tau = max(st + 300 - t, 1.0)
            for lag in (0, 1000, 1500, 2000, 2500, 3000, 4000, 6000):
                fmid = fm[max(np.searchsorted(fs, T - lag, side="right") - 1, 0)]
                row[f"fut{lag}"] = norm.cdf(np.log(fmid / K_f) / (sig * np.sqrt(tau))) if sig > 0 else np.nan
                if K_c is not None and len(cls) and K_fb == K_fb:
                    row[f"fb{lag}"] = norm.cdf(np.log(fmid / K_fb) / (sig * np.sqrt(tau))) if sig > 0 else np.nan
                if K_c is not None and len(cls):
                    k = np.searchsorted(cls, (T - lag) // 1000, side="right") - 1
                    row[f"cl{lag}"] = norm.cdf(np.log(clv[k] / K_c) / (sig * np.sqrt(tau))) if (k >= 0 and sig > 0) else np.nan
            out_rows.append(row)
    D = pd.DataFrame(out_rows)
    D["sk"] = D.Fstar - D.mid
    res = {"seconds": int(len(D)), "windows": int(D.w.nunique()), "pair_sum_top_rungs_median": round(float((1 - 2 * D.h).median()), 3),
           "h_star_q": D.h.quantile([.1, .5, .9]).round(3).to_dict(), "skew_q": D["sk"].quantile([.1, .25, .5, .75, .9]).round(3).to_dict(),
           "skew_autocorr_1s": round(float(D.groupby("w")["sk"].apply(lambda s: s.autocorr(1)).mean()), 3), "race": {}}
    tr, te = D[D.t < SPLIT], D[D.t >= SPLIT]
    for X in [c for c in D.columns if c.startswith("fut") or c.startswith("cl") or c.startswith("fb")]:
        sub_tr = tr[[X, "sk", "mid"]].dropna()
        sub_te = te[[X, "sk", "mid"]].dropna()
        if len(sub_tr) < 50 or len(sub_te) < 50:
            continue
        xtr, ytr = (sub_tr[X] - sub_tr.mid).to_numpy(), sub_tr["sk"].to_numpy()
        slope, icpt = np.polyfit(xtr, ytr, 1)
        r2_tr = float(np.corrcoef(xtr, ytr)[0, 1] ** 2)
        xte, yte = (sub_te[X] - sub_te.mid).to_numpy(), sub_te["sk"].to_numpy()
        pred = icpt + slope * xte
        r2_te = float(1 - np.sum((yte - pred) ** 2) / np.sum((yte - yte.mean()) ** 2))
        res["race"][X] = {"slope": round(float(slope), 3), "r2_build": round(r2_tr, 3), "r2_validate_heldout": round(r2_te, 3),
                          "n": [int(len(sub_tr)), int(len(sub_te))]}
    # H on time left
    res["h_by_time_left"] = D.groupby(pd.cut(300 - D.rel, [0, 60, 120, 180, 240, 300]), observed=True).h.median().round(3).rename(index=str).to_dict()
    res = json.loads(json.dumps(res, default=str))
    (HERE.parent / "results" / f"iter6_m1_center_{a}_{b}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
