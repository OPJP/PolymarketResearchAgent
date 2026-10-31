"""H2 WP-REACT: react to ANY play that moves ESPN's public win probability (turnovers, big gains,
fouls, scoring), not only scoring plays. Within W s after a play with |dWP| >= Delta becomes known
(wallclock + D), buy the team outcome (moneyline or spread) the play favoured.
FIT picks (D>=0, W, Delta) maximizing wallet-minus-others share of reactive+agreeing buys.
TEST: reactive share, direction agreement, AUC of score, each vs a play-timeline shift null
(+-300..1500 s per game, 200 perms); backtest buys every favoured BUY print in the window
(cap $100, market fee), per-game HAC t + bootstrap; latency degradation D+5..60."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue, permutation_pvalue
G,P,M,split=load()
B=P[(P.side=='BUY')&P.side_kind.isin(['home','away'])].copy().reset_index(drop=True)
# WP events per game
EV={}
for _,g in G.iterrows():
    pl=[(p[0],p[4]) for p in g.plays if p[4] is not None]
    if len(pl)<5: continue
    a=np.array(pl,float); o=np.argsort(a[:,0],kind='stable'); a=a[o]
    d=np.diff(a[:,1],prepend=a[0,1])
    EV[g.event_slug]=(a[:,0],d)
B=B[B.event_slug.isin(EV.keys())].reset_index(drop=True)
print('games with WP',len(EV),'team-side BUY prints',len(B),'wallet',B.is_wallet.sum())
sgn=np.where(B.side_kind.to_numpy()=='home',1.0,-1.0)
groups=B.groupby('event_slug').indices
def annotate(D,Delta,shift=None):
    since=np.full(len(B),np.nan); dwp=np.zeros(len(B))
    for ev,idx in groups.items():
        ts,d=EV[ev]; m=np.abs(d)>=Delta
        if not m.any(): continue
        kt=ts[m]+D+(shift or {}).get(ev,0); dd=d[m]
        o=np.argsort(kt); kt=kt[o]; dd=dd[o]
        t=B.ts.to_numpy()[idx]
        i=np.searchsorted(kt,t,side='right')-1; h=i>=0
        since[idx]=np.where(h,t-kt[np.clip(i,0,None)],np.nan)
        dwp[idx]=np.where(h,dd[np.clip(i,0,None)],0)
    return since, dwp*sgn
y=B.is_wallet.to_numpy(); fit=B.fit.to_numpy(); test=~fit
def stats_(since,fdwp,W,mask):
    r=(since>=0)&(since<=W)
    out={}
    for who,mm in (('wallet',mask&y),('others',mask&~y)):
        rr=r[mm]; ag=fdwp[mm][rr]
        out[f'{who}_share_reactive']=float(rr.mean()); out[f'{who}_agree']=float((ag>0).mean()) if len(ag) else np.nan
        out[f'{who}_n_reactive']=int(rr.sum()); out[f'{who}_share_reactive_agree']=float((rr&(fdwp[mm]>0)).mean())
    out['excess']=out['wallet_share_reactive_agree']-out['others_share_reactive_agree']
    return out
scan=[]
for D in (0,5,10,20,30):
    for Delta in (0.02,0.05,0.1):
        s,f=annotate(D,Delta)
        for W in (10,20,30,60):
            scan.append({'D':D,'Delta':Delta,'W':W,**stats_(s,f,W,fit)})
scan=pd.DataFrame(scan).sort_values('excess',ascending=False)
print(scan.head(8)[['D','Delta','W','wallet_share_reactive','others_share_reactive','wallet_agree','others_agree','excess']].round(3).to_string())
best=scan.iloc[0]; D,Delta,W=int(best.D),float(best.Delta),int(best.W)
out={'fit_choice':{'D':D,'Delta':Delta,'W':W},'fit_scan_top':scan.head(5).to_dict('records')}
s,f=annotate(D,Delta)
obs=stats_(s,f,W,test); out['test']=obs
score=np.where((s>=0)&(s<=W),f,0.0)
out['test_auc']=float(auc(y[test],score[test]))
rng=np.random.default_rng(11); nul=[]
evs=list(groups.keys())
for i in range(200):
    sh={e:int(rng.integers(300,1500))*int(rng.choice([-1,1])) for e in evs}
    s2,f2=annotate(D,Delta,sh); st=stats_(s2,f2,W,test)
    sc=np.where((s2>=0)&(s2<=W),f2,0.0)
    nul.append((st['excess'],st['wallet_agree'],auc(y[test],sc[test])))
nul=np.array(nul)
out['null']={'excess_p95':float(np.nanpercentile(nul[:,0],95)),'agree_p95':float(np.nanpercentile(nul[:,1],95)),'auc_p95':float(np.nanpercentile(nul[:,2],95)),
  'excess_perm_p':permutation_pvalue(obs['excess'],nul[:,0][np.isfinite(nul[:,0])]),'agree_perm_p':permutation_pvalue(obs['wallet_agree'],nul[:,1][np.isfinite(nul[:,1])]),
  'auc_perm_p':permutation_pvalue(out['test_auc'],nul[:,2][np.isfinite(nul[:,2])])}
def bt(mask):
    x=B[mask & B.payout.notna().to_numpy()]
    if len(x)<10: return {'trades':int(len(x))}
    pnl,usd=settle(x); x=x.assign(pnl=pnl); pg=x.groupby('event_slug').pnl.sum()
    t=hac_t_test(pg.to_numpy()); bp=stationary_bootstrap_pvalue(pg.to_numpy(),n_boot=2000).p_value
    return {'trades':int(len(x)),'games':int(len(pg)),'usd':float(usd.sum()),'pnl':float(pnl.sum()),'ret':float(pnl.sum()/usd.sum()),'t':float(t.statistic),'p':float(t.p_value),'boot_p':float(bp)}
out['backtest_test']=bt(test&(s>=0)&(s<=W)&(f>0))
out['backtest_test_excl_wallet']=bt(test&(s>=0)&(s<=W)&(f>0)&~y)
lat={}
for extra in (5,10,20,30,60):
    s3,f3=annotate(D+extra,Delta); lat[str(D+extra)]=bt(test&(s3>=0)&(s3<=W)&(f3>0))
out['latency']=lat
# FIT backtest for reference
out['backtest_fit']=bt(fit&(s>=0)&(s<=W)&(f>0))
print(json.dumps(out,indent=1,default=float))
json.dump(out,open(BASE+'h2_wpreact.json','w'),indent=1,default=float)
