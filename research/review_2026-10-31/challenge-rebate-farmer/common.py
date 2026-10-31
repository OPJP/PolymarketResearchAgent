import sys
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.analysis.updown import auc
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue, permutation_pvalue

def circular_shift_null(df, score, n_perm=200, seed=0, min_frac=0.15):
    """Null for 'score predicts which prints are the wallet's': within each window, the wallet's
    print times are shifted circularly by one random offset (>= min_frac of the window span), and the
    labels move to the nearest population prints at the shifted times. Keeps the number, clustering and
    spacing of the wallet's decisions per window; destroys their alignment with market state."""
    rng=np.random.default_rng(seed)
    df=df.reset_index(drop=True)
    sc=np.asarray(score,dtype=float)
    groups=[]
    for cid,g in df.groupby('condition_id'):
        idx=g.index.to_numpy(); ts=g.ts.to_numpy().astype(float)
        o=np.argsort(ts,kind='stable'); idx=idx[o]; ts=ts[o]
        y=df.y.to_numpy()[idx]
        if y.sum()==0: continue
        s0=g.start_ts.iloc[0]; span=float(g.end_ts.iloc[0]-s0)
        groups.append((idx,ts,y,s0,span))
    out=[]
    for _ in range(n_perm):
        yy=np.zeros(len(df),dtype=int)
        for idx,ts,y,s0,span in groups:
            off=rng.uniform(min_frac*span,(1-min_frac)*span)
            wt=ts[y==1]
            new=s0+((wt-s0+off)%span)
            j=np.clip(np.searchsorted(ts,new),0,len(ts)-1)
            j2=np.clip(j-1,0,len(ts)-1)
            jj=np.where(np.abs(ts[j2]-new)<np.abs(ts[j]-new),j2,j)
            yy[idx[jj]]=1
        out.append(auc(sc,yy))
    return np.array([x for x in out if np.isfinite(x)])

def match_report(df, score, n_perm=200, seed=0):
    y=df.y.to_numpy()
    a=auc(np.asarray(score,dtype=float),y)
    null=circular_shift_null(df,score,n_perm,seed)
    return {'n':int(len(df)),'wallet':int(y.sum()),'auc':a,'null_mean':float(null.mean()),'null_p95':float(np.percentile(null,95)),'perm_p':permutation_pvalue(a,null)}

def pnl_summary(f, key='condition_id'):
    if f is None or len(f)==0: return {'trades':0}
    per=f.groupby(key)['pnl'].sum()
    t=hac_t_test(per.to_numpy())
    b=stationary_bootstrap_pvalue(per.to_numpy(),n_boot=3000).p_value if per.size>=5 else None
    usd=float(f['usd'].sum())
    return {'trades':int(len(f)),'windows':int(per.size),'usd':usd,'pnl':float(f.pnl.sum()),'fees':float(f['fee'].sum()) if 'fee' in f else 0.0,'ret':float(f.pnl.sum()/usd) if usd else None,'per_window_t':t.statistic,'per_window_p':t.p_value,'boot_p':b}
