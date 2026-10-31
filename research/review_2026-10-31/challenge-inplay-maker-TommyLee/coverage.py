import pickle, numpy as np, pandas as pd
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
d=pickle.load(open(W+'/window.pkl','rb')); t=d['trades']
F=pickle.load(open(W+'/frames160.pkl','rb')); f=pickle.load(open(W+'/wallet_fills160.pkl','rb'))
cids=F['cids']
ta=t[t.condition_id.isin(cids)]
a=ta.groupby('condition_id').agg(n_act=('ts','size'),usd_act=('usdc','sum'))
b=f.groupby('cid').agg(n_tape=('ts','size'),usd_tape=('usd','sum'))
c=a.join(b,how='left').fillna(0)
c['ratio']=c.n_tape/c.n_act
print(c.describe())
print((c.ratio<0.5).sum(), 'markets with <50% coverage')
print(c.sort_values('ratio').head(10))
# full tape row counts per market
mk=F['mk']; tk=F['tk']
print(mk.groupby('cid').size().describe())
# check if full tape hits a cap (e.g. exactly some number)
print(mk.groupby('cid').size().sort_values().tail(10))
print('activity sides', ta.side.value_counts())
