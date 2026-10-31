"""H1 FAIR-LINE on TEST: pre-registered from FIT (max per-game t): F=120 s, theta=0.04, L=1 s.
(a) match: AUC(score) wallet vs other takers on TEST, null = per-game sibling-tape time shift +-(300..1500)s.
(b) backtest: buy every BUY print with score>=theta (cap $100, market fee), per-game HAC t + bootstrap.
(c) latency L=2,5,10,30 s and 'exclude wallet's own prints as fill opportunities'."""
import sys, json, time, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *
from fv import market_geometry, fair_scores
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue, permutation_pvalue
F,TH=120,0.04
G,P,M,split=load(); Gi=G.set_index('event_slug')
tape=Tape(P); geo=market_geometry(P,M)
B=P[(P.side=='BUY')&P.condition_id.isin(geo.keys())&~P.fit].copy().reset_index(drop=True)
y=B.is_wallet.to_numpy()
out={'params':{'F':F,'theta':TH,'L':1}}
def bt(x):
    x=x[x.payout.notna()]
    pnl,usd=settle(x); x=x.assign(pnl=pnl); pg=x.groupby('event_slug').pnl.sum()
    t=hac_t_test(pg.to_numpy()); bp=stationary_bootstrap_pvalue(pg.to_numpy(),n_boot=2000).p_value
    return {'trades':int(len(x)),'games':int(len(pg)),'usd':float(usd.sum()),'pnl':float(pnl.sum()),'ret':float(pnl.sum()/usd.sum()),'t':float(t.statistic),'p':float(t.p_value),'boot_p':float(bp)}
for L in (1,2,5,10,30):
    f=fair_scores(B,P,M,Gi,tape,geo,L=L,F=F); s=f-B.price.to_numpy()
    if L==1:
        out['test_auc']=float(auc(y,s)); out['coverage_wallet']=float(np.isfinite(s[y]).mean())
        sel=s>=TH
        out['precision']=float(y[sel].mean()); out['base_rate']=float(y[np.isfinite(s)].mean()); out['recall']=float(sel[y].mean())
        out['wallet_share_flagged']=float((s[y]>=TH).mean()); out['others_share_flagged']=float((s[~y]>=TH).mean())
        out['backtest_L1']=bt(B[sel]); out['backtest_L1_excl_wallet_prints']=bt(B[sel&~y])
        s1=s
    else:
        out[f'backtest_L{L}']=bt(B[s>=TH])
    print(L, {k:v for k,v in out.items() if k.startswith('backtest') or k=='test_auc'}, flush=True)
# permutation null for AUC
rng=np.random.default_rng(7); null=[]; t0=time.time()
evs=B.event_slug.unique()
for i in range(60):
    sh={e:int(rng.integers(300,1500))*int(rng.choice([-1,1])) for e in evs}
    f=fair_scores(B,P,M,Gi,tape,geo,L=1,F=F,shift=sh); null.append(auc(y,f-B.price.to_numpy()))
null=np.array([x for x in null if np.isfinite(x)])
out['auc_null_mean']=float(null.mean()); out['auc_null_p95']=float(np.percentile(null,95)); out['auc_perm_p']=float(permutation_pvalue(out['test_auc'],null)); out['n_perm']=int(len(null))
out['wallet_replay_test_same_games']=bt(B[y])
print(json.dumps(out,indent=1))
json.dump(out,open(BASE+'h1_fairline_test.json','w'),indent=1)
