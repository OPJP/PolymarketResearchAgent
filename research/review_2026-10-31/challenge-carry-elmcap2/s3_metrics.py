import json, pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.workflows.screen import wallet_pnl_metrics, apply_criteria
from polyrea.adapters.polymarket import PolymarketData
from polyrea.stats.persistence import persistence_report
from polyrea.stats import significance as S
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
W='0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'; AS_OF=1793318400
pm=PolymarketData()
body,src=pm.user_pnl(W)
m=wallet_pnl_metrics(body['points'], AS_OF)
for k in ['history_days','last_30d_pnl','median_month_pnl','share_positive_months','annual_sharpe','share_positive_weeks','hac_t_pre','p_pre','p_boot_pre','incentive_share']:
    print(k, m[k])
print('holm approx p_pre*500 =', min(1,m['p_pre']*500))
df=daily_frame(body['points'], as_of=AS_OF); d=df['d_economic_pnl'].iloc[1:]
print('sharpe recompute', S.sharpe(d.to_numpy()))
# sensitivity: drop the two Fed days
top=d.sort_values(ascending=False)
print('top 5 days', top.head(5).round(0).to_dict())
dd=d.drop(top.index[:2])
print('last30 excluding 2 Fed days', d.iloc[-30:].drop(top.index[:2], errors='ignore').sum())
print('sharpe without top2 days', S.sharpe(dd.to_numpy()))
# share of total pnl from top 10 days
print('top10 days share of total', top.head(10).sum()/d.sum())
rep=persistence_report(d.to_numpy(), recent_days=30)
print('persistence recent', rep.recent if hasattr(rep,'recent') else rep)
# recent 30 d HAC t
print('recent30 hac', S.hac_t_test(d.iloc[-30:].to_numpy()))
print('recent30 boot', S.stationary_bootstrap_pvalue(d.iloc[-30:].to_numpy(), n_boot=4000))
# monthly blocks
mb=monthly_blocks(d); print('n blocks', len(mb), 'positive share', np.mean([x>0 for x in mb]), 'last 8 blocks', [round(x) for x in mb[:8]])
# trade pnl excluding income
tp=df['d_trade_pnl'].iloc[1:]; print('trade-only sharpe', S.sharpe(tp.to_numpy()), 'trade last30', tp.iloc[-30:].sum())
print('income 30d', df['d_wallet_income'].iloc[-30:].sum(), 'income all', df['d_wallet_income'].iloc[1:].sum())
json.dump({k:(v if not isinstance(v,(np.floating,)) else float(v)) for k,v in m.items() if k!='cumulative_weekly'}, open(OUT+'metrics_recomputed.json','w'), default=str, indent=1)
