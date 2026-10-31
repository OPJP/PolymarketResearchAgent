"""H1: tape-momentum taker. Buy outcome X at observed taker BUY prints of X when X's last-print price rose
by >= theta over the Delta seconds ending at ts-L (only prints with ts <= ts-L are used). theta<0 = fade (reversal) variant.
FIT chooses (Delta, theta) at L=2; TEST is evaluated at L in {1,2,5,10}. Wallet's own prints are not purchasable."""
import json, numpy as np, pandas as pd, sys
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *
tk,mk,pay,active,fit,test,split,event=load()
S=Series(tk)
buys=tk[tk.side=='BUY'].copy()
buys['pay']=np.where(buys.outcome==0,buys.cid.map(pay),1-buys.cid.map(pay))
def signal(df,L,D,shift=None):
    out=np.full(len(df),np.nan)
    for cid,idx in df.groupby('cid').indices.items():
        g=df.iloc[idx]; t=g.ts.to_numpy()-L
        if shift is not None:
            a,b=active[cid]; span=max(b-a,1); t=a+((t-a+shift[cid])%span)
        p_now=S.p0(cid,t); p_prev=S.p0(cid,t-D)
        m0=p_now-p_prev
        out[idx]=np.where(g.outcome.to_numpy()==0,m0,-m0)
    return out
def bt(df,L,D,theta,cap=50.0):
    df=df[df.wallet!=WALLET]
    m=signal(df,L,D)
    sel=df[(m>=theta) if theta>0 else (m<=theta)].copy()
    if sel.empty: return {'trades':0}
    usd=np.minimum(sel['size']*sel.price,cap); sh=usd/sel.price
    fee=sh*FEE_RATE*sel.price*(1-sel.price)
    sel['pnl']=sh*(sel.pay-sel.price)-fee; sel['usd']=usd
    pm=sel.groupby('cid').pnl.sum()
    r={'trades':int(len(sel)),'usd':float(usd.sum()),'pnl':float(sel.pnl.sum()),'ret':float(sel.pnl.sum()/usd.sum()),'fees':float(fee.sum())}
    r.update(cluster_t(pm,event)); return r
res={'split_ts':split,'fit_markets':len(fit),'test_markets':len(test)}
F_b=buys[buys.cid.isin(fit)]; T_b=buys[buys.cid.isin(test)]
scan={}
for D in [5,10,30,60]:
    for th in [0.02,0.04,0.06,0.10,-0.04,-0.06,-0.10]:
        r=bt(F_b,2,D,th); scan[f'D{D}_th{th}']=r
        print('FIT',D,th,{k:(round(v,4) if isinstance(v,float) else v) for k,v in r.items() if k in('trades','usd','pnl','ret','per_market_t','per_event_p')})
best=max(scan,key=lambda k:(scan[k].get('per_market_t') or -1e9) if scan[k].get('trades',0)>=30 else -1e9)
D=int(best.split('_')[0][1:]); th=float(best.split('th')[1])
print('chosen',best)
res['fit_scan']=scan; res['chosen']={'Delta':D,'theta':th}
res['test_by_latency']={}
for L in [1,2,5,10]:
    r=bt(T_b,L,D,th); res['test_by_latency'][L]=r; print('TEST L',L,{k:(round(v,4) if isinstance(v,float) else v) for k,v in r.items()})
# match test on TEST: population all taker BUY prints, label wallet, score = momentum at chosen D, L=2 (sign as chosen)
sgn=1 if th>0 else -1
y=(T_b.wallet==WALLET).to_numpy()
sc=sgn*signal(T_b,2,D)
obs=auc(sc,y)
rng=np.random.default_rng(0); null=[]
for i in range(300):
    sh={c:int(rng.integers(300,max(301,active[c][1]-active[c][0]-300))) for c in test}
    null.append(auc(sgn*signal(T_b,2,D,shift=sh),y))
null=np.array(null)
res['match_test']={'auc':obs,'null_mean':float(np.nanmean(null)),'null_p95':float(np.nanpercentile(null,95)),'perm_p':float((1+np.sum(null>=obs))/(1+np.sum(np.isfinite(null)))),'n_wallet':int(y.sum()),'n_pop':int(len(y))}
# also the wallet's own taker buys scored: precision at threshold
fire=(sc>=abs(th))
res['match_test'].update({'wallet_fire_rate':float(fire[y].mean()),'others_fire_rate':float(fire[~y].mean())})
print('MATCH',res['match_test'])
# wallet's own taker buys in TEST (original strategy) for comparison, same cap convention w/o cap
wb=T_b[T_b.wallet==WALLET]
fee=wb['size']*FEE_RATE*wb.price*(1-wb.price); pnl=wb['size']*(wb.pay-wb.price)-fee
pmw=pnl.groupby(wb.cid).sum(); r=cluster_t(pmw,event); r.update({'trades':int(len(wb)),'usd':float((wb['size']*wb.price).sum()),'pnl':float(pnl.sum())})
res['wallet_taker_buys_test']=r; print('WALLET taker buys TEST',r)
json.dump(res,open(W+'/h1_momentum_taker.json','w'),indent=1,default=float)
