"""H5: 'between-rounds' maker. Quote both sides at fair-delta only while the time since the last public-tape jump
(round-end proxy) is in [a,b] s (freeze/buy time), pull quotes otherwise. Backtest: FIT(80 older)->TEST(80 newer).
Match: likelihood-ratio score of time-since-jump bins fitted on FITm (first 40 maker-phase markets), evaluated on
TESTm (last 40) against a per-market circular time-shift null."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *; from makerbt import maker_bt_window, jump_times
tk,mk,pay,active,fit,test,split,event=load()
S=Series(tk)
sp=json.load(open(W+'/maker_phase_split.json')); fitm=set(sp['fitm']); testm=set(sp['testm'])
def summ(r):
    if r.get('fills',0)==0: return {'fills':0}
    s=cluster_t(r['_pm'],event); o={k:v for k,v in r.items() if not k.startswith('_')}; o.update(s); return o
fc,tc=sorted(fit),sorted(test)
scan=[]
for th in (0.03,0.05):
    for (a,b) in ((3,20),(3,30),(5,40),(10,30),(3,60),(30,120)):
        for d in (0.0,0.005,0.01,0.02):
            p=dict(theta_j=th,a=a,b=b,delta=d); r=summ(maker_bt_window(tk,pay,active,fc,L=2,**p)); scan.append((p,r))
ok=[(p,r) for p,r in scan if r.get('fills',0)>=100]
bp,br=max(ok,key=lambda x:x[1]['per_market_t'])
print('FIT best',bp,{k:br[k] for k in ('fills','usd','pnl','ret','per_market_t','per_market_p')})
print('FIT top5',[(p,round(r['ret'],4),round(r['per_market_p'],3)) for p,r in sorted(ok,key=lambda x:-x[1]['per_market_t'])[:5]])
res={'fit_scan':[{'params':p,**{k:v for k,v in r.items() if k in('fills','usd','pnl','ret','per_market_t','per_market_p')}} for p,r in scan],'chosen':bp,'test':{}}
for L in (0,2,5):
    for touch in (False,True):
        r=summ(maker_bt_window(tk,pay,active,tc,L=L,at_touch=touch,**bp)); res['test'][f'L{L}_{"touch" if touch else "strict"}']=r
        print('TEST',L,touch,{k:round(v,4) if isinstance(v,float) else v for k,v in r.items() if k in('fills','usd','pnl','ret','pairs','per_market_p','per_event_p','per_event_boot_p')})
# ---- match on maker-phase split
bins=np.array([0,5,10,20,30,45,60,90,120,180,300,600,1e9])
def tsj_scores(P,theta,shift=None,L=2):
    out=np.full(len(P),np.nan)
    for cid,idx in P.groupby('cid').indices.items():
        ts_all,p0_all,_,_=S.s[cid]; J=jump_times(ts_all,p0_all,theta)
        t=P.ts.to_numpy()[idx]-L
        if shift is not None:
            a,b=active[cid]; span=max(b-a,1); t=a+((t-a+shift[cid])%span)
        if len(J)==0: out[idx]=1e8; continue
        k=np.searchsorted(J,t,side='right')-1
        out[idx]=np.where(k>=0,t-J[np.clip(k,0,None)],1e8)
    return out
PF=mk[(mk.side=='BUY')&(mk.cid.isin(fitm))].reset_index(drop=True); yF=(PF.wallet==WALLET).to_numpy()
PT=mk[(mk.side=='BUY')&(mk.cid.isin(testm))].reset_index(drop=True); yT=(PT.wallet==WALLET).to_numpy()
best=None
for th in (0.03,0.05,0.08):
    x=tsj_scores(PF,th); b=np.digitize(x,bins)-1
    cw=np.bincount(b[yF],minlength=len(bins))+1; co=np.bincount(b[~yF],minlength=len(bins))+1
    lr=np.log((cw/cw.sum())/(co/co.sum()))
    a_fit=auc(lr[b],yF)
    print('FITm theta',th,'in-sample AUC',round(a_fit,4))
    if best is None or a_fit>best[0]: best=(a_fit,th,lr)
_,th,lr=best
def sc(P,shift=None): x=tsj_scores(P,th,shift); return lr[np.digitize(x,bins)-1]
obs=auc(sc(PT),yT)
rng=np.random.default_rng(3); null=[]
for i in range(300):
    sh={c:int(rng.integers(300,max(301,active[c][1]-active[c][0]-300))) for c in testm}
    null.append(auc(sc(PT,sh),yT))
null=np.array(null)
res['match']={'theta':th,'lr_by_bin':lr.tolist(),'bins':bins.tolist(),'test_auc':float(obs),'null_mean':float(null.mean()),'null_p99':float(np.percentile(null,99)),'perm_p':float((1+np.sum(null>=obs))/(1+len(null))),'n_wallet':int(yT.sum()),'n_pop':int(len(yT))}
print('MATCH TESTm',res['match'])
json.dump(res,open(W+'/h5_window_maker.json','w'),indent=1,default=float)
