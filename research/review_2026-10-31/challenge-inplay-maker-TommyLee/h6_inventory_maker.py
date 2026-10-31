"""H6: inventory-balancing two-sided maker (targets the maker-phase mechanism: locked pair spread).
Every R s: fair = last public print at t0-L; bid_o = fair_o - delta - k*max(0, inv_o - inv_other)/S (widen the side
already held, keep the other tight); stop bidding a side once its unmatched inventory exceeds cap shares.
Strict trade-through fills from later taker prints in (t0, t0+R]; settle at resolution. FIT picks (delta,k,cap) at L=2."""
import sys, json, math, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *
tk,mk,pay,active,fit,test,split,event=load()
G={cid:g for cid,g in tk.groupby('cid')}
def run(cids,delta,k,cap,L=2,R=5,size=20.0,tick=0.001,touch=False):
    per={}; tot_usd=0; tot_pnl=0; pairs=0; fills=0
    for cid in cids:
        g=G[cid]; ts=g.ts.to_numpy(); p0=g.p0.to_numpy(); oc=g.outcome.to_numpy(); sd=g.side.to_numpy(); pr=g.price.to_numpy(); sz=g['size'].to_numpy()
        a,b=active[cid]; inv=[0.0,0.0]; cost=[0.0,0.0]
        for t0 in range(a,b,R):
            kk=np.searchsorted(ts,t0-L,side='right')-1
            if kk<0: continue
            lo=np.searchsorted(ts,t0,side='right'); hi=np.searchsorted(ts,t0+R,side='right')
            if hi<=lo: continue
            f0=p0[kk]
            for o in (0,1):
                fair=f0 if o==0 else 1-f0
                excess=max(0.0,inv[o]-inv[1-o])
                if excess>=cap: continue
                q=math.floor((fair-delta-k*excess/size)/tick+1e-9)*tick
                if q<tick or q>1-tick: continue
                s=slice(lo,hi)
                if touch: m=((oc[s]==o)&(sd[s]=='SELL')&(pr[s]<=q+1e-9))|((oc[s]!=o)&(sd[s]=='BUY')&(pr[s]>=1-q-1e-9))
                else: m=((oc[s]==o)&(sd[s]=='SELL')&(pr[s]<q-1e-9))|((oc[s]!=o)&(sd[s]=='BUY')&(pr[s]>1-q+1e-9))
                f=min(size,float(sz[s][m].sum()))
                if f<=0: continue
                inv[o]+=f; cost[o]+=f*q; fills+=1
        po=pay[cid]; pnl=inv[0]*po+inv[1]*(1-po)-cost[0]-cost[1]
        if inv[0]+inv[1]>0:
            per[cid]=pnl; tot_usd+=cost[0]+cost[1]; tot_pnl+=pnl; pairs+=min(inv)
    r={'fills':fills,'usd':tot_usd,'pnl':tot_pnl,'ret':tot_pnl/tot_usd if tot_usd else None,'pairs':pairs}
    if len(per)>=5: r.update(cluster_t(per,event))
    return r
fc,tc=sorted(fit),sorted(test)
scan=[]
for d in (0.0,0.005,0.01,0.02):
    for k in (0.0,0.005,0.02):
        for cap in (40,100,1e9):
            p=dict(delta=d,k=k,cap=cap); r=run(fc,**p); scan.append((p,r))
            print('FIT',p,{kk:round(v,4) if isinstance(v,float) else v for kk,v in r.items() if kk in('fills','usd','pnl','ret','per_market_p')},flush=True)
ok=[(p,r) for p,r in scan if r['fills']>=100]
bp,br=max(ok,key=lambda x:x[1].get('per_market_t',-1e9))
print('chosen',bp)
res={'fit_scan':[{'params':p,**r} for p,r in scan],'chosen':bp,'test':{}}
for L in (0,2,5):
    for touch in (False,True):
        r=run(tc,L=L,touch=touch,**bp); res['test'][f'L{L}_{"touch" if touch else "strict"}']=r
        print('TEST',L,touch,{kk:round(v,4) if isinstance(v,float) else v for kk,v in r.items()},flush=True)
json.dump(res,open(W+'/h6_inventory_maker.json','w'),indent=1,default=float)
