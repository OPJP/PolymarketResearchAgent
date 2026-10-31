"""Split the D<0 TEST backtest into trades executed before vs after the play's ESPN wall clock."""
import pickle, sys
import numpy as np, pandas as pd
from polyrea.workflows.sports_study import annotate, _backtest
d = pickle.load(open(sys.argv[1], "rb")); allp, events, test = d["allp"], d["events"], d["test"]
W = 20
for D in (-10, -5, 0):
    parts = []
    for s in test:
        p = allp[allp["event_slug"] == s]
        if p.empty: continue
        a = annotate(p, events[s], D); a["wc"] = a["ts"] - a["since"] - D; parts.append(a)
    a = pd.concat(parts, ignore_index=True)
    sel = a[(a["since"] >= 0) & (a["since"] <= W) & (a["fav"] > 0) & a["payout"].notna()]
    pre, post = sel[sel["ts"] < sel["wc"]], sel[sel["ts"] >= sel["wc"]]
    for name, x in (("pre-wallclock", pre), ("post-wallclock", post)):
        if len(x) == 0: print(f"D={D:>3} {name:14s}: 0 trades"); continue
        usd = np.minimum(x["size"] * x["price"], 100.0); sh = usd / x["price"]
        pnl = sh * x["payout"] - usd - x["fee_rate"] * x["price"] * (1 - x["price"]) * sh
        print(f"D={D:>3} {name:14s}: trades {len(x):>6} usd {usd.sum():>11,.0f} pnl {pnl.sum():>9,.0f} return {pnl.sum()/usd.sum():+.4f}")
