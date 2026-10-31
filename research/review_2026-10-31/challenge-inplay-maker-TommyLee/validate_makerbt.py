"""Check the vectorized backtest reproduces polyrea.analysis.tape_maker on the recorded TEST setting."""
import sys; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *; from makerbt import maker_bt
from polyrea.analysis.tape_maker import tape_maker_backtest
tk,mk,pay,active,fit,test,split,event=load()
flow=tk.rename(columns={'cid':'condition_id'})[['condition_id','ts','outcome','side','price','size']]
tc=sorted(test)
ref=tape_maker_backtest(flow[flow.condition_id.isin(test)],pay,0.05,latency=2,active=active)
mine=maker_bt(tk,pay,active,tc,0.05,2)
print('ref',{k:ref[k] for k in ['fills','usd_bought','pnl','return_on_bought']})
print('mine',{k:mine[k] for k in ['fills','usd','pnl','ret']})
