"""H3 WP-VALUE: buy the moneyline side whose ESPN win probability (latest play known at wallclock + D)
exceeds the taker's price by >= theta. A value (not speed) rule: if ESPN's model leads Polymarket,
it should survive realistic API delays. FIT picks (D, theta) by max per-game t of the backtest
(>=300 trades); TEST: AUC wallet vs others (null: play-timeline shift, 200 perms) and backtest."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue, permutation_pvalue
G,P,M,split=load()
B=P[(P.side=='BUY')&(P.mtype=='moneyline')&P.side_kind.isin(['home','away'])].copy().reset_index(drop=True)
WP={}
for _,g in G.iterrows():
    pl=[(p[0],p[4]) for p in g.plays if p[4] is not None]
    if len(pl)>=5:
        a=np.array(pl,float); a=a[np.argsort(a[:,0],kind='stable')]; WP[g.event_slug]=a
B=B[B.event_slug.isin(WP.keys())].reset_index(drop=True)
y=B.is_wallet.to_numpy(); fit=B.fit.to_numpy(); test=~fit
print('ML prints',len(B),'wallet',y.sum(),'fit games',B[fit].event_slug.nunique(),'test games',B[test].event_slug.nunique())
groups=B.groupby('event_slug').indices
home=(B.side_kind=='home').to_numpy()
def wp_side(D,shift=None):
    out=np.full(len(B),np.nan)
    for ev,idx in groups.items():
        a=WP[ev]; kt=a[:,0]+D+(shift or {}).get(ev,0)
        i=np.searchsorted(kt,B.ts.to_numpy()[idx],side='right')-1
        w=np.where(i>=0,a[np.clip(i,0,None),1],np.nan)
        out[idx]=np.where(home[idx],w,1-w)
    return out
def bt(mask):
    x=B[mask & B.payout.notna().to_numpy()]
    if len(x)<10: return {'trades':int(len(x))}
    pnl,usd=settle(x); x=x.assign(pnl=pnl); pg=x.groupby('event_slug').pnl.sum()
    t=hac_t_test(pg.to_numpy()); bp=stationary_bootstrap_pvalue(pg.to_numpy(),n_boot=2000).p_value if len(pg)>=5 else None
    return {'trades':int(len(x)),'games':int(len(pg)),'usd':float(usd.sum()),'pnl':float(pnl.sum()),'ret':float(pnl.sum()/usd.sum()),'t':float(t.statistic),'p':float(t.p_value),'boot_p':bp}
scan=[]
for D in (5,10,20,30,60):
    s=wp_side(D)-B.price.to_numpy()
    for th in (0.0,0.03,0.05,0.1,0.15):
        r=bt(fit&(s>=th)); 
        if r['trades']>=300: scan.append({'D':D,'theta':th,**r,'fit_auc':auc(y[fit],s[fit])})
scan=pd.DataFrame(scan).sort_values('t',ascending=False)
print(scan[['D','theta','trades','games','ret','t','p','fit_auc']].round(3).to_string())
best=scan.iloc[0]; D,TH=int(best.D),float(best.theta)
s=wp_side(D)-B.price.to_numpy()
out={'fit_choice':{'D':D,'theta':TH},'fit_scan':scan.head(6).to_dict('records'),'test_auc':float(auc(y[test],s[test]))}
rng=np.random.default_rng(3); nul=[]
for i in range(200):
    sh={e:int(rng.integers(300,1500))*int(rng.choice([-1,1])) for e in groups}
    s2=wp_side(D,sh)-B.price.to_numpy(); nul.append(auc(y[test],s2[test]))
nul=np.array(nul); out['auc_null_p95']=float(np.nanpercentile(nul,95)); out['auc_perm_p']=permutation_pvalue(out['test_auc'],nul[np.isfinite(nul)])
out['wallet_share_flagged']=float((s[test&y]>=TH).mean()); out['others_share_flagged']=float((s[test&~y]>=TH).mean())
out['backtest_test']=bt(test&(s>=TH)); out['backtest_test_excl_wallet']=bt(test&(s>=TH)&~y)
out['latency']={str(D+e):bt(test&((wp_side(D+e)-B.price.to_numpy())>=TH)) for e in (10,30,60)}
print(json.dumps(out,indent=1,default=float))
json.dump(out,open(BASE+'h3_wpvalue.json','w'),indent=1,default=float)
