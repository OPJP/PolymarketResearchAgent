"""Shared helpers for the challenge tests (public tape only; resolution for settlement only)."""
import pickle, numpy as np, pandas as pd
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
WALLET='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
FEE_RATE=0.05

def load():
    F=pickle.load(open(W+'/frames160.pkl','rb'))
    tk=F['tk'].sort_values(['cid','ts'],kind='stable').reset_index(drop=True)
    mk=F['mk'].sort_values(['cid','ts'],kind='stable').reset_index(drop=True)
    tk['p0']=np.where(tk.outcome==0,tk.price,1-tk.price)
    tk['dir0']=np.where(((tk.outcome==0)&(tk.side=='BUY'))|((tk.outcome==1)&(tk.side=='SELL')),1,-1)
    tk['usd']=tk['size']*tk.price
    active=F['active']; cids=F['cids']
    split=int(np.median([active[c][0] for c in cids]))
    fit={c for c in cids if active[c][0]<split}; test={c for c in cids if active[c][0]>=split}
    meta=F['meta']
    event={c:str(meta.loc[c,'slug']).rsplit('-game',1)[0] if '-game' in str(meta.loc[c,'slug']) else str(meta.loc[c,'slug']) for c in cids}
    return tk,mk,F['payouts'],active,fit,test,split,event

class Series:
    """Per-market last-print implied price of outcome 0, queried strictly at or before t (PIT)."""
    def __init__(self,tk):
        self.s={cid:(g.ts.to_numpy(),g.p0.to_numpy(),g.dir0.to_numpy(),g.usd.to_numpy()) for cid,g in tk.groupby('cid')}
    def p0(self,cid,t):
        ts,p,_,_=self.s[cid]; k=np.searchsorted(ts,t,side='right')-1
        out=np.where(k>=0,p[np.clip(k,0,None)],np.nan); return out
    def flow0(self,cid,a,b):
        ts,_,d,u=self.s[cid]; c=np.concatenate([[0],np.cumsum(d*u)])
        lo=np.searchsorted(ts,a,side='right'); hi=np.searchsorted(ts,b,side='right')
        return c[hi]-c[lo]

def auc(score,y):
    from scipy.stats import rankdata
    m=np.isfinite(score); s=score[m]; yy=y[m].astype(bool)
    n1=yy.sum(); n0=(~yy).sum()
    if n1==0 or n0==0: return np.nan
    r=rankdata(s); return (r[yy].sum()-n1*(n1+1)/2)/(n1*n0)

def cluster_t(pnl_by_market, event):
    """HAC t over markets plus a t over events (map/match markets of one match clustered)."""
    from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue
    s=pd.Series(pnl_by_market)
    t1=hac_t_test(s.to_numpy())
    e=s.groupby(s.index.map(event)).sum()
    t2=hac_t_test(e.to_numpy())
    b=stationary_bootstrap_pvalue(e.to_numpy(),n_boot=2000) if len(e)>=5 else None
    return {'markets':int(len(s)),'events':int(len(e)),'per_market_t':t1.statistic,'per_market_p':t1.p_value,'per_event_t':t2.statistic,'per_event_p':t2.p_value,'per_event_boot_p':(b.p_value if b else None)}
