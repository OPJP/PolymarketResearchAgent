import sys
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import os; os.chdir('/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums
from polyrea.stats.significance import hac_t_test, sharpe
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'; AS_OF=1793318400
body,src=PolymarketData().user_pnl(W)
pts=body.get('points') or []
print('points', len(pts), 'keys', list(pts[-1].keys()), src.cached, src.fetched_at)
df=daily_frame(pts, as_of=AS_OF)
d=df.iloc[1:]
print('days', len(d), d.index.min(), d.index.max())
e=d['d_economic_pnl']
print('last30 economic', e.iloc[-30:].sum(), 'trade', d['d_trade_pnl'].iloc[-30:].sum(), 'wallet_income', d['d_wallet_income'].iloc[-30:].sum(), 'maker_rebate', d['d_maker_rebate'].iloc[-30:].sum(), 'fees', d['d_fees_paid'].iloc[-30:].sum(), 'vol', d['d_volume_usdc'].iloc[-30:].sum())
mb=monthly_blocks(e); print('monthly blocks', [round(x) for x in mb], 'median', np.median(mb[:6]))
wk=weekly_sums(e); print('weeks', len(wk), 'pos share', (wk>0).mean())
print('annual sharpe', sharpe(e.to_numpy()), 'pos days', (e>0).mean())
pre=e.iloc[:-30]
print('pre days', len(pre), hac_t_test(pre.to_numpy()))
print('recent', hac_t_test(e.iloc[-30:].to_numpy()))
# rebate ratio over time
d=d.copy(); d['taker_reb']=d['d_wallet_income']-d['d_maker_rebate']-d.get('d_reward_income',0)
m=d.resample('30D', origin='end').sum()
m['reb_rate']=m.taker_reb/(-m.d_fees_paid)
m['trade_ex_fee']=m.d_trade_pnl
print(m[['d_economic_pnl','d_trade_pnl','d_fees_paid','taker_reb','d_maker_rebate','reb_rate','d_volume_usdc']].round(3).to_string())
# weekly rebate rate last 8 weeks
w7=d.iloc[-56:].resample('7D', origin='end').sum()
w7['reb_rate']=w7.taker_reb/(-w7.d_fees_paid)
print(w7[['d_economic_pnl','d_trade_pnl','d_fees_paid','taker_reb','reb_rate','d_volume_usdc']].round(3).to_string())
# 0% tier daily series stats
z=d['d_economic_pnl']-d['taker_reb']
print('0%-tier economic last30', z.iloc[-30:].sum(), 'all-history sum', z.sum(), 'hac all', hac_t_test(z.to_numpy()))
d.to_pickle('/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/daily.pkl')
