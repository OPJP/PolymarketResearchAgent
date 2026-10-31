"""H6 GOAL rule (N=300, theta=0.15, frozen from FIT match-fit): moneyline-clock shift null, latency, concentration, FIT+TEST pooled."""
import sys, json, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S)
src=open(f'{S}/h6_soccer_lag.py').read().split("F=B[B.period=='FIT']")[0]
sys.argv=[sys.argv[0],S]; exec(src)
from evalkit import backtest, perm_test
N,th=300,0.15
def hitf(x,mlcol): return (x.outcome=='Over')&(x[mlcol]>=th)&(x[f'own{N}']<th/2)&(x.price>=0.05)&(x.price<=0.95)
B['hit']=hitf(B,f'ml{N}')
T=B[B.period=='TEST']; F=B[B.period=='FIT']
out={}
obs=T.hit[T.is_wallet].mean()-T.hit[~T.is_wallet].mean(); null=[]
rng=np.random.default_rng(4)
for _ in range(200):
    B['mls']=ml_move(N,shift=True,rng=rng); h=hitf(B,'mls'); tt=B.period=='TEST'
    null.append(h[tt&B.is_wallet].mean()-h[tt&~B.is_wallet].mean())
null=np.array(null); out['test_shift_null']={'obs':float(obs),'null_p95':float(np.percentile(null,95)),'perm_p':float((1+(null>=obs).sum())/(len(null)+1))}
out['fit_backtest']=backtest(F[F.hit]); out['test_backtest']=backtest(T[T.hit]); out['pooled_backtest']=backtest(B[B.hit])
out['test_backtest_excl_wallet']=backtest(T[T.hit&~T.is_wallet])
sel=T[T.hit&T.payout.notna()].copy(); usd=np.minimum(sel['size']*sel.price,100); sh=usd/sel.price
sel['pnl']=sh*sel.payout-usd-sel.fee_rate*sel.price*(1-sel.price)*sh
pe=sel.groupby('event_slug').pnl.sum().sort_values()
out['test_concentration']={'events':int(len(pe)),'top3_share':float(pe.tail(3).sum()/pe.sum()),'share_events_positive':float((pe>0).mean()),'pnl_without_top3':float(pe.iloc[:-3].sum())}
# latency: recompute ml and own features at larger L
lat={}
for LL in (5,10,30):
    globals()['L']=LL; mlx=ml_move(N)
    # own move at latency LL from the prints table is not stored; approximate with the L=2 own move (conservative only for ml)
    h=(B.outcome=='Over')&(mlx>=th)&(B[f'own{N}']<th/2)&(B.price>=0.05)&(B.price<=0.95)
    lat[str(LL)]={k:backtest(B[h&(B.period=='TEST')]).get(k) for k in ('trades','ret','per_event_p')}
out['latency_ml_only']=lat
print(json.dumps(out,indent=1,default=float)); json.dump(out,open(f'{S}/h6_robust_result.json','w'),indent=1,default=float)
