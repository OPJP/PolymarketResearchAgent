"""H4: post-jump re-quoting maker ("provide liquidity into the overreaction"): bid only on the outcome whose
last-print price FELL by >= theta over D s ending at t0-L, at fair-delta (fair = newest public print).
Match: score = -momentum of bought outcome; direction and D chosen on FIT by AUC, evaluated on TEST with
time-shift null. Backtest: FIT picks (D, theta, delta) at L=2; TEST at L in {0,2,5,10}, strict and at-touch."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *; from makerbt import maker_bt
tk,mk,pay,active,fit,test,split,event=load()
S=Series(tk)
def pop(cset):
    P=mk[(mk.side=='BUY')&(mk.cid.isin(cset))].reset_index(drop=True); return P,(P.wallet==WALLET).to_numpy()
def score(P,D,L=2,shift=None):
    out=np.full(len(P),np.nan)
    for cid,idx in P.groupby('cid').indices.items():
        g=P.iloc[idx]; t=g.ts.to_numpy()-L
        if shift is not None:
            a,b=active[cid]; span=max(b-a,1); t=a+((t-a+shift[cid])%span)
        v0=S.p0(cid,t)-S.p0(cid,t-D)
        out[idx]=np.where(g.outcome.to_numpy()==0,-v0,v0)   # positive = bought outcome fell
    return out
res={}
PF,yF=pop(fit); fa={D:auc(score(PF,D),yF) for D in (10,30,60,120)}
print('FIT AUC by D',fa); Dm=max(fa,key=fa.get); res['match_fit_auc']=fa; res['match_D']=Dm
PT,yT=pop(test); obs=auc(score(PT,Dm),yT)
rng=np.random.default_rng(2); null=[]
for i in range(300):
    sh={c:int(rng.integers(300,max(301,active[c][1]-active[c][0]-300))) for c in test}
    null.append(auc(score(PT,Dm,shift=sh),yT))
null=np.array(null)
res['match_test']={'auc':float(obs),'null_mean':float(null.mean()),'null_p99':float(np.percentile(null,99)),'perm_p':float((1+np.sum(null>=obs))/(1+len(null))),'n_wallet':int(yT.sum()),'n_pop':int(len(yT))}
print('TEST match',res['match_test'])
def summ(r):
    if r.get('fills',0)==0: return {'fills':0}
    s=cluster_t(r['_pm'],event); o={k:v for k,v in r.items() if not k.startswith('_')}; o.update(s); return o
fc,tc=sorted(fit),sorted(test)
scan=[]
for D in (10,30,60):
    for th in (0.02,0.05,0.10):
        for d in (0.0,0.005,0.01,0.02,0.05):
            p=dict(side_rule='antimom',D=D,theta=th,delta=d); r=summ(maker_bt(tk,pay,active,fc,L=2,tick=0.001,**p)); scan.append((p,r))
ok=[(p,r) for p,r in scan if r.get('fills',0)>=100]
bp,br=max(ok,key=lambda x:x[1]['per_market_t'])
print('FIT best',bp,{k:br[k] for k in ('fills','usd','pnl','ret','per_market_t','per_market_p')})
print('FIT p<0.05:',[(p,round(r['per_market_p'],3)) for p,r in ok if r['per_market_p']<0.05])
tst={}
for L in (0,2,5,10):
    for touch in (False,True):
        r=summ(maker_bt(tk,pay,active,tc,L=L,tick=0.001,at_touch=touch,**bp)); tst[f'L{L}_{"touch" if touch else "strict"}']=r
        print('TEST',L,touch,{k:round(v,4) if isinstance(v,float) else v for k,v in r.items() if k in('fills','usd','pnl','ret','per_market_p','per_event_p','per_event_boot_p')})
res.update({'fit_scan':[{'params':p,**{k:v for k,v in r.items() if k in('fills','usd','pnl','ret','per_market_t','per_market_p')}} for p,r in scan],'chosen':bp,'test':tst})
json.dump(res,open(W+'/h4_postjump.json','w'),indent=1,default=float)
