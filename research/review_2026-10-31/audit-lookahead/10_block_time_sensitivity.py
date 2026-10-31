"""Sensitivity of the Up/Down backtests to the block-time stamp (match time <= block time).
Taker: a print stamped ts was matched at ts - g; deciding with spot available at ts - latency
is lookahead whenever latency < g. Shown via backtest at latency 0..3 with the chosen theta.
Maker: a print stamped t0+1..t0+g may have matched BEFORE the bid posted at t0; re-run the
maker backtest with print times moved to ts - g."""
import pickle, json
from pathlib import Path
import numpy as np
from polyrea.analysis.updown import SpotIndex, taker_flow, maker_backtest, backtest

D = pickle.load(open(Path(__file__).parent / "data" / "btc5m.pkl", "rb"))
spot = SpotIndex(D["spot_ts"]); test = D["test"]
R = "/home/user/PolymarketResearchAgent/research/wallets/"
for w in ("0x3725d52f3c252e8374999cc8617292ea2608ad88", "0xb55fa1296e6ec55d0ce53d93b9237389f11764d4"):
    st = json.load(open(R + w + "/updown_study_btc_5m.json"))["derived"]["match_test"]
    th = st["theta"]
    out = []
    for L in (0, 1, 2, 3):
        b = backtest(test["prints"], spot, theta=th, latency=L)
        out.append(f"L={L}: ret {b['return_on_traded']:+.4f} pnl {b['pnl']:>9,.0f} p {b['per_window_p']:.3f}")
    print(w[:10], "taker theta", th, " | ".join(out))
flow = taker_flow(test["tapes"], test["windows"])
for delta, lat, label in ((0.08, 0, "chosen delta=0.08 lat=0 (0xc533/0x0ca4/0x3048)"), (0.08, 3, "chosen delta=0.08 lat=3 (0x3725/0xb55f)")):
    for at_touch in (False, True):
        res = []
        for g in (0, 1, 2, 3):
            f = flow.assign(ts=flow["ts"] - g)
            r = maker_backtest(f, test["windows"], spot, delta, lat, at_touch=at_touch)
            res.append(f"g={g}: ret {r['return_on_bought']:+.4f} pnl {r['pnl']:>8,.0f}")
        print(f"maker {label} at_touch={at_touch}: " + " | ".join(res))
