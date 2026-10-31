"""Independent recomputation of stage A1 + persistence numbers from the cached user-pnl series."""
import json, math
import numpy as np, pandas as pd
from scipy import stats
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame
from polyrea.workflows.screen import wallet_pnl_metrics
from polyrea.stats.persistence import persistence_report
W='0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705'; AS_OF=1793318400
pm=PolymarketData(); body,_=pm.user_pnl(W)
pts=body['points']
df=daily_frame(pts, as_of=AS_OF)
d=df['d_economic_pnl'].iloc[1:]
print('days',len(d), d.index.min().date(), d.index.max().date())
def nw_t(x, lags=None):
    x=np.asarray(x,float); n=len(x); m=x.mean(); e=x-m
    L = lags if lags is not None else max(1,int(math.floor(4*(n/100)**(2/9))))
    s=e@e/n
    for k in range(1,L+1): s+=2*(1-k/(L+1))*(e[k:]@e[:-k])/n
    t=m/math.sqrt(s/n); return t, stats.norm.sf(t), L
x=d.to_numpy()
pre=x[:-30]; rec=x[-30:]
print('pre n',len(pre),'NW t/p',nw_t(pre)); print('recent 30 NW t/p',nw_t(rec), 'plain t p', stats.ttest_1samp(rec,0,alternative='greater'))
for L in (0,1,2,5,7): print(' recent lags',L,nw_t(rec,L))
print('recent30 sum',rec.sum(),'mean',rec.mean(),'pos days',(rec>0).mean())
# sharpe, weeks, months
print('annual sharpe', x.mean()/x.std(ddof=1)*math.sqrt(365))
k=len(x)//7; wk=x[len(x)-7*k:].reshape(k,7).sum(1); print('pos weeks',(wk>0).mean(), k)
blocks=[x[e-30:e].sum() for e in range(len(x),29,-30)]; print('30d blocks recent first',[round(b) for b in blocks])
# trend via OLS with NW
n=len(x); t=np.arange(n); tc=t-t.mean(); beta=tc@(x-x.mean())/(tc@tc)
res=x-x.mean()-beta*tc; u=tc*res
for L in (4,7,14,30):
    s=u@u
    for k_ in range(1,L+1): s+=2*(1-k_/(L+1))*(u[k_:]@u[:-k_])
    se=math.sqrt(s)/(tc@tc); print('trend lags',L,'beta',round(beta,2),'z',round(beta/se,3),'p',stats.norm.cdf(beta/se))
# Spearman on daily, and on weekly
print('spearman daily',stats.spearmanr(t,x)); print('spearman weekly',stats.spearmanr(np.arange(k),wk))
# trend excluding first 30 days (ramp-up month)
x2=x[30:]; n2=len(x2); t2=np.arange(n2)-np.arange(n2).mean(); b2=t2@(x2-x2.mean())/(t2@t2)
r2=x2-x2.mean()-b2*t2; u2=t2*r2; L=4; s=u2@u2
for k_ in range(1,L+1): s+=2*(1-k_/(L+1))*(u2[k_:]@u2[:-k_])
print('trend excl first 30d: beta',b2,'z',b2/(math.sqrt(s)/(t2@t2)),'p',stats.norm.cdf(b2/(math.sqrt(s)/(t2@t2))))
# PnL per volume over months (edge per $ vs size)
vol=df['d_volume_usdc'].iloc[1:].to_numpy(); fees=df['d_fees_paid'].iloc[1:].to_numpy(); inc=df['d_wallet_income'].iloc[1:].to_numpy()
tr=df['d_trade_pnl'].iloc[1:].to_numpy()
for e in range(len(x),29,-30):
    sl=slice(e-30,e)
    print(f'block ending {d.index[e-1].date()}: pnl {x[sl].sum():>10.0f} vol {vol[sl].sum():>12.0f} pnl/vol {x[sl].sum()/vol[sl].sum():.4f} fees {fees[sl].sum():>9.0f} income {inc[sl].sum():>9.0f} pnl_ex_income {x[sl].sum()-inc[sl].sum():>10.0f}')
pr=persistence_report(x)
print('repo persistence:', pr.recent, pr.trend, pr.decline, pr.cusum_break, sep='\n')
m=wallet_pnl_metrics(pts, AS_OF); print({k:m[k] for k in ('last_30d_pnl','median_month_pnl','annual_sharpe','share_positive_weeks','share_positive_months','p_pre','p_boot_pre')})
# rebate dependence last 30d
last=df.iloc[-30:]
print('last30 taker/maker income: wallet_income',last['d_wallet_income'].sum(),'fees_paid',last['d_fees_paid'].sum(), 'econ',last['d_economic_pnl'].sum())
raw=pd.DataFrame(pts); raw=raw[raw.timestamp<=AS_OF]; raw=raw[raw.timestamp%86400==0]
a=raw[raw.timestamp==AS_OF-30*86400].iloc[0]; b=raw[raw.timestamp==AS_OF].iloc[0]
for f in ('taker_rebate','maker_rebate','reward_income','fees_paid','economic_pnl','trade_pnl','volume_usdc'):
    print(' ',f, round(b[f]-a[f],1))
print('  observed taker rebate rate', (b['taker_rebate']-a['taker_rebate'])/-(b['fees_paid']-a['fees_paid']))
