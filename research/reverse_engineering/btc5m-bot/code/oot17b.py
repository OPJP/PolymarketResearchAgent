"""Iteration 17, PRE-REGISTRATION 11b (post hoc, written after pre-registration 11's result showed the laptop receive clock drifting
from -637 to -1161 ms against Binance T over the block): the same score with a LOCAL clock offset. tau_loc(t) = median of (receive ms -
T) over the trade messages received in the trailing 60 s (causal; per 1-s grid, then per book message); book receive times shifted by
(131 - tau_loc). Everything else as oot17.py (model, anchor, threshold, orders). One run; reported next to the block-median result."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oot17 as base  # re-runs the pre-registered score (cheap) and leaves its arrays in the module
import dc_exam14 as dx

xt, xT, qt = base.xt, base.xT, base.qt
lag = (xt - xT).astype(float)
sec = xt // 1000
g = pd.Series(lag).groupby(sec).median()
full = pd.Series(np.nan, index=np.arange(sec.min(), sec.max() + 1)); full.loc[g.index] = g.values
loc = full.rolling(60, min_periods=5).median().ffill().bfill()
tq = loc.reindex(qt // 1000).ffill().bfill().to_numpy()
Tb = qt - tq + 131
three = base.o[base.o.wallet.isin(["DS", "GF", "XM"])]
sib = base.o[base.o.wallet.isin(["W4", "W5"])]
r = {"tau_loc_q": [float(x) for x in np.nanquantile(tq, [0.0, 0.5, 1.0])]}
r["local_offset"], sc = base.score(three, Tb)
r["local_offset_W4_W5"], _ = base.score(sib, Tb)
r["passes_bar_0.80"] = bool(r["local_offset"]["acc_per_order"] >= 0.80)
# sensitivity of the cut to a constant error in the clock (diagnostic only): shift the local cut by d ms
r["cut_shift_scan"] = {}
for d in (-100, -50, -25, 0, 25, 50, 100):
    rr, _ = base.score(three, Tb - d)
    r["cut_shift_scan"][d] = rr["acc_per_order"]
sc.to_parquet(base.S + "/oot17b_pred.parquet", index=False)
json.dump(r, open(base._ROOT + "/research/reverse_engineering/btc5m-bot/results/oot17b_side_localclock.json", "w"), indent=1, default=str)
print(json.dumps(r, indent=1, default=str))
