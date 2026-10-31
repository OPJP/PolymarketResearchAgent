"""H5 exploration on FITm only (first 40 maker-phase markets by start): time since last tape jump at maker BUY fills,
wallet vs other makers. Jump at print time t: |p0(t)-p0(t-10)|>=theta (prints <= t only); de-duplicated 20 s."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *
tk,mk,pay,active,fit,test,split,event=load()
S=Series(tk)
tsorted=sorted(test,key=lambda c:active[c][0]); fitm=set(tsorted[:40]); testm=set(tsorted[40:])
json.dump({'fitm':sorted(fitm),'testm':sorted(testm),'split_m':active[tsorted[40]][0]},open(W+'/maker_phase_split.json','w'))
def jumps(cid,theta,win=10,dedup=20):
    ts,p,_,_=S.s[cid]
    prev=S.p0(cid,ts-win)
    j=ts[np.abs(p-prev)>=theta]
    out=[];last=-1e18
    for t in j:
        if t-last>dedup: out.append(t)
        last=t
    return np.array(out)
P=mk[(mk.side=='BUY')&(mk.cid.isin(fitm))].reset_index(drop=True)
y=(P.wallet==WALLET).to_numpy()
for theta in (0.03,0.05,0.08):
    tsj=np.full(len(P),np.nan)
    for cid,idx in P.groupby('cid').indices.items():
        J=jumps(cid,theta); t=P.ts.to_numpy()[idx]-2
        k=np.searchsorted(J,t,side='right')-1
        tsj[idx]=np.where(k>=0,t-J[np.clip(k,0,None)],np.nan)
    bins=[0,5,10,20,30,45,60,90,120,180,300,600,1e9]
    h=pd.DataFrame({'b':pd.cut(tsj,bins),'w':y,'usd':P['size']*P.price})
    tab=h.groupby(['b','w'],observed=False).usd.sum().unstack(fill_value=0)
    tab=tab/tab.sum()
    tab.columns=['others','wallet']; tab['ratio']=tab.wallet/tab.others
    print('theta',theta,'n jumps/market', np.mean([len(jumps(c,theta)) for c in fitm]))
    print(tab.round(3).to_string())
