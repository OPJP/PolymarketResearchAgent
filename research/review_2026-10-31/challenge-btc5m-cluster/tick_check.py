"""Re-run the recorded directional spot-maker backtest (polyrea.analysis.updown.maker_backtest) with the markets'
actual tick size (orderPriceMinTickSize = 0.001) instead of the 0.01 used in the study; FIT delta scan then TEST."""
import pickle, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.pit import TimeSeries
from polyrea.analysis.updown import SpotIndex, maker_backtest
d = pickle.load(open("data.pkl", "rb"))
ev = np.concatenate([d["fit"]["spot_ev"], d["test"]["spot_ev"]]); vals = np.concatenate([d["fit"]["spot_vals"], d["test"]["spot_vals"]])
o = np.argsort(ev, kind="stable")
spot = SpotIndex(TimeSeries.build("spot", zip(ev[o].tolist(), vals[o].tolist()), availability_lag=1))
keep = ("fills", "pnl", "return_on_bought", "per_window_t", "per_window_p")
out = {}
for tick in (0.01, 0.001):
    for at in (False, True):
        scan = {dl: maker_backtest(d["fit"]["flow"], d["fit"]["windows"], spot, dl, 0, tick=tick, at_touch=at) for dl in (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)}
        best = max(scan, key=lambda k: scan[k].get("per_window_t", -1e9) if scan[k].get("fills", 0) >= 30 else -1e9)
        te = maker_backtest(d["test"]["flow"], d["test"]["windows"], spot, best, 0, tick=tick, at_touch=at)
        key = f"tick={tick},at_touch={at}"
        out[key] = {"fit_scan": {str(k): {kk: v.get(kk) for kk in keep} for k, v in scan.items()}, "chosen_delta": best, "test": {kk: te.get(kk) for kk in keep}}
        print(key, "chosen", best, {kk: te.get(kk) for kk in keep}, flush=True)
json.dump(out, open("tick_check.json", "w"), indent=1, default=float)
