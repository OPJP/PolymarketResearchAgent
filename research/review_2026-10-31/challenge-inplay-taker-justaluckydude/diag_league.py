"""Post-hoc diagnostics (not used for any pass/fail): H2 and H3 TEST backtests split by league, H2 coverage of all wallet buys."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *
from polyrea.stats.significance import hac_t_test
G,P,M,split=load()
WP={}
for _,g in G.iterrows():
    pl=[(p[0],p[4]) for p in g.plays if p[4] is not None]
    if len(pl)>=5:
        a=np.array(pl,float); a=a[np.argsort(a[:,0],kind='stable')]; WP[g.event_slug]=a
B=P[(P.side=='BUY')&P.side_kind.isin(['home','away'])&P.event_slug.isin(WP.keys())].copy().reset_index(drop=True)
sgn=np.where(B.side_kind=='home',1.0,-1.0)
since=np.full(len(B),np.nan); fav=np.zeros(len(B)); wps=np.full(len(B),np.nan)
for ev,idx in B.groupby('event_slug').indices.items():
    a=WP[ev]; d=np.diff(a[:,1],prepend=a[0,1]); m=np.abs(d)>=0.02
    kt=a[m,0]; dd=d[m]; t=B.ts.to_numpy()[idx]
    i=np.searchsorted(kt,t,side='right')-1; h=i>=0
    since[idx]=np.where(h,t-kt[np.clip(i,0,None)],np.nan); fav[idx]=np.where(h,dd[np.clip(i,0,None)],0)*sgn[idx]
    j=np.searchsorted(a[:,0]+5,t,side='right')-1
    w=np.where(j>=0,a[np.clip(j,0,None),1],np.nan); wps[idx]=np.where(B.side_kind.to_numpy()[idx]=='home',w,1-w)
B['react']=(since>=0)&(since<=30)&(fav>0); B['wpval']=(wps-B.price)>=0.10
T=B[~B.fit&B.payout.notna()].copy(); pnl,usd=settle(T); T['pnl']=pnl; T['cusd']=usd
for name,mask in (('H2 WP-REACT D0 W30',T.react),('H3 WP-VALUE D5 th0.10 (ML only)',T.wpval&(T.mtype=='moneyline'))):
    x=T[mask]
    for lg,g in x.groupby('league'):
        pg=g.groupby('event_slug').pnl.sum()
        print(name,lg,'trades',len(g),'ret',round(g.pnl.sum()/g.cusd.sum(),4),'games',len(pg),'p',round(hac_t_test(pg.to_numpy()).p_value,3) if len(pg)>=5 else None)
allw=P[P.is_wallet&(P.side=='BUY')]
tw=allw[~allw.fit]
cov=B[~B.fit&B.is_wallet].react.sum()/len(tw)
print('H2 reactive+agreeing wallet buys / ALL wallet buys on TEST games:',round(cov,3),' (team-side WP prints / all:',round(len(B[~B.fit&B.is_wallet])/len(tw),3),')')
