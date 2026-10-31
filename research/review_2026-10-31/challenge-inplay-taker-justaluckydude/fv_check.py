import sys, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *
from polyrea.stats.significance import hac_t_test
B=pd.read_pickle(BASE+'buys_fv.pkl')
for F in (30,120,600):
    s=B[f'fair_L1_F{F}']-B.price; o=~B.is_wallet
    print(F,'others |score| median',np.nanmedian(np.abs(s[o])).round(4),'corr fair-price others',np.corrcoef(B.loc[o&s.notna(),f'fair_L1_F{F}'],B.loc[o&s.notna(),'price'])[0,1].round(4))
# calibration of fair: among others' prints, payout vs fair
b=B[B.payout.notna()&B.fair_L1_F120.notna()]
b['fb']=pd.cut(b.fair_L1_F120,np.linspace(0,1,11))
print(b.groupby('fb',observed=True).agg(n=('payout','size'),fair=('fair_L1_F120','mean'),price=('price','mean'),win=('payout','mean')).round(3))
# backtest grid on FIT: buy every BUY print (any wallet) with score>=theta, cap $100
B=B[B.payout.notna()]
for F in (30,120,600):
    for th in (0.0,0.02,0.04,0.06,0.1,0.15):
        for part in ('fit','test') if False else ('fit',):
            x=B[B.fit & ((B[f'fair_L1_F{F}']-B.price)>=th)]
            if len(x)<50: continue
            pnl,usd=settle(x); x=x.assign(pnl=pnl)
            pg=x.groupby('event_slug').pnl.sum()
            t=hac_t_test(pg.to_numpy())
            print(f'FIT F{F} th{th}: trades {len(x)} usd {usd.sum():.0f} ret {pnl.sum()/usd.sum():+.4f} games {len(pg)} t {t.statistic:.2f} p {t.p_value:.3f}')
