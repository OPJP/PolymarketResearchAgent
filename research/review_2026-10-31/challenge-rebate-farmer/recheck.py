import sys, pickle, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import os; os.chdir('/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.stats.persistence import persistence_report
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue, sharpe
from polyrea.analysis.ledger import build_ledger, capital_and_roc
from polyrea.analysis.profile import resolution_info
from polyrea.analysis.pnl import monthly_blocks, weekly_sums
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
d=pd.read_pickle(S+'daily.pkl')
e=d['d_economic_pnl'].copy()
# one-off taker rebate lump on 2026-10-25 (day_end index): rebate/prev-day fee = 5.99 vs median 0.44
day=d.index[d.taker_reb.idxmax()==d.index][0] if False else d.taker_reb.idxmax()
prev_fee=-d.d_fees_paid.shift(1).loc[day]
excess=d.taker_reb.loc[day]-0.44*prev_fee
print('lump day', day, 'rebate', d.taker_reb.loc[day], 'prev fee', prev_fee, 'excess over 44%', excess)
# all days with rate>1
r=d.taker_reb/(-d.d_fees_paid.shift(1))
print('days with rebate > prev-day fee:', [(str(i.date()), round(v,2), round(d.taker_reb.loc[i],0)) for i,v in r[r>1].items()])
e2=e.copy(); e2.loc[day]-=excess
for nm,x in (('recorded',e),('ex-lump',e2)):
    pr=persistence_report(x.to_numpy())
    print(nm,'last30', round(x.iloc[-30:].sum()), 'recent', pr.recent, 'decline', pr.decline, 'trend', pr.trend)
    mb=monthly_blocks(x); wk=weekly_sums(x)
    print('   monthly', [round(v) for v in mb[:6]], 'median', round(np.median(mb[:6])), 'pos weeks', round((wk>0).mean(),3), 'sharpe', round(sharpe(x.to_numpy()),2), 'boot pre p', stationary_bootstrap_pvalue(x.iloc[:-30].to_numpy(), n_boot=4000).p_value)
# 0%-tier newcomer series (economic minus taker rebate) by 30-day block
z=e-d.taker_reb
print('0%-tier 30d blocks (recent first):',[round(v) for v in monthly_blocks(z)[:6]],' at steady 44%:',[round(v) for v in monthly_blocks(z-0.44*d.d_fees_paid.shift(1).fillna(0))[:6]])
print('pre-fee trade pnl 30d blocks', [round(v) for v in monthly_blocks(d.d_trade_pnl)[:6]], 'fees blocks', [round(v) for v in monthly_blocks(d.d_fees_paid)[:6]])
print('trade_pnl/volume by block', [round(a/b,4) for a,b in zip(monthly_blocks(d.d_trade_pnl)[:6], monthly_blocks(d.d_volume_usdc)[:6])])
print('fees/volume by block', [round(-a/b,4) for a,b in zip(monthly_blocks(d.d_fees_paid)[:6], monthly_blocks(d.d_volume_usdc)[:6])])
# ROC recompute
w=pickle.load(open(S+'win.pkl','rb'))
res={}
for cid,m in w['markets'].items():
    ri=resolution_info(m)
    if ri['resolved'] and ri['closed_ts']: res[cid]=ri['closed_ts']
led=build_ledger('0xb55fa1296e6ec55d0ce53d93b9237389f11764d4', w['activity'], res)
print('ROC', capital_and_roc(led, e, 30), ' ROC ex-lump', capital_and_roc(led, e2, 30))
pk=led.daily_peak_exposure(); print('daily peak exposure last 30', pk.iloc[-31:].round(0).to_dict())
