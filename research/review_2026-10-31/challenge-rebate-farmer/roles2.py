import pandas as pd, numpy as np
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
t=pd.read_pickle(S+'trades_roles.pkl')
pd.set_option('display.width',250); pd.set_option('display.max_rows',200); pd.set_option('display.max_columns',20)
g2=t.groupby(['fam','role']).agg(fills=('usdc','size'), usd=('usdc','sum'), fees=('fee','sum'), pnl=('pnl','sum'), pre=('pnl_prefee','sum')).round(0)
g2['ret%']=(100*g2.pnl/g2.usd).round(2)
print(g2.sort_values('usd',ascending=False).head(30).to_string())
# price buckets by role
t['pb']=(t.price*10).astype(int).clip(0,9)
g3=t.groupby(['role','pb']).agg(usd=('usdc','sum'), pnl=('pnl','sum'), pre=('pnl_prefee','sum'), fees=('fee','sum')).round(0)
print(g3.to_string())
# daily pnl by role
t['day']=pd.to_datetime(t.ts,unit='s').dt.floor('D')
dd=t.groupby(['day','role']).pnl.sum().unstack()
print(dd.describe().round(0))
print('maker daily positive share', (dd.maker>0).mean())
