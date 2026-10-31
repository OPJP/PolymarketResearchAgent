"""Shared loaders and point-in-time feature builders for the challenge.

All features for a print at time t use only taker prints with ts <= t - L
(L >= 1 s, strictly earlier seconds) or ESPN plays with wallclock + D <= t.
Payout (resolution) is used only for settlement.
"""
import pickle, numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
BASE='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude/'

def load():
    D=pickle.load(open(BASE+'games200.pkl','rb'))
    G=pd.DataFrame(D['games']); P=D['prints'].copy()
    split=int(np.median(G.start)); G['fit']=G.start<split
    P=P.merge(G[['event_slug','fit','league','start']],on='event_slug')
    P['usd']=P.price*P['size']
    # implied price of token 0 from every taker print (BUY/SELL of either token)
    P['p0']=np.where(P.tok==0,P.price,1-P.price)
    P=P.sort_values(['condition_id','ts']).reset_index(drop=True)
    return G,P,D['markets'],split

class Tape:
    """Per-market last implied p0 known at or before a time (strictly earlier seconds via L)."""
    def __init__(self,P):
        self.m={}
        for cid,g in P.groupby('condition_id',sort=False):
            # aggregate to last print per second
            s=g.groupby('ts').p0.last()
            self.m[cid]=(s.index.to_numpy(np.int64), s.to_numpy(float))
    def at(self,cid,q):
        """p0 at the last second <= q (nan if none)."""
        ts,p=self.m.get(cid,(np.array([],np.int64),np.array([])))
        i=np.searchsorted(ts,q,side='right')-1
        out=np.where(i>=0,p[np.clip(i,0,None)] if len(p) else np.nan,np.nan)
        return out
    def last_ts(self,cid,q):
        ts,p=self.m.get(cid,(np.array([],np.int64),np.array([])))
        i=np.searchsorted(ts,q,side='right')-1
        return np.where(i>=0,ts[np.clip(i,0,None)] if len(ts) else -1,-1)

def fee(price,shares,rate):
    return rate*price*(1-price)*shares

def settle(sel,cap=100.0):
    usd=np.minimum(sel['usd'].to_numpy(),cap); pr=sel['price'].to_numpy()
    sh=usd/pr; f=fee(pr,sh,sel['fee_rate'].to_numpy())
    return sh*sel['payout'].to_numpy()-usd-f, usd

def auc(y,s):
    m=np.isfinite(s)
    return roc_auc_score(y[m],s[m]) if m.sum()>10 and len(set(y[m]))==2 else np.nan
