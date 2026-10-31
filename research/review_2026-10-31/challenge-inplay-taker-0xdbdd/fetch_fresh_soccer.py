"""Fresh soccer holdout for H6: wallet-traded soccer totals markets NOT in the first sample, their tapes, and the
event's moneyline (win/draw) market tapes."""
import sys, pickle, json, re, time, numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.adapters.polymarket import PolymarketData, GAMMA_API
from polyrea.analysis.profile import resolution_info
S=sys.argv[1]; NMAX=int(sys.argv[2])
t=pd.read_pickle(f'{S}/trades_enriched.pkl'); m=pickle.load(open(f'{S}/window.pkl','rb'))['markets']
used=set(pickle.load(open(f'{S}/tapes.pkl','rb'))['sel'].condition_id)
AS_OF=1793318400; START=AS_OF-30*86400
t=t[t.gst.notna()]
mk=t.groupby('condition_id').agg(fam=('fam','first'),smt=('smt','first'),gst=('gst','first'),title=('title','first')).reset_index()
mk['line']=mk.title.map(lambda s: float(re.search(r'O/U (\d+\.?\d*)',s).group(1)) if re.search(r'O/U (\d+\.?\d*)',s or '') else np.nan)
soc={'other','sports:epl','sports:lal','sports:ucl','sports:bun','sports:sea','sports:ukr','sports:mls','sports:uel','sports:spl','sports:fl'}
c=mk[(mk.smt=='totals')&mk.fam.isin(soc)&(mk.line<=6.5)&~mk.condition_id.isin(used)&(mk.gst>=START)&(mk.gst<AS_OF-6*3600)]
c=c.sample(min(NMAX,len(c)),random_state=99)
print('fresh totals markets',len(c),flush=True)
pm=PolymarketData()
def tape(cid,mm,gst,hours):
    r=resolution_info(mm); end=int(min(r['closed_ts'] or gst+hours*3600, gst+hours*3600))
    rows,_,_=pm.market_trades(cid,start=int(gst)-600,end=end,taker_only=True); return rows
def ev(slug):
    data,_=pm.http.get_json(f'{GAMMA_API}/events',{'slug':slug.replace('-more-markets','')},adapter='gamma.events',max_age=None)
    return (data or [None])[0]
c['event_slug']=c.condition_id.map(lambda x:(m[x].get('events') or [{}])[0].get('slug'))
c=c[c.event_slug.notna()]
with ThreadPoolExecutor(4) as ex: evs=dict(zip(c.event_slug.unique(), ex.map(ev,c.event_slug.unique())))
jobs=[('tot',r.condition_id,m[r.condition_id],r.gst,r.event_slug) for r in c.itertuples()]
for s,e in evs.items():
    for mm in (e or {}).get('markets') or []:
        if mm.get('sportsMarketType')=='moneyline' and mm.get('gameStartTime'):
            jobs.append(('ml',mm['conditionId'],mm,pd.Timestamp(mm['gameStartTime']).timestamp(),s))
print('jobs',len(jobs),flush=True)
t0=time.time(); out=[]
def run(j):
    kind,cid,mm,gst,s=j
    try: return kind,cid,mm,gst,s,tape(cid,mm,gst,6 if kind=='tot' else 4)
    except Exception as e: return kind,cid,mm,gst,s,None
with ThreadPoolExecutor(6) as ex:
    for i,r in enumerate(ex.map(run,jobs)):
        out.append(r)
        if i%100==0: print(i,round(time.time()-t0),flush=True)
pickle.dump({'sel':c,'events':evs,'tapes':out},open(f'{S}/fresh_soccer.pkl','wb')); print('done',time.time()-t0)
