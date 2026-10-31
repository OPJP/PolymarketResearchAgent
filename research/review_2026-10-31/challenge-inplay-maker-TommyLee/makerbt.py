"""Vectorized tape maker backtest with per-quote side filters (same fill rules as polyrea.analysis.tape_maker,
validated against it). Decisions at quote time t0 use prints with ts <= t0-L only; resolution only settles."""
import numpy as np, pandas as pd, math
from common import *

def maker_bt(tk, pay, active, cids, delta, L, R=10, size=20.0, tick=0.01, side_rule=None, D=30, theta=0.0,
             at_touch=False, exclude_wallet_prints=False, delta_dog=None, return_fills=False):
    """side_rule: None (both sides), 'fav' (bid only outcome with fair>=theta), 'dog' (fair<=theta),
    'mom' (bid only outcome whose price rose >= theta over D s ending t0-L), 'antimom' (fell <= -theta),
    'lean' (both sides; favourite at delta, underdog at delta_dog)."""
    out=[]
    for cid in cids:
        g=tk[tk.cid==cid]
        if exclude_wallet_prints: gq=g[g.wallet!=WALLET]
        else: gq=g
        ts_all=g.ts.to_numpy(); p0_all=g.p0.to_numpy()
        a,b=active[cid]
        ts=gq.ts.to_numpy()
        inwin=(ts>a)&(ts<=b+R)   # prints in (a, last grid + R]
        gq=gq[inwin]; ts=ts[inwin]
        if len(gq)==0: continue
        t0=a+R*np.ceil((ts-a)/R).astype(np.int64)-R
        keep=t0<b
        gq=gq[keep]; ts=ts[keep]; t0=t0[keep]
        if len(gq)==0: continue
        def p0at(t):
            k=np.searchsorted(ts_all,t,side='right')-1
            return np.where(k>=0,p0_all[np.clip(k,0,None)],np.nan)
        f0=p0at(t0-L)
        mom0=f0-p0at(t0-L-D)
        oc=gq.outcome.to_numpy(); sd=gq.side.to_numpy(); pr=gq.price.to_numpy(); sz=gq['size'].to_numpy()
        for o in (0,1):
            fair=f0 if o==0 else 1-f0
            mom=mom0 if o==0 else -mom0
            d=np.full(len(fair),delta,dtype=float)
            if side_rule=='lean' and delta_dog is not None:
                d=np.where(fair>=0.5,delta,delta_dog)
            q=np.floor((fair-d)/tick+1e-9)*tick
            ok=np.isfinite(q)&(q>=tick)&(q<=1-tick)
            if side_rule=='fav': ok&=fair>=theta
            elif side_rule=='dog': ok&=fair<=theta
            elif side_rule=='mom': ok&=np.nan_to_num(mom,nan=-9)>=theta
            elif side_rule=='antimom': ok&=np.nan_to_num(mom,nan=9)<=-theta
            if at_touch:
                hit=((oc==o)&(sd=='SELL')&(pr<=q+1e-9))|((oc!=o)&(sd=='BUY')&(pr>=1-q-1e-9))
            else:
                hit=((oc==o)&(sd=='SELL')&(pr<q-1e-9))|((oc!=o)&(sd=='BUY')&(pr>1-q+1e-9))
            hit&=ok
            if not hit.any(): continue
            df=pd.DataFrame({'t0':t0[hit],'q':q[hit],'sz':sz[hit]})
            agg=df.groupby('t0').agg(q=('q','first'),sz=('sz','sum'))
            filled=np.minimum(size,agg.sz.to_numpy())
            po=pay[cid] if o==0 else 1-pay[cid]
            for tt,qq,ff in zip(agg.index.to_numpy(),agg.q.to_numpy(),filled):
                out.append((cid,int(tt),o,float(qq),float(ff),float(ff*(po-qq))))
    if not out: return {'fills':0}
    f=pd.DataFrame(out,columns=['cid','ts','outcome','price','shares','pnl'])
    usd=float((f.price*f.shares).sum())
    pm=f.groupby('cid').pnl.sum()
    r={'fills':int(len(f)),'usd':usd,'pnl':float(f.pnl.sum()),'ret':float(f.pnl.sum()/usd) if usd else None,
       'maker_rebate_est':float((0.15*FEE_RATE*f.price*(1-f.price)*f.shares).sum())}
    r['_pm']=pm
    if return_fills: r['_fills']=f
    return r

