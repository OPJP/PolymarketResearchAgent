"""Decision-level match on TEST for the maker hypotheses. Population: every passive (maker) BUY on the public
tape of the TEST markets; label: the wallet's. Scores use only prints with ts <= fill_ts-2.
H2 score = fair of bought outcome (favourite-ness); H3 score = 30 s tape momentum of bought outcome.
Null: per-market circular shift of the score clock by 5 min .. span-5 min (300 draws)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *
tk,mk,pay,active,fit,test,split,event=load()
S=Series(tk)
P=mk[(mk.side=='BUY')&(mk.cid.isin(test))].reset_index(drop=True)
y=(P.wallet==WALLET).to_numpy()
def score(kind,L=2,D=30,shift=None):
    out=np.full(len(P),np.nan)
    for cid,idx in P.groupby('cid').indices.items():
        g=P.iloc[idx]; t=g.ts.to_numpy()-L
        if shift is not None:
            a,b=active[cid]; span=max(b-a,1); t=a+((t-a+shift[cid])%span)
        f0=S.p0(cid,t)
        if kind=='fav': v0=f0
        else: v0=f0-S.p0(cid,t-D)
        out[idx]=np.where(g.outcome.to_numpy()==0,v0,(1-v0) if kind=='fav' else -v0)
    return out
res={'n_pop':int(len(P)),'n_wallet':int(y.sum())}
rng=np.random.default_rng(1)
for kind in ('fav','mom'):
    obs=auc(score(kind),y)
    null=[]
    for i in range(300):
        sh={c:int(rng.integers(300,max(301,active[c][1]-active[c][0]-300))) for c in test}
        null.append(auc(score(kind,shift=sh),y))
    null=np.array(null)
    res[kind]={'auc':float(obs),'null_mean':float(np.nanmean(null)),'null_p99':float(np.nanpercentile(null,99)),'perm_p_high':float((1+np.sum(null>=obs))/(1+len(null))),'perm_p_low':float((1+np.sum(null<=obs))/(1+len(null)))}
    print(kind,res[kind])
# descriptive: wallet vs others maker buys price-level and distance to last print
f=score('fav'); res['desc']={'wallet_mean_fair':float(np.nanmean(f[y])),'others_mean_fair':float(np.nanmean(f[~y])),
 'wallet_mean_px_minus_fair':float(np.nanmean(P.price.to_numpy()[y]-f[y])),'others_mean_px_minus_fair':float(np.nanmean(P.price.to_numpy()[~y]-f[~y]))}
print(res['desc'])
json.dump(res,open(W+'/maker_match.json','w'),indent=1)
