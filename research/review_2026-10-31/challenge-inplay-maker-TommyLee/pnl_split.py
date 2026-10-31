"""Recompute A1/persistence numbers from the cached user-pnl series and split economics by phase."""
import json, numpy as np, pandas as pd, pickle
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
pm=PolymarketData()
data,src=pm.user_pnl('0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2',max_age=1e12)
print(src.cached, src.body_sha256)
pts=data['points']
if isinstance(pts,dict): print(pts.keys())
df=daily_frame(pts,as_of=1793318400)
print(df.index.min(),df.index.max(),len(df))
d=df['d_economic_pnl']
print('last30',d.iloc[-30:].sum(),'blocks',monthly_blocks(d))
pre=d.iloc[:-30]; r=hac_t_test(pre.to_numpy()); print('pre n',len(pre),'hac t',r.statistic,'p',r.p_value)
b=stationary_bootstrap_pvalue(pre.to_numpy(),n_boot=4000); print('boot p',b.p_value)
ann=d.mean()/d.std(ddof=1)*np.sqrt(365); print('annual sharpe',ann,'pos weeks',(weekly_sums(d)>0).mean(),'pos days',(d>0).mean())
rec=hac_t_test(d.iloc[-30:].to_numpy()); print('recent30 t',rec.statistic,'p',rec.p_value)
cols=[c for c in df.columns if c.startswith('d_')]
df['phase']=np.where(df.index<pd.Timestamp('2026-10-17',tz='UTC'),'pre-Oct17','Oct17+')
df['month']=np.where(df.index>pd.Timestamp('2026-09-30',tz='UTC'),'window','before')
g=df.groupby(['month','phase'])[cols].sum(); g['days']=df.groupby(['month','phase']).size()
pd.set_option('display.width',250); print(g.round(0).T)
# per-day in window
w=df[df.index>pd.Timestamp('2026-09-30',tz='UTC')][cols].round(0)
print(w.to_string())
# earliest period economics by 30d blocks
df['blk']=((len(df)-1-np.arange(len(df)))//30)
print(df.groupby('blk')[cols].sum().round(0).T)
df.to_pickle(W+'/daily_pnl.pkl')
