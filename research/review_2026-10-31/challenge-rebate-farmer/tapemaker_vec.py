import numpy as np, pandas as pd
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue
def tape_maker_vec(flow, windows, delta, latency, requote_s=10, size_shares=20.0, tick=0.01, queue_share=1.0, at_touch=False, min_secs_to_end=0, max_secs_to_end=None):
    """Vectorized equivalent of polyrea.analysis.tape_maker.tape_maker_backtest (active=[start,end)).
    fair(Up) at tick t0 = last taker print (implied Up) with ts <= t0 - latency. at_touch=True: prints AT the bid fill too."""
    by={w.condition_id:w for w in windows}
    out=[]
    for cid,g in flow.groupby('condition_id'):
        w=by.get(cid)
        if w is None or w.up_payout is None: continue
        g=g.sort_values('ts',kind='stable')
        ts=g.ts.to_numpy().astype(np.int64); isup=g.is_up.to_numpy(); side=g.side.to_numpy(); px=g.price.to_numpy(); sz=g['size'].to_numpy()
        p0=np.where(isup,px,1-px)
        ticks=np.arange(w.start_ts, w.end_ts-min_secs_to_end, requote_s)
        if max_secs_to_end is not None: ticks=ticks[(w.end_ts-ticks)<=max_secs_to_end]
        if len(ticks)==0: continue
        k=np.searchsorted(ts, ticks-latency, side='right')-1
        fair0=np.where(k>=0, p0[np.clip(k,0,None)], np.nan)
        j=np.searchsorted(ticks, ts, side='left')-1   # print at ts belongs to tick j with t0 < ts <= t0+R
        ok=(j>=0)&(ts>ticks[np.clip(j,0,None)])&(ts<=ticks[np.clip(j,0,None)]+requote_s)
        jj=j[ok]
        for sup in (True,False):
            fair=fair0 if sup else 1-fair0
            q=np.floor((fair-delta)/tick+1e-9)*tick
            valid=np.isfinite(fair)&(q>=tick-1e-12)&(q<=1-tick+1e-12)
            qj=q[jj]; eps=-1e-9 if at_touch else 1e-9
            thr=((isup[ok]==sup)&(side[ok]=='SELL')&(px[ok]<qj-eps))|((isup[ok]!=sup)&(side[ok]=='BUY')&(px[ok]>1-qj+eps))
            avail=np.bincount(jj[thr],weights=sz[ok][thr],minlength=len(ticks))*queue_share
            filled=np.where(valid,np.minimum(size_shares,avail),0.0)
            idx=np.nonzero(filled>0)[0]
            if len(idx)==0: continue
            pay=w.up_payout if sup else 1-w.up_payout
            for i in idx:
                out.append((cid,int(ticks[i]),sup,float(q[i]),float(filled[i]),float(filled[i]*(pay-q[i])),w.end_ts))
    if not out: return {'fills':0}
    f=pd.DataFrame(out,columns=['condition_id','ts','is_up','price','shares','pnl','end_ts'])
    per=f.groupby('condition_id').pnl.sum(); t=hac_t_test(per.to_numpy()); usd=float((f.price*f.shares).sum())
    return {'fills':int(len(f)),'markets':int(per.size),'usd_bought':usd,'pnl':float(f.pnl.sum()),'return_on_bought':float(f.pnl.sum()/usd) if usd else None,
            'per_market_t':t.statistic,'per_market_p':t.p_value,'per_market_bootstrap_p':stationary_bootstrap_pvalue(per.to_numpy(),n_boot=2000).p_value if per.size>=5 else None,'_fills':f}
