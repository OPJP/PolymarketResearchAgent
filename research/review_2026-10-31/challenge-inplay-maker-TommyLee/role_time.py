import pickle, numpy as np, pandas as pd, sys
sys.path.insert(0,W:='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *
tk,mk,pay,active,fit,test,split,event=load()
f=pickle.load(open(W+'/wallet_fills160.pkl','rb'))
f['day']=pd.to_datetime(f.ts,unit='s').dt.date
f['half']=np.where(f.cid.isin(fit),'FIT','TEST')
print('split',pd.to_datetime(split,unit='s'))
print(f.groupby(['half','role']).agg(n=('ts','size'),usd=('usd','sum'),net=('net','sum'),mk=('cid','nunique')))
d=f.groupby(['day','role']).usd.sum().unstack(fill_value=0); d['maker_share']=d.maker/(d.maker+d.taker)
print(d.round(0).to_string())
