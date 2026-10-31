import json, pickle, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.workflows.investigate import load_window
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.ledger import capital_and_roc
from polyrea.analysis.pnl import daily_frame
from polyrea.analysis.profile import resolution_info
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
W='0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'
AS_OF=1793318400
pm=PolymarketData()
t0=time.time()
win=load_window(W, days=30, as_of=AS_OF, pm=pm)
print('load', time.time()-t0, len(win['activity']), len(win['trades']), len(win['markets']), 'missing', len(win['missing_markets']))
body, src = pm.user_pnl(W)
df=daily_frame(body.get('points') or [], as_of=AS_OF)
daily=df['d_economic_pnl'].iloc[1:]
roc=capital_and_roc(win['ledger'], daily, 30)
print('roc', roc)
print(df[['d_economic_pnl','d_trade_pnl','d_wallet_income','d_volume_usdc']].tail(35).round(0).to_string())
pickle.dump({'win':win,'df':df}, open(OUT+'win.pkl','wb'))
