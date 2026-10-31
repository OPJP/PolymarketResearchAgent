"""Robustness of H1 FAIR-LINE TEST result: per league, per market type, game concentration,
and whether its PnL follows the wallet's own prints (footprint following)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *
from fv import market_geometry, fair_scores
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue
F,TH=120,0.04
G,P,M,split=load(); Gi=G.set_index('event_slug')
tape=Tape(P); geo=market_geometry(P,M)
B=P[(P.side=='BUY')&P.condition_id.isin(geo.keys())&~P.fit].copy().reset_index(drop=True)
B['score']=fair_scores(B,P,M,Gi,tape,geo,L=1,F=F)-B.price
X=B[(B.score>=TH)&B.payout.notna()].copy()
pnl,usd=settle(X); X['pnl']=pnl; X['cusd']=usd
# seconds since last wallet print in same game (any market), strictly before
wp=P[P.is_wallet].groupby('event_slug').ts.apply(lambda s: np.sort(s.to_numpy()))
def since_wallet(r):
    a=wp.get(r.event_slug)
    if a is None: return np.nan
    i=np.searchsorted(a,r.ts,side='left')-1
    return r.ts-a[i] if i>=0 else np.nan
X['since_wallet']=[since_wallet(r) for r in X.itertuples()]
def summ(g): 
    return pd.Series({'trades':len(g),'usd':round(g.cusd.sum()),'pnl':round(g.pnl.sum()),'ret':round(g.pnl.sum()/g.cusd.sum(),4)})
out={}
print(X.groupby('league').apply(summ)); print(X.groupby('mtype').apply(summ))
X['after_wallet']=pd.cut(X.since_wallet.fillna(1e9),[-1,10,60,600,1e10],labels=['<=10s','10-60s','1-10min','>10min/none'])
print(X.groupby('after_wallet',observed=True).apply(summ))
pg=X.groupby('event_slug').pnl.sum().sort_values()
print('per-game pnl: top5 share',pg.tail(5).sum()/pg.sum(),'bottom5',pg.head(5).sum(), 'n games',len(pg),'positive games',(pg>0).mean())
pg2=pg.iloc[:-1]; t=hac_t_test(pg2.to_numpy()); print('drop best game: t',t.statistic,'p',t.p_value)
# no-fee and zero-fee-markets-only
for lg in X.league.unique():
    x=X[X.league==lg]; g=x.groupby('event_slug').pnl.sum()
    if len(g)>=5: print(lg,'games',len(g),'p',hac_t_test(g.to_numpy()).p_value)
out={'by_league':X.groupby('league').apply(summ).to_dict('index'),'by_mtype':X.groupby('mtype').apply(summ).to_dict('index'),
     'by_time_since_wallet_print':X.groupby('after_wallet',observed=True).apply(summ).to_dict('index'),
     'top5_game_share_of_pnl':float(pg.tail(5).sum()/pg.sum()),'share_positive_games':float((pg>0).mean()),'drop_best_game_p':float(t.p_value)}
json.dump(out,open(BASE+'h1_decomp.json','w'),indent=1,default=str)
