"""Synthetic check: does annotate()/_backtest() with D<0 use a play before it happens?"""
import pandas as pd
from polyrea.adapters.espn import Game, Play
from polyrea.workflows.sports_study import annotate, scoring_events, _backtest

# Home team scores at wall clock 1000; home wins (payout 1 for home buys).
g = Game("nba", "x", "Atlanta Hawks", "Miami Heat", 900, (Play(900, 0, 0, False, None, "tip"), Play(1000, 2, 0, True, None, "Hawks score")))
ev = scoring_events(g)
print("scoring events:", ev.to_dict("records"))
rows = [{"event_slug": "g", "ts": ts, "is_wallet": False, "side_kind": "home", "price": 0.5, "size": 100.0, "payout": 1.0, "fee_rate": 0.0} for ts in (992, 995, 1003)]
p = pd.DataFrame(rows)
for D in (-10, -5, 0, 5):
    a = annotate(p, ev, D)
    print(f"D={D:>3}: ts={a['ts'].tolist()} since={a['since'].tolist()} fav={a['fav'].tolist()}")
    pre = a[(a['ts'] < 1000)]
    bt = _backtest(pre, 20)
    print(f"        _backtest on the two PRE-play prints (992, 995): trades={bt.get('trades')} pnl={bt.get('pnl')} return={bt.get('return_on_traded')}")
