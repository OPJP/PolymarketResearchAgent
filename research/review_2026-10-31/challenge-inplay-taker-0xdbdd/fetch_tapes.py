"""Fetch public taker tapes for a stratified sample of the wallet's in-play markets."""
import pickle, json, sys, time, re, random
import pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.profile import resolution_info
S=sys.argv[1]; N_TOT=int(sys.argv[2]); N_GEN=int(sys.argv[3])
t=pd.read_pickle(f'{S}/trades_enriched.pkl')
d=pickle.load(open(f'{S}/window.pkl','rb')); m=d['markets']
AS_OF=1793318400; START=AS_OF-30*86400; SPLIT=AS_OF-15*86400
t=t[t.gst.notna()]
mk=t.groupby('condition_id').agg(fam=('fam','first'),smt=('smt','first'),gst=('gst','first'),title=('title','first'),usdc=('usdc','sum'),n=('ts','size')).reset_index()
mk=mk[(mk.gst>=START)&(mk.gst<AS_OF-6*3600)]
def line(title):
    mm=re.search(r'O/U (\d+\.?\d*)',title or ''); return float(mm.group(1)) if mm else np.nan
mk['line']=mk.title.map(line)
soccer_fams={'other','sports:epl','sports:lal','sports:ucl','sports:bun','sports:sea','sports:ukr','sports:mls','sports:uel','sports:spl','sports:fl'}
tot=mk[(mk.smt=='totals')&mk.fam.isin(soccer_fams)&(mk.line<=6.5)]
gen=mk[~mk.condition_id.isin(tot.condition_id)&mk.smt.isin(['moneyline','child_moneyline','totals','spreads'])]
rng=np.random.default_rng(7)
def strat(df,n):
    out=[]
    for half,(lo,hi) in enumerate([(START,SPLIT),(SPLIT,AS_OF)]):
        x=df[(df.gst>=lo)&(df.gst<hi)]
        k=min(n//2,len(x)); out.append(x.sample(k,random_state=int(rng.integers(1e9))))
    return pd.concat(out)
sel=pd.concat([strat(tot,N_TOT).assign(set='soccer_totals'),strat(gen,N_GEN).assign(set='general')])
print(sel.groupby(['set','fam']).size().sort_values(ascending=False).head(30))
pm=PolymarketData()
def fetch(row):
    mm=m[row.condition_id]; r=resolution_info(mm)
    st=int(row.gst)-600
    en=int(min(r['closed_ts'] or (row.gst+6*3600), row.gst+6*3600))
    try:
        rows,src,cov=pm.market_trades(row.condition_id,start=st,end=en,taker_only=True)
    except Exception as e:
        return row.condition_id, None, str(e)
    return row.condition_id, rows, cov.status
t0=time.time(); out={}
with ThreadPoolExecutor(6) as ex:
    for i,(cid,rows,st) in enumerate(ex.map(fetch, sel.itertuples())):
        out[cid]={'rows':rows,'status':st}
        if i%25==0: print(i, round(time.time()-t0), st, len(rows or []), flush=True)
pickle.dump({'sel':sel,'tapes':out}, open(f'{S}/tapes.pkl','wb'))
print('done', time.time()-t0, sum(len(v['rows'] or []) for v in out.values()))
