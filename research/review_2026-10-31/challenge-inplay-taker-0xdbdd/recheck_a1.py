import sys, json, numpy as np
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.screen import wallet_pnl_metrics
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums
from polyrea.stats import significance as S
W='0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
pm=PolymarketData()
body,src=pm.user_pnl(W, max_age=None)
print('src', src.fetched_at, src.cached, src.body_sha256[:12])
pts=body['points']
# as_of used by screen = day of fetch 2026-10-30 midnight UTC?
for as_of in (1793318400, 1793318400+86400):
    m=wallet_pnl_metrics(pts, as_of)
    print(as_of, {k:m[k] for k in ['history_days','last_30d_pnl','median_month_pnl','share_positive_months','annual_sharpe','share_positive_weeks','p_pre','p_boot_pre','hac_t_pre','pre_selection_days']})
df=daily_frame(pts, as_of=1793318400+86400)
d=df['d_economic_pnl'].iloc[1:]
print('last day', d.index.max(), 'n', len(d))
w=weekly_sums(d); print('weeks', len(w), (w>0).mean(), 'last 8 weeks', np.round(w[-8:]))
mb=monthly_blocks(d); print('blocks', np.round(mb))
# Holm: p_holm = p_pre * rank multiplier; check bound p_pre*500
m=wallet_pnl_metrics(pts, 1793318400+86400)
print('Bonferroni bound p_pre*500 =', m['p_pre']*500)
# DSR recompute: per-day sharpe vs expected max of 500 noise
from scipy import stats
T=len(d); sr=d.mean()/d.std(ddof=1); g3=stats.skew(d); g4=stats.kurtosis(d,fisher=False)
N=500; emc=0.5772156649
sd=1/np.sqrt(T-1)
sr0=sd*((1-emc)*stats.norm.ppf(1-1/N)+emc*stats.norm.ppf(1-1/(N*np.e)))
z=(sr-sr0)*np.sqrt(T-1)/np.sqrt(1-g3*sr+(g4-1)/4*sr**2)
print('SR/day',sr,'SR0',sr0,'DSR',stats.norm.cdf(z), 'skew',g3,'kurt',g4)
# trade_pnl (excluding rebates) last 30
dt=df['d_trade_pnl'].iloc[1:]; print('trade pnl last30', dt.iloc[-30:].sum(), 'income last30', df['d_wallet_income'].iloc[-30:].sum(), 'fees', df['d_fees_paid'].iloc[-30:].sum())
# weekly with 30-day: weekly sums last 30 days
print('last 30 daily', np.round(d.iloc[-30:].values))
