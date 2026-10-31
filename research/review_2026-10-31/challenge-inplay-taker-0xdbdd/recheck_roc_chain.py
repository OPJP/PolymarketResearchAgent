import sys, json
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.workflows.investigate import load_window, verify_onchain
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame
from polyrea.analysis.ledger import capital_and_roc
W='0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'; AS_OF=1793318400
pm=PolymarketData(); win=load_window(W,30,AS_OF,pm=pm)
body,_=pm.user_pnl(W,max_age=None); df=daily_frame(body['points'],as_of=AS_OF); daily=df['d_economic_pnl'].iloc[1:]
roc=capital_and_roc(win['ledger'],daily,window_days=30); print(json.dumps(roc,default=float))
ch=verify_onchain(W,win['trades'],sample=12,seed=2026)
print(json.dumps({k:v for k,v in ch.items() if k!='sources'},default=float))
