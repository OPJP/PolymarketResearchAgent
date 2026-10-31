"""Feature builder for taker-buy and passive-buy prints (point-in-time: every feature at print ts uses records with ts < print ts)."""
import sys, pickle
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.analysis.updown import SpotIndex, fair_up_vectorized, maker_buy_prints, taker_flow
from polyrea.pit import TimeSeries
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'

def load(dur):
    P=pickle.load(open(S+f'period_btc_{dur}.pkl','rb'))
    ev=np.concatenate([P['fit']['spot'].event_ts,P['test']['spot'].event_ts]); vals=np.concatenate([P['fit']['spot'].values,P['test']['spot'].values])
    o=np.argsort(ev,kind='stable')
    spot=SpotIndex(TimeSeries.build('spot.kraken.btc', zip(ev[o].tolist(), vals[o].tolist()), availability_lag=1))
    return P, spot

def implied_up_series(flow):
    """per window: arrays of (ts, implied Up price) from every taker print (BUY or SELL), sorted."""
    out={}
    for cid,g in flow.groupby('condition_id'):
        g=g.sort_values('ts',kind='stable')
        up=np.where(g.is_up.to_numpy(), g.price.to_numpy(), 1-g.price.to_numpy())
        out[cid]=(g.ts.to_numpy().astype(np.int64), up)
    return out

def last_before(series, cid, t, lag=1):
    ts,up=series.get(cid,(np.array([],dtype=np.int64),np.array([])))
    i=np.searchsorted(ts, t-lag+1, side='left')-1   # records with ts <= t-lag
    return np.where(i>=0, up[np.clip(i,0,None)] if len(up) else np.nan, np.nan)

def add_features(pr, flow, spot, wallet_trades, lag=1):
    pr=pr.copy().reset_index(drop=True)
    ser=implied_up_series(flow)
    ts=pr.ts.to_numpy().astype(np.int64)
    cid=pr.condition_id.to_numpy()
    up_last=np.full(len(pr),np.nan); up_30=np.full(len(pr),np.nan); up_120=np.full(len(pr),np.nan)
    for c in np.unique(cid):
        m=cid==c
        up_last[m]=last_before(ser,c,ts[m],lag)
        up_30[m]=last_before(ser,c,ts[m],30)
        up_120[m]=last_before(ser,c,ts[m],120)
    side_last=np.where(pr.is_up, up_last, 1-up_last)
    pr['mom30']=np.where(pr.is_up, up_last-up_30, up_30-up_last)   # move of the bought side over 30s before
    pr['mom120']=np.where(pr.is_up, up_last-up_120, up_120-up_last)
    pr['prem']=pr.price-side_last          # price paid vs last implied price of that side
    pr['secs_to_end']=pr.end_ts-pr.ts
    pr['frac']=(pr.ts-pr.start_ts)/(pr.end_ts-pr.start_ts)
    fu=fair_up_vectorized(spot, pr.start_ts.to_numpy(), pr.end_ts.to_numpy(), ts-lag, int(pr.twap.iloc[0]))
    pr['spot_edge']=np.where(pr.is_up, fu, 1-fu)-pr.price
    pr['fair_side']=np.where(pr.is_up, fu, 1-fu)
    # wallet inventory before t (wallet's own public fills with ts < print ts)
    wt=wallet_trades[wallet_trades.condition_id.isin(set(cid))]
    inv_same=np.zeros(len(pr)); inv_opp=np.zeros(len(pr)); cost_opp=np.full(len(pr),np.nan)
    for c,g in wt.groupby('condition_id'):
        m=np.nonzero(cid==c)[0]
        if len(m)==0: continue
        g=g.sort_values('ts')
        gts=g.ts.to_numpy(); up=(g.outcome_index.to_numpy()==0)
        cu=np.cumsum(np.where(up,g['size'],0)); cd=np.cumsum(np.where(~up,g['size'],0))
        uu=np.cumsum(np.where(up,g.usdc,0)); ud=np.cumsum(np.where(~up,g.usdc,0))
        k=np.searchsorted(gts, ts[m], side='left')-1  # strictly before
        qu=np.where(k>=0,cu[np.clip(k,0,None)],0); qd=np.where(k>=0,cd[np.clip(k,0,None)],0)
        vu=np.where(k>=0,uu[np.clip(k,0,None)],0); vd=np.where(k>=0,ud[np.clip(k,0,None)],0)
        isup=pr.is_up.to_numpy()[m]
        inv_same[m]=np.where(isup,qu,qd); inv_opp[m]=np.where(isup,qd,qu)
        co=np.where(isup, np.where(qd>0, vd/np.maximum(qd,1e-9), np.nan), np.where(qu>0, vu/np.maximum(qu,1e-9), np.nan))
        cost_opp[m]=co
    pr['imb']=inv_opp-inv_same      # >0: wallet is short this side
    pr['pair_vs_own']=pr.price+cost_opp   # pair cost if this buy completes a pair against own inventory
    pr['y']=(pr.wallet==W).astype(int)
    return pr
