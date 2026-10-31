"""Reproduce the recorded spot-latency taker match test and wallet replays with the project's own functions."""
import sys, json
import numpy as np
from common import *
from polyrea.analysis.updown import SpotIndex, match_test, wallet_replay, backtest
from polyrea.pit import TimeSeries
d, G = load()
ev = np.concatenate([d["fit"]["spot_ev"], d["test"]["spot_ev"]]); vals = np.concatenate([d["fit"]["spot_vals"], d["test"]["spot_vals"]])
o = np.argsort(ev, kind="stable")
spot = SpotIndex(TimeSeries.build("spot", zip(ev[o].tolist(), vals[o].tolist()), availability_lag=1))
out = {}
for name in sys.argv[1:]:
    w = W[name]
    mt = match_test(d["fit"]["prints"], d["test"]["prints"], w, spot, n_perm=200, seed=7)
    rp = wallet_replay(d["test"]["prints"], w)
    bt = backtest(d["test"]["prints"], spot, theta=mt["theta"], latency=mt["chosen_latency_s"])
    out[name] = {"latency": mt["chosen_latency_s"], "theta": mt["theta"], "test_auc": mt["test"]["auc"], "null_mean": mt["test"]["auc_null_mean"], "perm_p": mt["test"]["auc_perm_p"],
                 "wallet_replay": rp, "backtest": {k: bt[k] for k in ("trades", "pnl", "return_on_traded", "per_window_p")}}
    print(name, json.dumps(out[name], default=float), flush=True)
json.dump(out, open("repro_match.json", "w"), indent=1, default=float)
