"""Build a per-print table (all taker prints in sampled markets) with point-in-time features.

Every feature for a print at second t uses only prints with ts <= t - L (L = latency, default 2 s),
plus listing-time metadata (gameStartTime, sportsMarketType, outcomes, feeSchedule).
Resolution payout is attached for settlement only.
"""
import pickle, json, sys, re
import numpy as np, pandas as pd
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.analysis.profile import resolution_info
S=sys.argv[1]; L=int(sys.argv[2]) if len(sys.argv)>2 else 2
W='0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
tp=pickle.load(open(f'{S}/tapes.pkl','rb')); sel=tp['sel'].set_index('condition_id')
m=pickle.load(open(f'{S}/window.pkl','rb'))['markets']
SPLIT=1793318400-15*86400
NS=[10,30,60,120,300]
out=[]
for cid,v in tp['tapes'].items():
    rows=v['rows']
    if not rows: continue
    mm=m[cid]; tokens=[str(x) for x in json.loads(mm['clobTokenIds'])]; outs=json.loads(mm['outcomes'])
    res=resolution_info(mm)
    if not res['resolved']: continue
    gst=sel.loc[cid,'gst']; rate=float((mm.get('feeSchedule') or {}).get('rate',0.05)) if mm.get('feesEnabled',True) else 0.0
    df=pd.DataFrame(rows)
    df=df[df['asset'].astype(str).isin(tokens)].copy()
    if df.empty: continue
    df['ts']=df['timestamp'].astype(int); df['k']=df['asset'].astype(str).map(tokens.index)
    df['price']=df['price'].astype(float); df['size']=df['size'].astype(float)
    df['wallet']=df['proxyWallet'].str.lower()
    df=df.sort_values('ts',kind='stable').reset_index(drop=True)
    # implied token-0 price from every print (buy or sell, either token)
    p0=np.where(df.k==0, df.price, 1-df.price)
    ts=df.ts.to_numpy()
    # last known p0 at time t-L: index of last print with ts <= t-L
    def last_idx(tq):
        return np.searchsorted(ts, tq, side='right')-1
    i_known=last_idx(ts-L)
    p0_known=np.where(i_known>=0, p0[np.clip(i_known,0,None)], np.nan)
    feat={'p0_known':p0_known,'since_last_print':np.where(i_known>=0, ts-ts[np.clip(i_known,0,None)], np.nan)}
    for N in NS:
        j=last_idx(ts-L-N)
        feat[f'p0_lag{N}']=np.where(j>=0, p0[np.clip(j,0,None)], np.nan)
    # signed buy flow on token0 in (t-L-30, t-L]: +usd for buy token0 / sell token1, - otherwise
    sgn=np.where(((df.k==0)&(df.side=='BUY'))|((df.k==1)&(df.side=='SELL')),1.0,-1.0)
    usd=(df.price*df['size']).to_numpy()
    cum=np.concatenate([[0],np.cumsum(sgn*usd)])
    for Wf in (30,120):
        a=np.searchsorted(ts, ts-L-Wf, side='right'); b=np.searchsorted(ts, ts-L, side='right')
        feat[f'flow0_{Wf}']=cum[b]-cum[a]
    # number of prints in market in last 60s (activity)
    a=np.searchsorted(ts, ts-L-60, side='right'); b=np.searchsorted(ts, ts-L, side='right'); feat['n60']=b-a
    f=pd.DataFrame(feat)
    df=pd.concat([df[['ts','k','side','price','size','wallet','transactionHash']].reset_index(drop=True),f],axis=1)
    df['cid']=cid; df['event_slug']=mm['events'][0]['slug'] if mm.get('events') else mm['slug']
    df['set']=sel.loc[cid,'set']; df['fam']=sel.loc[cid,'fam']; df['smt']=mm.get('sportsMarketType')
    df['outcome']=[outs[k] for k in df.k]; df['gst']=gst; df['minutes']=(df.ts-gst)/60
    df['payout']=[res['payout'].get(tokens[k],np.nan) for k in df.k]
    df['fee_rate']=rate; df['period']=np.where(gst<SPLIT,'FIT','TEST')
    df['line']=float(re.search(r'O/U (\d+\.?\d*)', mm.get('question','')).group(1)) if re.search(r'O/U (\d+\.?\d*)', mm.get('question','')) else np.nan
    df['is_wallet']=df.wallet==W
    out.append(df)
P=pd.concat(out,ignore_index=True)
# features in the bought token's frame
sgnk=np.where(P.k==0,1,-1)
P['pk_known']=np.where(P.k==0,P.p0_known,1-P.p0_known)
for N in NS: P[f'mom{N}']=sgnk*(P.p0_known-P[f'p0_lag{N}'])
P['flowk_30']=sgnk*P.flow0_30; P['flowk_120']=sgnk*P.flow0_120
P['gap']=P.price-P.pk_known
P.to_pickle(f'{S}/prints_L{L}.pkl')
B=P[(P.side=='BUY')&(P.minutes>=0)]
print('prints',len(P),'in-play buys',len(B),'wallet in-play buys',B.is_wallet.sum(),'markets',P.cid.nunique(),'events',P.event_slug.nunique())
print(B.groupby(['set','period']).agg(n=('ts','size'),w=('is_wallet','sum'),mk=('cid','nunique')))