def jump_times(tk_cid_ts, tk_cid_p0, theta, win=10, dedup=20):
    """Times of public-tape jumps: a print at t with |p0(t)-p0(t-win)|>=theta (uses prints <= t only)."""
    ts=tk_cid_ts; p=tk_cid_p0
    k=np.searchsorted(ts,ts-win,side='right')-1
    prev=np.where(k>=0,p[np.clip(k,0,None)],np.nan)
    j=ts[np.abs(p-prev)>=theta]
    out=[];last=-1e18
    for t in j:
        if t-last>dedup: out.append(t)
        last=t
    return np.array(out,dtype=float)

def maker_bt_window(tk, pay, active, cids, delta, L, a, b, theta_j, R=5, size=20.0, tick=0.001, at_touch=False):
    """H5: two-sided maker that quotes only while the time since the last public-tape jump (known at t0-L) is in [a,b]."""
    out=[]
    for cid in cids:
        g=tk[tk.cid==cid]
        ts_all=g.ts.to_numpy(); p0_all=g.p0.to_numpy()
        J=jump_times(ts_all,p0_all,theta_j)
        s,e=active[cid]
        ts=ts_all; inwin=(ts>s)&(ts<=e+R); gq=g[inwin]; ts=ts[inwin]
        if len(gq)==0: continue
        t0=s+R*np.ceil((ts-s)/R).astype(np.int64)-R
        keep=t0<e; gq=gq[keep]; ts=ts[keep]; t0=t0[keep]
        if len(gq)==0: continue
        k=np.searchsorted(ts_all,t0-L,side='right')-1
        f0=np.where(k>=0,p0_all[np.clip(k,0,None)],np.nan)
        if len(J):
            kj=np.searchsorted(J,t0-L,side='right')-1
            tsj=np.where(kj>=0,(t0-L)-J[np.clip(kj,0,None)],np.inf)
        else: tsj=np.full(len(t0),np.inf)
        on=(tsj>=a)&(tsj<=b)
        oc=gq.outcome.to_numpy(); sd=gq.side.to_numpy(); pr=gq.price.to_numpy(); sz=gq['size'].to_numpy()
        for o in (0,1):
            fair=f0 if o==0 else 1-f0
            q=np.floor((fair-delta)/tick+1e-9)*tick
            ok=np.isfinite(q)&(q>=tick)&(q<=1-tick)&on
            if at_touch: hit=((oc==o)&(sd=='SELL')&(pr<=q+1e-9))|((oc!=o)&(sd=='BUY')&(pr>=1-q-1e-9))
            else: hit=((oc==o)&(sd=='SELL')&(pr<q-1e-9))|((oc!=o)&(sd=='BUY')&(pr>1-q+1e-9))
            hit&=ok
            if not hit.any(): continue
            df=pd.DataFrame({'t0':t0[hit],'q':q[hit],'sz':sz[hit]})
            agg=df.groupby('t0').agg(q=('q','first'),sz=('sz','sum'))
            filled=np.minimum(size,agg.sz.to_numpy()); po=pay[cid] if o==0 else 1-pay[cid]
            for tt,qq,ff in zip(agg.index.to_numpy(),agg.q.to_numpy(),filled):
                out.append((cid,int(tt),o,float(qq),float(ff),float(ff*(po-qq))))
    if not out: return {'fills':0}
    f=pd.DataFrame(out,columns=['cid','ts','outcome','price','shares','pnl'])
    usd=float((f.price*f.shares).sum()); pm=f.groupby('cid').pnl.sum()
    q=f.groupby(['cid','outcome']).shares.sum().unstack(fill_value=0.0)
    pairs=float(np.minimum(q.get(0,0),q.get(1,0)).sum()) if q.shape[1]==2 else 0.0
    return {'fills':int(len(f)),'usd':usd,'pnl':float(f.pnl.sum()),'ret':float(f.pnl.sum()/usd),'pairs':pairs,'_pm':pm}
