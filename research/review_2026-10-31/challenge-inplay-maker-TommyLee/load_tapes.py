"""Reload the same 160 sampled markets as maker_study (seed=5) with full and taker tapes; cache to pickle."""
import pickle, json, random, time, sys
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.profile import resolution_info
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
d=pickle.load(open(W+'/window.pkl','rb'))
t, markets = d['trades'], d['markets']
w='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
pm=PolymarketData()
agg = t.groupby("condition_id").agg(first=("ts", "min"), last=("ts", "max"), n=("ts", "size"), usd=("usdc", "sum"))
agg = agg[agg["n"] >= 5]
rng = random.Random(5)
cids = list(agg.index)
if len(cids) > 160: cids = rng.sample(cids, 160)
payouts, active = {}, {}
for cid in cids:
    r = resolution_info(markets.get(cid) or {})
    tokens = json.loads((markets.get(cid) or {}).get("clobTokenIds") or "[]")
    if r["resolved"] and len(tokens) == 2:
        payouts[cid] = r["payout"].get(str(tokens[0]), 0.0)
        active[cid] = (int(agg.at[cid, "first"]), int(agg.at[cid, "last"]))
cids = [c for c in cids if c in payouts]
print(len(cids))
def load(cid):
    a,b=active[cid]
    taker,_,c1 = pm.market_trades(cid, start=a-1800, end=b+600, taker_only=True)
    full,_,c2 = pm.market_trades(cid, start=a-1800, end=b+600, taker_only=False)
    return cid, taker, full, c1.status, c2.status
t0=time.time()
with ThreadPoolExecutor(6) as ex:
    parts=list(ex.map(load,cids))
print('loaded', time.time()-t0)
print(pd.Series([p[3] for p in parts]).value_counts(), pd.Series([p[4] for p in parts]).value_counts())
pickle.dump({'cids':cids,'payouts':payouts,'active':active,'parts':parts}, open(W+'/tapes160.pkl','wb'))
