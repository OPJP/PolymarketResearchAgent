"""Fresh holdout for H5: the wallet's other in-play US-sports games (not in the 128-game sample) that have spreads.
Fetch each event's markets from gamma (by event slug) and the public taker tape of its moneyline and spread markets."""
import sys, pickle, json, time, numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.adapters.polymarket import PolymarketData, GAMMA_API
from polyrea.analysis.profile import resolution_info
S=sys.argv[1]
t=pd.read_pickle(f'{S}/trades_enriched.pkl')
d=pickle.load(open(f'{S}/espn_games200.pkl','rb')); used={e['event_slug'] for e in d['games']}
t['league']=t.slug.str.split('-').str[0]
x=t[t.league.isin(['nba','nfl','cfb','wnba','nhl','mlb'])&(t.ts>=t.gst)]
g=x.groupby('event_slug').agg(n=('ts','size'),smts=('smt',lambda s:sorted(set(s))),gst=('gst','first'))
g=g[(g.n>=5)&~g.index.isin(used)&g.smts.map(lambda s:'spreads' in s)]
pm=PolymarketData()
def ev(slug):
    data,_=pm.http.get_json(f'{GAMMA_API}/events',{'slug':slug},adapter='gamma.events',max_age=None)
    return slug,(data or [None])[0]
with ThreadPoolExecutor(4) as ex: evs=dict(ex.map(ev,g.index))
wallet_cids=set(t.condition_id)
jobs=[]
for slug,e in evs.items():
    if not e: continue
    for m in e.get('markets') or []:
        st=m.get('sportsMarketType')
        if not m.get('gameStartTime'): continue
        if (st=='moneyline') or (st=='spreads' and m.get('conditionId') in wallet_cids):
            jobs.append((slug,m))
print('events',len(evs),'markets',len(jobs),flush=True)
def fetch(job):
    slug,m=job; gst=int(pd.Timestamp(m['gameStartTime']).timestamp()); r=resolution_info(m)
    end=int(min(r['closed_ts'] or gst+5*3600, gst+5*3600))
    rows,_,cov=pm.market_trades(m['conditionId'],start=gst,end=end,taker_only=True)
    return slug,m,rows
t0=time.time(); out=[]
with ThreadPoolExecutor(6) as ex:
    for i,res in enumerate(ex.map(fetch,jobs)):
        out.append(res)
        if i%50==0: print(i,round(time.time()-t0),len(res[2]),flush=True)
pickle.dump({'events':evs,'tapes':out,'split':int(np.median([e['start'] for e in d['games']]))},open(f'{S}/fresh_h5.pkl','wb'))
print('done',time.time()-t0)
