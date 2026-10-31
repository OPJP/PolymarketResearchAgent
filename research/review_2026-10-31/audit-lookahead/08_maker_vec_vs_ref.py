"""Check maker_backtest (vectorized) against _maker_backtest_reference on the real TEST tape."""
import pickle, time
from pathlib import Path
import numpy as np
from polyrea.analysis.updown import SpotIndex, taker_flow, maker_backtest, _maker_backtest_reference

D = pickle.load(open(Path(__file__).parent / "data" / "btc5m.pkl", "rb"))
spot = SpotIndex(D["spot_ts"]); test = D["test"]
flow = taker_flow(test["tapes"], test["windows"])
wins = test["windows"][:60]
cids = {w.condition_id for w in wins}
f = flow[flow.condition_id.isin(cids)]
for delta, lat, ms in ((0.08, 0, 0), (0.0, 3, 0), (0.02, 20, 30)):
    a = maker_backtest(f, wins, spot, delta, lat, min_secs_to_end=ms); b = _maker_backtest_reference(f, wins, spot, delta, lat, min_secs_to_end=ms)
    print(f"delta {delta} lat {lat} min_end {ms}: vec fills {a['fills']} pnl {a['pnl']:.4f} | ref fills {b['fills']} pnl {b['pnl']:.4f} | equal {abs(a['pnl']-b['pnl'])<1e-6 and a['fills']==b['fills']}")
