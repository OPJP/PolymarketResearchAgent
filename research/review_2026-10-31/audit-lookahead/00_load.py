"""Load the cached BTC 5m FIT/TEST periods exactly as the studies do, and pickle them."""
import pickle, sys, time
from pathlib import Path
from polyrea.workflows.investigate import default_as_of
from polyrea.workflows.updown_study import load_period, sample_blocks, DAY
from polyrea.adapters.polymarket import PolymarketData
from polyrea.pit import TimeSeries
import numpy as np

OUT = Path(__file__).parent / "data"
as_of = default_as_of()
fit_b = sample_blocks(as_of - 14 * DAY, as_of - 7 * DAY, 12, 7200, 7)
test_b = sample_blocks(as_of - 7 * DAY, as_of, 12, 7200, 8)
print("as_of", as_of, "fit blocks", fit_b[:3], "... test blocks", test_b[:3])
pm = PolymarketData()
t0 = time.time()
fit = load_period("btc", "5m", fit_b, pm, with_full_tape=True)
test = load_period("btc", "5m", test_b, pm, with_full_tape=True)
print("loaded in", round(time.time() - t0, 1), "s; fit windows", len(fit["windows"]), "test windows", len(test["windows"]))
ev = np.concatenate([fit["spot"].event_ts, test["spot"].event_ts])
vals = np.concatenate([fit["spot"].values, test["spot"].values])
order = np.argsort(ev, kind="stable")
spot_ts = TimeSeries.build(fit["spot"].name, zip(ev[order].tolist(), vals[order].tolist()), availability_lag=1)
pickle.dump({"as_of": as_of, "fit_blocks": fit_b, "test_blocks": test_b, "fit": fit, "test": test, "spot_ts": spot_ts}, open(OUT / "btc5m.pkl", "wb"))
print("fit prints", len(fit["prints"]), "test prints", len(test["prints"]), "spot seconds", len(spot_ts))
