import sys
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import os; os.chdir('/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'; AS_OF=1793318400
body,src=PolymarketData().user_pnl(W)
df=pd.DataFrame(body['points'])
df=df[(df.timestamp%86400==0)&(df.timestamp<=AS_OF)].copy()
df['day']=pd.to_datetime(df.timestamp,unit='s')
cols=['taker_rebate','maker_rebate','fees_paid','fees','fees_refunded','sponsored_income','referral_income','reward_income','wallet_income','trade_pnl','economic_pnl','volume_usdc']
for c in cols: df[c]=pd.to_numeric(df[c],errors='coerce')
dd=df.set_index('day')[cols].diff()
dd['rate']=dd.taker_rebate/(-dd.fees_paid)
pd.set_option('display.width',250)
print(dd.iloc[-40:].round(1).to_string())
x=dd.iloc[-30:]
print('last30 sums'); print(x.sum().round(1))
print('history sums'); print(dd.sum().round(1))
# daily rebate as a function of previous day's fees
r=pd.DataFrame({'reb':dd.taker_rebate,'fee_prev':-dd.fees_paid.shift(1),'fee':-dd.fees_paid}).dropna()
r=r[r.reb>0]
print('rate same-day median', (r.reb/r.fee).median(), 'prev-day median', (r.reb/r.fee_prev).median())
print((r.reb/r.fee_prev).iloc[-40:].round(3).to_string())
