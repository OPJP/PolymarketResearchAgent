import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.stats.persistence import persistence_report
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue, sharpe, deflated_sharpe_ratio
from polyrea.analysis.pnl import monthly_blocks, weekly_sums
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
d=pd.read_pickle(S+'daily.pkl')
e=d['d_economic_pnl'].copy()
prevfee=-d.d_fees_paid.shift(1)
rate=d.taker_reb/prevfee
steady=float(rate[(rate>0.2)&(rate<0.8)].median())
lumps=rate[rate>1].index
excess=(d.taker_reb-steady*prevfee).loc[lumps]
print('steady taker rebate rate (median of daily rebate / prev-day fees):', round(steady,4))
print('lumps:', {str(k.date()):round(v) for k,v in excess.items()})
out={'steady_rate':steady,'lumps_excess':{str(k.date()):float(v) for k,v in excess.items()}}
oct_lump=[k for k in lumps if k.month==10][0]
for nm,x in (('recorded',e),('ex_oct25_lump',e.copy().where(e.index!=oct_lump, e-excess.loc[oct_lump])),('ex_all_lumps',e-excess.reindex(e.index).fillna(0))):
    pr=persistence_report(x.to_numpy())
    mb=monthly_blocks(x); wk=weekly_sums(x)
    pre=x.iloc[:-30].to_numpy()
    r={'last30':float(x.iloc[-30:].sum()),'monthly_blocks':[float(v) for v in mb[:6]],'median_block':float(np.median(mb[:6])),'pos_weeks':float((wk>0).mean()),'pos_blocks':float(np.mean(np.array(mb[:6])>0)),
       'annual_sharpe':sharpe(x.to_numpy()),'pre_hac':hac_t_test(pre).p_value,'pre_boot':stationary_bootstrap_pvalue(pre,n_boot=4000).p_value,'dsr':deflated_sharpe_ratio(pre,500),
       'recent_p':pr.recent.p_value,'decline_p':pr.decline.p_value,'trend_p':pr.trend.p_value}
    out[nm]=r
    print(nm,{k:(round(v,4) if isinstance(v,float) else [round(z) for z in v] if isinstance(v,list) else v) for k,v in r.items()})
z=e-d.taker_reb
out['zero_tier_blocks']=[float(v) for v in monthly_blocks(z)[:6]]
out['steady_tier_blocks_ex_lumps']=[float(v) for v in monthly_blocks(z+steady*prevfee.fillna(0))[:6]]
out['top_tier_50pct_blocks']=[float(v) for v in monthly_blocks(z+0.5*prevfee.fillna(0))[:6]]
print('newcomer 0% tier 30d blocks:', [round(v) for v in out['zero_tier_blocks']])
print('at steady 44% (no lumps):', [round(v) for v in out['steady_tier_blocks_ex_lumps']])
print('at 50%:', [round(v) for v in out['top_tier_50pct_blocks']])
# daily 0%-tier series significance last 30
print('0% tier last-30 HAC', hac_t_test(z.iloc[-30:].to_numpy()), ' all history', hac_t_test(z.to_numpy()))
json.dump(out,open(S+'recheck_a1_persistence.json','w'),indent=1,default=float)
