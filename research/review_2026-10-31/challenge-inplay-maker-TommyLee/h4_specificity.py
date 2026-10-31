"""Is the H4 anti-momentum score specific to the wallet? Same score (60 s fall of the bought outcome, known at fill-2 s)
used to separate each of the 8 largest other makers' BUY fills from the rest, TEST markets.
Also the clean within-maker-phase check: D chosen on FITm (first 40 maker-phase markets), AUC on TESTm (last 40)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *
tk,mk,pay,active,fit,test,split,event=load(); S=Series(tk)
sp=json.load(open(W+'/maker_phase_split.json')); fitm=set(sp['fitm']); testm=set(sp['testm'])
def score(P,D,L=2,shift=None):
    out=np.full(len(P),np.nan)
    for cid,idx in P.groupby('cid').indices.items():
        g=P.iloc[idx]; t=g.ts.to_numpy()-L
        if shift is not None:
            a,b=active[cid]; span=max(b-a,1); t=a+((t-a+shift[cid])%span)
        v0=S.p0(cid,t)-S.p0(cid,t-D); out[idx]=np.where(g.outcome.to_numpy()==0,-v0,v0)
    return out
P=mk[(mk.side=='BUY')&(mk.cid.isin(test))].reset_index(drop=True); s=score(P,60)
top=P[P.wallet!=WALLET].groupby('wallet').size().sort_values(ascending=False).head(8)
res={'wallet_auc':auc(s,(P.wallet==WALLET).to_numpy()),'others':{}}
for wl,n in top.items(): res['others'][wl]={'n':int(n),'auc':float(auc(s,(P.wallet==wl).to_numpy()))}
print(json.dumps(res,indent=1))
PF=mk[(mk.side=='BUY')&(mk.cid.isin(fitm))].reset_index(drop=True); yF=(PF.wallet==WALLET).to_numpy()
fa={D:float(auc(score(PF,D),yF)) for D in (10,30,60,120)}; Dm=max(fa,key=fa.get)
PT=mk[(mk.side=='BUY')&(mk.cid.isin(testm))].reset_index(drop=True); yT=(PT.wallet==WALLET).to_numpy()
obs=auc(score(PT,Dm),yT); rng=np.random.default_rng(4); null=[]
for i in range(300):
    sh={c:int(rng.integers(300,max(301,active[c][1]-active[c][0]-300))) for c in testm}; null.append(auc(score(PT,Dm,shift=sh),yT))
null=np.array(null)
res['clean_split']={'fitm_auc_by_D':fa,'D':Dm,'testm_auc':float(obs),'null_mean':float(null.mean()),'null_p99':float(np.percentile(null,99)),'perm_p':float((1+np.sum(null>=obs))/(1+len(null))),'n_wallet':int(yT.sum())}
print(res['clean_split'])
json.dump(res,open(W+'/h4_specificity.json','w'),indent=1)
