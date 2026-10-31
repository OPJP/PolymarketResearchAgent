"""Load the exact BTC 5m FIT/TEST inputs of the stored study from the HTTP cache and pickle them."""
import json, pickle, sys, time
import numpy as np
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.updown_study import load_period, sample_blocks, DAY
from polyrea.pit import TimeSeries
from polyrea.analysis.updown import maker_buy_prints

OUT = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/verify-lookahead-0/data.pkl"
st = json.load(open("/home/user/PolymarketResearchAgent/research/wallets/0xc53375ff94e96100f2b30a4b5775db35218d69a9/updown_study_btc_5m.json"))
as_of = st["subject"]["as_of"]
fit_blocks = sample_blocks(as_of - 14 * DAY, as_of - 7 * DAY, 12, 7200, 7)
test_blocks = sample_blocks(as_of - 7 * DAY, as_of, 12, 7200, 8)
assert [list(b) for b in fit_blocks] == st["observed"]["fit_blocks"], "fit blocks differ"
assert [list(b) for b in test_blocks] == st["observed"]["test_blocks"], "test blocks differ"
pm = PolymarketData()
t0 = time.time()
fit = load_period("btc", "5m", fit_blocks, pm, with_full_tape=True)
test = load_period("btc", "5m", test_blocks, pm, with_full_tape=True)
print("loaded in", round(time.time() - t0, 1), "s")
ev = np.concatenate([fit["spot"].event_ts, test["spot"].event_ts])
vals = np.concatenate([fit["spot"].values, test["spot"].values])
order = np.argsort(ev, kind="stable")
spot_ts = TimeSeries.build(fit["spot"].name, zip(ev[order].tolist(), vals[order].tolist()), availability_lag=1)
fit_m = maker_buy_prints(fit["full_tapes"], fit["tapes"], fit["windows"])
test_m = maker_buy_prints(test["full_tapes"], test["tapes"], test["windows"])
print("fit prints", len(fit["prints"]), "test prints", len(test["prints"]), "spot seconds", len(spot_ts))
print("fit maker prints", len(fit_m), "test maker prints", len(test_m))
pickle.dump({"as_of": as_of, "fit_blocks": fit_blocks, "test_blocks": test_blocks,
             "fit_prints": fit["prints"], "test_prints": test["prints"], "spot_ts": spot_ts,
             "fit_m": fit_m, "test_m": test_m}, open(OUT, "wb"))
