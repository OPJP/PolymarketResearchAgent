"""Load the cached FIT/TEST BTC-5m blocks (same blocks as the recorded studies) and dump to pickle."""
import os, sys, pickle, time
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import numpy as np, pandas as pd
from polyrea.workflows.updown_study import load_period, sample_blocks, DAY
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.updown import maker_buy_prints, taker_flow, taker_buy_prints
from polyrea.pit import TimeSeries

OUT = os.path.dirname(os.path.abspath(__file__))
AS_OF = 1793318400  # frozen as_of of the recorded studies (2026-10-30 00:00 UTC)
fitb = sample_blocks(AS_OF - 14 * DAY, AS_OF - 7 * DAY, 12, 7200, 7)
testb = sample_blocks(AS_OF - 7 * DAY, AS_OF, 12, 7200, 8)
print("fit blocks", fitb[:3], "test blocks", testb[:3])
pm = PolymarketData()
t0 = time.time()
res = {}
for name, blocks in (("fit", fitb), ("test", testb)):
    d = load_period("btc", "5m", blocks, pm, with_full_tape=True)
    print(name, "windows", len(d["windows"]), "prints", len(d["prints"]), "partial", len(d["partial_tapes"]), "elapsed", round(time.time() - t0, 1))
    res[name] = {
        "blocks": blocks,
        "windows": d["windows"],
        "tapes": d["tapes"],
        "full_tapes": d["full_tapes"],
        "spot_ev": d["spot"].event_ts, "spot_vals": d["spot"].values,
        "prints": d["prints"],
        "maker_prints": maker_buy_prints(d["full_tapes"], d["tapes"], d["windows"]),
        "flow": taker_flow(d["tapes"], d["windows"]),
    }
with open(os.path.join(OUT, "data.pkl"), "wb") as f:
    pickle.dump(res, f)
print("done", time.time() - t0)
