import pickle, pandas as pd, numpy as np
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
t=pd.read_pickle(S+'trades_roles.pkl')
P=pickle.load(open(S+'period_btc_15m.pkl','rb'))
cids={w.condition_id:w for w in P['test']['windows']}
tt=t[t.condition_id.isin(cids)].copy()
print('wallet fills in test 15m windows', len(tt), tt.role.value_counts().to_dict(), 'windows', tt.condition_id.nunique(), '/', len(cids))
tt['rel']=tt.ts-tt.condition_id.map(lambda c: cids[c].start_ts)
pd.set_option('display.width',250); pd.set_option('display.max_rows',300)
c=tt.condition_id.value_counts().index[5]
w=cids[c]
x=tt[tt.condition_id==c].sort_values('ts')[['rel','outcome','role','price','size','usdc']]
print(c, 'up_payout', w.up_payout); print(x.head(120).to_string())
print('rel quantiles by role', tt.groupby('role').rel.describe())
