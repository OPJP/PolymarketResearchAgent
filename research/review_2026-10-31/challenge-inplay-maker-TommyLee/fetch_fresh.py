"""Fetch public tapes for 60 FRESH maker-phase markets (first wallet fill >= 2026-10-17 UTC, >=5 fills, not in the
160-market sample), for a confirmatory test with parameters fixed beforehand (H4: D=120 s, L=2 s)."""
import pickle, json, random, time
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.profile import resolution_info
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
d=pickle.load(open(W+'/window.pkl','rb')); t,markets=d['trades'],d['markets']
old=set(pickle.load(open(W+'/tapes160.pkl','rb'))['cids'])
agg=t.groupby('condition_id').agg(first=('ts','min'),last=('ts','max'),n=('ts','size'))
cand=[c for c in agg.index if agg.at[c,'n']>=5 and agg.at[c,'first']>=1792195200 and c not in old]
print('candidates',len(cand))
rng=random.Random(11); pick=rng.sample(sorted(cand),60)
payouts,active={},{}
for c in pick:
    r=resolution_info(markets.get(c) or {}); tokens=json.loads((markets.get(c) or {}).get('clobTokenIds') or '[]')
    if r['resolved'] and len(tokens)==2:
        payouts[c]=r['payout'].get(str(tokens[0]),0.0); active[c]=(int(agg.at[c,'first']),int(agg.at[c,'last']))
pick=[c for c in pick if c in payouts]
pm=PolymarketData()
def load(cid):
    a,b=active[cid]
    taker,_,c1=pm.market_trades(cid,start=a-1800,end=b+600,taker_only=True)
    full,_,c2=pm.market_trades(cid,start=a-1800,end=b+600,taker_only=False)
    return cid,taker,full,c1.status,c2.status
t0=time.time()
with ThreadPoolExecutor(3) as ex: parts=list(ex.map(load,pick))
print('loaded',len(parts),'in',round(time.time()-t0,1),'s', pd.Series([p[3] for p in parts]).value_counts().to_dict(), pd.Series([p[4] for p in parts]).value_counts().to_dict())
pickle.dump({'cids':pick,'payouts':payouts,'active':active,'parts':parts},open(W+'/tapes_fresh60.pkl','wb'))
