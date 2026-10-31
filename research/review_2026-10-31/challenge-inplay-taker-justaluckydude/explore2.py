import sys, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *
B=pd.read_pickle(BASE+'buys_feats2_L1.pkl')
B=B[B.payout.notna()].copy()
B['fee']=fee(B.price,B['size'],B.fee_rate); B['pnl']=B['size']*B.payout-B.usd-B.fee
def tab(x,by):
    return x.groupby(by,observed=True).apply(lambda g: pd.Series({'n':len(g),'usd':round(g.usd.sum()),'ret':round(g.pnl.sum()/g.usd.sum(),4)}))
F=B[B.fit]
w=F[F.is_wallet]; o=F[~F.is_wallet]
bins=[-1,0.5,5,30,120,600,1e9]
print('FIT wallet by own_stale'); print(tab(w,pd.cut(w.own_stale,bins)))
print('FIT others by own_stale'); print(tab(o,pd.cut(o.own_stale,bins)))
for col in ('gap_sib','gap_ml','espn_net_since_last'):
    lab=lambda x: np.select([x>0.0001,x<-0.0001],['fav','against'],'zero/nan')
    print('FIT wallet by sign of',col); print(tab(w,lab(w[col])))
    print('FIT others by sign of',col); print(tab(o,lab(o[col])))
print('FIT wallet by mtype'); print(tab(w,w.mtype))
print('FIT wallet by league'); print(tab(w,w.league))
T=B[~B.fit]; wt=T[T.is_wallet]
print('TEST wallet by mtype'); print(tab(wt,wt.mtype))
print('TEST wallet by league'); print(tab(wt,wt.league))
