import pickle, numpy as np, pandas as pd
D=pickle.load(open('/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude/games200.pkl','rb'))
G=pd.DataFrame(D['games']); P=D['prints']
split=int(np.median(G.start)); G['fit']=G.start<split
print('split',pd.Timestamp(split,unit='s'), 'fit games',G.fit.sum(),'test',(~G.fit).sum())
print(G.groupby(['fit','league']).size().unstack(0))
P=P.merge(G[['event_slug','fit','league','start']],on='event_slug')
print('fee rates', P.fee_rate.value_counts().head())
print('side x wallet', pd.crosstab(P.side,P.is_wallet))
print('mtype x wallet', pd.crosstab(P.mtype,P.is_wallet))
w=P[P.is_wallet]
print('wallet price quantiles', w.price.quantile([.05,.25,.5,.75,.95]).round(3).tolist())
print('wallet usd quantiles', (w.price*w.size).quantile([.05,.25,.5,.75,.95,.99]).round(1).tolist())
# time in game fraction
dur=G.set_index('event_slug').apply(lambda g: g.plays[-1][0]-g.start,axis=1)
P['tfrac']=(P.ts-P.start)/P.event_slug.map(dur)
print('wallet tfrac q', P[P.is_wallet].tfrac.quantile([.1,.25,.5,.75,.9]).round(2).tolist(), 'others', P[~P.is_wallet].tfrac.quantile([.1,.25,.5,.75,.9]).round(2).tolist())
# return by price bucket, wallet vs others, BUY prints only, fees
b=P[(P.side=='BUY')&P.payout.notna()].copy()
b['usd']=b.price*b['size']; b['fee']=b.fee_rate*b.price*(1-b.price)*b['size']; b['pnl']=b['size']*b.payout-b.usd-b.fee
b['bk']=pd.cut(b.price,[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,.95,1.0])
t=b.groupby(['bk','is_wallet'],observed=True).apply(lambda g: pd.Series({'n':len(g),'usd':g.usd.sum(),'ret':g.pnl.sum()/g.usd.sum(),'ret_capped': (np.minimum(g.usd,100)/g.price*g.payout - np.minimum(g.usd,100) - g.fee_rate*(1-g.price)*np.minimum(g.usd,100)).sum()/np.minimum(g.usd,100).sum()}))
print(t.unstack(1).round(4))
print('overall ret wallet', b[b.is_wallet].pnl.sum()/b[b.is_wallet].usd.sum(), 'others', b[~b.is_wallet].pnl.sum()/b[~b.is_wallet].usd.sum())
for f in (True,False):
    x=b[b.fit==f]
    print('fit' if f else 'test','wallet ret',x[x.is_wallet].pnl.sum()/x[x.is_wallet].usd.sum(), 'usd',x[x.is_wallet].usd.sum(), 'others ret', x[~x.is_wallet].pnl.sum()/x[~x.is_wallet].usd.sum())
