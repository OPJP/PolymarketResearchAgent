import json, random, sys, time
import pandas as pd
from polyrea.adapters.espn import LEAGUES
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.investigate import load_window
W='0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705'
AS_OF=1793318400
t0=time.time()
pm=PolymarketData()
win=load_window(W, days=30, as_of=AS_OF, pm=pm)
print('loaded', time.time()-t0)
t, markets = win["trades"], win["markets"]
print(t.columns.tolist()); print(len(t))
t = t.assign(league=t["slug"].str.split("-").str[0])
t = t[t["league"].isin(LEAGUES.keys())]
gs = {c: pd.Timestamp(m["gameStartTime"]).timestamp() for c, m in markets.items() if m.get("gameStartTime")}
t = t[t["condition_id"].map(lambda c: c in gs)]
t = t[t["ts"] >= t["condition_id"].map(gs)]
games = t.groupby("event_slug").agg(league=("league", "first"), n=("ts", "size"), first=("ts", "min"), cids=("condition_id", lambda x: sorted(set(x)))).reset_index()
games = games[games["n"] >= 5].sort_values("first")
print('in-play games n>=5:', len(games), games.league.value_counts().to_dict())
import pickle
pickle.dump(win, open(sys.argv[1],'wb'))
