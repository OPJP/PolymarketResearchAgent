import pandas as pd, numpy as np
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
for nm in ['tk_15m_fit','mk_15m_fit']:
    d=pd.read_pickle(S+nm+'.pkl')
    d['pb']=(d.price*10).astype(int).clip(0,9)
    print('==',nm)
    print(d.groupby('y').prem.describe(percentiles=[.05,.25,.5,.75,.95]).round(3))
    print('wallet prem value counts (rounded)'); print(d[d.y==1].prem.round(2).value_counts().head(10))
    print('others prem value counts'); print(d[d.y==0].prem.round(2).value_counts().head(10))
    g=d.groupby('pb').agg(n=('y','size'), wshare=('y','mean'))
    print(g.round(4).T)
    d['tb']=(d.frac*10).astype(int).clip(0,9)
    print(d.groupby('tb').y.mean().round(4).to_dict())
