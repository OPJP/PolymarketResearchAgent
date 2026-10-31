import json, pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.adapters.polymarket import PolymarketData
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
W='0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'; AS_OF=1793318400
d=pickle.load(open(OUT+'win.pkl','rb')); win=d['win']; led=win['ledger']; mk=win['markets']
s=led.exposure_series()
start=pd.Timestamp(AS_OF-30*86400,unit='s',tz='UTC'); end=pd.Timestamp(AS_OF,unit='s',tz='UTC')
sw=s[(s.index>start)&(s.index<=end)]
# time-weighted average capital in the window
idx=sw.index; vals=sw.values
prev=s[s.index<=start]
lvl0=prev.iloc[-1] if len(prev) else 0.0
times=np.r_[start.value/1e9, idx.asi8/1e9, end.value/1e9]; levels=np.r_[lvl0, vals]
dur=np.diff(times); twa=(levels*dur).sum()/dur.sum()
print('window start level', lvl0, 'time-weighted avg capital', twa, 'peak', sw.max(), 'peak time', sw.idxmax())
dp=led.daily_peak_exposure(); print(dp[dp.index>start].round(0).to_string())
# composition at peak time
pk=sw.idxmax().value//10**9
# replay: open positions at pk -> recompute from positions' trades
tr=pd.DataFrame(led.trades)
rows=[]
for a,p in led.positions.items():
    pass
# approximate: cost basis of buys before pk minus sells, for positions not closed before pk
comp={}
for a,p in led.positions.items():
    t=tr[(tr.asset==a)&(tr.ts<=pk)]
    if t.empty: continue
    if p.closed_at is not None and p.closed_at<=pk and p.opened_at is not None and p.opened_at<=p.closed_at:
        # closed before peak and not reopened
        continue
    c=t[t.side=='BUY'].usdc.sum()-t[t.side=='SELL'].usdc.sum()
    comp[(p.condition_id, t.title.iloc[0], t.outcome.iloc[0])]=c
c=pd.Series(comp).sort_values(ascending=False)
print('approx composition at peak (net cash in):'); print(c.head(20).round(0).to_string()); print('sum', c.sum())
pv,src=PolymarketData().portfolio_value(W)
print('current portfolio value (data-api /value):', pv, src.fetched_at)
print('ledger open cost at end', s.iloc[-1], 'at', s.index[-1])
json.dump({'twa_capital':twa,'peak':float(sw.max()),'peak_time':str(sw.idxmax()),'portfolio_value_now':pv}, open(OUT+'capital.json','w'), indent=1)
