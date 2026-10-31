"""For the sampled soccer totals markets, fetch the event's moneyline markets (gamma events by slug) and their taker tapes."""
import sys, pickle, json, time, numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.adapters.polymarket import PolymarketData, GAMMA_API
from polyrea.analysis.profile import resolution_info
S=sys.argv[1]
P=pd.read_pickle(f'{S}/prints_L2.pkl'); st=P[P.set=='soccer_totals']
slugs=sorted(st.event_slug.unique())
pm=PolymarketData()
def ev(slug):
    try:
        data,_=pm.http.get_json(f'{GAMMA_API}/events',{'slug':slug.replace('-more-markets','')},adapter='gamma.events',max_age=None)
    except Exception as e: return slug,None
    return slug,(data or [None])[0]
with ThreadPoolExecutor(4) as ex: evs=dict(ex.map(ev,slugs))
jobs=[(s,m) for s,e in evs.items() if e for m in (e.get('markets') or []) if m.get('sportsMarketType')=='moneyline' and m.get('gameStartTime')]
print('events',len(evs),'ml markets',len(jobs),flush=True)
def fetch(job):
    slug,m=job; gst=int(pd.Timestamp(m['gameStartTime']).timestamp()); r=resolution_info(m)
    end=int(min(r['closed_ts'] or gst+4*3600, gst+4*3600))
    rows,_,_=pm.market_trades(m['conditionId'],start=gst,end=end,taker_only=True); return slug,m,rows
t0=time.time(); out=[]
with ThreadPoolExecutor(6) as ex:
    for i,res in enumerate(ex.map(fetch,jobs)):
        out.append(res)
        if i%100==0: print(i,round(time.time()-t0),flush=True)
pickle.dump({'events':evs,'tapes':out},open(f'{S}/soccer_ml.pkl','wb')); print('done',time.time()-t0)
