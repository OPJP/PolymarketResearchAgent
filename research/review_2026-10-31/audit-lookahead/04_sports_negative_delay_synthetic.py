"""Issue: sports_study's FIT grid for the information delay D includes -10 and -5 s, and the
argmax over the grid is unrestricted. With D < 0, annotate() treats a scoring play as known
|D| seconds BEFORE its ESPN wall-clock time, so decisions use plays that have not happened yet.
(match_test for Up/Down restricts the chosen lag to >= 0; sports_study has no such guard.)"""
import numpy as np, pandas as pd
from polyrea.workflows.sports_study import annotate, _backtest

events = pd.DataFrame({"ts": [1000], "home_pts": [3], "away_pts": [0]})  # home scores at wallclock 1000
prints = pd.DataFrame({"event_slug": ["g"] * 2, "ts": [992, 995], "side_kind": ["home"] * 2, "is_wallet": [False, True],
                       "price": [0.50, 0.50], "size": [100.0, 100.0], "payout": [1.0, 1.0], "fee_rate": [0.0, 0.0]})
for D in (-10, -5, 0):
    a = annotate(prints, events, D)
    print(f"D={D:>3}: prints at ts {a['ts'].tolist()} (play happens at 1000) -> since={a['since'].tolist()} fav={a['fav'].tolist()} | backtest W=20: {_backtest(a, 20)}")

import inspect, polyrea.workflows.sports_study as ss
src = inspect.getsource(ss.run_sports_study)
print("grid line :", [l.strip() for l in src.splitlines() if "grid_d =" in l][0])
print("argmax line:", [l.strip() for l in src.splitlines() if "idxmax" in l][0])
