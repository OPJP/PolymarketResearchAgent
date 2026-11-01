"""Iteration 17: did the decision clock move in the new regime? Tick-lock PSTH of first legs (DS / GF / XM) of the 11-01 06:00-09:30
record on the live Binance spot book (rec_bn15 v2), with the LOCAL laptop clock offset (oot17b): Te = receive - tau_loc(t) (book
events on the exchange clock, minus the ~4 ms bookTicker lead which is common to the capture). Signed microprice change toward the
bought outcome per 10-ms bin of m0 - Te in [0, 800) ms, placebo m0 - 3 s subtracted. Compared with the capture days' peak (DS 265 ms,
GF 285, XM 305; iteration 16 finding 2). Usage: python knee17.py"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live
S = os.environ["RE16_SCRATCH"] + "/it17"
sc = pd.read_parquet(S + "/oot17b_pred.parquet")
win = pd.read_parquet(S + "/post17_windows.parquet")
a_ts, b_ts = int(win.start_ts.min()) - 10, int(win.end_ts.max()) + 10
qt, mic, xt, xT = [], [], [], []
for r in live.iter_live("btc5m_bnspot2", a_ts, b_ts):
    if r.get("k") == "q":
        b, B, a, A = float(r["b"]), float(r["B"]), float(r["a"]), float(r["A"])
        qt.append(r["t"]); mic.append((b * A + a * B) / (A + B))
    elif r.get("k") == "x":
        xt.append(r["t"]); xT.append(r["T"])
qt = np.asarray(qt, np.int64); mic = np.asarray(mic); o = np.argsort(qt, kind="stable"); qt, mic = qt[o], mic[o]
xt = np.asarray(xt, np.int64); xT = np.asarray(xT, np.int64)
lag = (xt - xT).astype(float); sec = xt // 1000
g = pd.Series(lag).groupby(sec).median()
full = pd.Series(np.nan, index=np.arange(sec.min(), sec.max() + 1)); full.loc[g.index] = g.values
loc = full.rolling(60, min_periods=5).median().ffill().bfill()
Te = qt - loc.reindex(qt // 1000).ffill().bfill().to_numpy()
dm = np.r_[0.0, np.diff(mic)]
f1 = sc[sc["first"]].copy()
BW, NB = 10, 80
res = {}
for w in ("ALL", "DS", "GF", "XM"):
    x = f1 if w == "ALL" else f1[f1.wallet == w]
    H = np.zeros(NB); Hp = np.zeros(NB)
    for m0, up in zip(x.m0.to_numpy(np.int64), x.is_up.to_numpy(bool)):
        sgn = 1.0 if up else -1.0
        for sh, acc in ((0, H), (3000, Hp)):
            lo, hi = np.searchsorted(Te, m0 - sh - NB * BW, "left"), np.searchsorted(Te, m0 - sh, "right")
            if hi > lo:
                b = ((m0 - sh - Te[lo:hi]) // BW).astype(int)
                k = (b >= 0) & (b < NB)
                np.add.at(acc, b[k], sgn * dm[lo:hi][k])
    D = (H - Hp) / max(len(x), 1)
    pk = int(np.argmax(D)); half = D[pk] / 2
    above = np.where(D >= half)[0]
    res[w] = {"n": int(len(x)), "peak_lag_ms": pk * BW + BW / 2, "half_max_span_ms": [int(above.min() * BW), int(above.max() * BW + BW)],
              "per_50ms": [round(float(D[i:i + 5].sum()), 4) for i in range(0, NB, 5)]}
res["note"] = "per_50ms bins start at 0 ms (m0 - Te in [0,50), [50,100), ...); microprice change in USD toward o per first leg, placebo subtracted"
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/knee17.json", "w"), indent=1)
print(json.dumps(res, indent=1))
