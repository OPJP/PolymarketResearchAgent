"""Iteration 13 (X124 = assumptions P4 step 1, on the public archive instead of the live lab): the window OPEN as a decision type.
On the dcside13 frame (10-20 / 10-21 operator taker orders, a = archive match ms - 180): for decisions in [0, 15) s vs [30, 300)
s, agreement of the order's outcome with (i) the Binance spot microprice tick over [a - 250, a), (ii) the exact-strike value
side argmax_o (FV_o - ask_o), FV_up = Phi(ln(CL(a) / K) / (sigma sqrt(tau))) with CL = RTDS Chainlink (server clock <= a), K =
Gamma priceToBeat, sigma = the 15-min realized vol of Binance 1-s returns, (iii) the underdog by ask; and P(large).
Usage: python open13.py FRAME_TAG ARCHIVE_DIR"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
from scipy.special import ndtr
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
tag, A = sys.argv[1], sys.argv[2]
X = pd.read_parquet(f"{C}/it13/dcside13_frame{tag}.parquet")
win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
ptb = pd.read_parquet(f"{C}/ptb.parquet").set_index("start").priceToBeat.astype(float)
st = win.loc[X.cid, "start_ts"].to_numpy(np.int64)
a = ((X.rel.to_numpy() + st) * 1000).astype(np.int64); k = ptb.reindex(st).to_numpy(float)
b = pd.read_parquet(f"{C}/binance_1s.parquet"); s0 = int(b.sec.min())
px = b.set_index("sec").close.reindex(np.arange(s0, int(b.sec.max()) + 1)).ffill().to_numpy(float)
r1 = np.r_[0.0, np.diff(np.log(px))]; c2 = np.cumsum(r1 ** 2)
sec = a // 1000 - 2
rv = np.sqrt(np.maximum((c2[np.clip(sec - s0, 0, None)] - c2[np.clip(sec - 900 - s0, 0, None)]) / 900.0, 1e-14))
def at(T, V, tt):
    i = np.searchsorted(T, tt, "right") - 1
    o = V[np.clip(i, 0, len(V) - 1)].astype(float); o[i < 0] = np.nan
    return o
cl = np.full(len(X), np.nan)
for day in sorted(X.day.unique()):
    m = (X.day == day).to_numpy()
    r = pd.read_parquet(f"{A}/btcrtds_{day}.parquet", columns=["serverTimestampMs", "fullAccuracyValue"]).sort_values("serverTimestampMs")
    cl[m] = at(r.serverTimestampMs.to_numpy(np.int64), r.fullAccuracyValue.astype(float).to_numpy() / 1e18, a[m])
tau = np.maximum(st + 300 - a / 1000.0, 1.0)
fvu = ndtr(np.log(cl / k) / (rv * np.sqrt(tau)))
gapU, gapD = fvu - X.askU_0.to_numpy(), (1 - fvu) - X.askD_0.to_numpy()
value = np.where(np.isfinite(gapU) & np.isfinite(gapD), np.sign(gapU - gapD), np.nan)
y = X.up.to_numpy() == 1; rel = X.rel.to_numpy(); lg = X.osz.to_numpy() >= 45
sig = {"tick_bs_mic_250": np.sign(X.bs_mic_250.to_numpy()), "value_exact_strike": value, "underdog": np.where(X.askU_0 < 0.5, 1.0, -1.0),
       "fav_exact_strike": np.sign(fvu - 0.5)}
res = {}
for nm, v in sig.items():
    o = {}
    for a0, b0 in ((-60, 0), (0, 15), (15, 30), (30, 300)):
        mm = (rel >= a0) & (rel < b0) & np.isfinite(v) & (v != 0)
        o[f"{a0}-{b0}"] = [round(float(((v[mm] > 0) == y[mm]).mean()), 4) if mm.any() else None, int(mm.sum())]
    res[nm] = o
res["p_large"] = {f"{a0}-{b0}": round(float(lg[(rel >= a0) & (rel < b0)].mean()), 4) for a0, b0 in ((-60, 0), (0, 15), (15, 30), (30, 300))}
mm = (rel >= 0) & (rel < 15) & np.isfinite(value) & (value != 0)
res["open_value_gap_abs_q"] = [round(float(x), 4) for x in np.nanpercentile(np.abs(gapU - gapD)[mm], [25, 50, 75])]
big = mm & (np.abs(gapU - gapD) > 0.05)
res["open_value_side_when_gap_gt_5c"] = [round(float(((value[big] > 0) == y[big]).mean()), 4) if big.any() else None, int(big.sum())]
json.dump(res, open(f"{R}/open13{tag}.json", "w"), indent=1)
print(json.dumps(res))
