"""H7 follow-up: timing of the wallet's soccer buys relative to ESPN goal wallclock, and the after-fee return of Over
prints by seconds after the goal (all takers vs the wallet). Shows where any goal-reaction edge sits in time."""
import sys, json, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S)
src=open(f'{S}/h7_espn_soccer.py').read().split("F=A[A.period=='FIT']")[0]
sys.argv=[sys.argv[0],S]; exec(src)
from evalkit import backtest
sg=since_goal(A,0); A['since']=sg
# wallet lag histogram (all buys) relative to latest goal wallclock, and relative to nearest goal (either side)
lags=[]
for s,g in A[A.is_wallet].groupby('event_slug'):
    gl=np.array(G[s]['goals'])
    for t in g.ts: 
        d=t-gl; d=d[np.abs(d)<=300]; lags.extend(d.tolist())
h,e=np.histogram(lags,bins=[-300,-120,-60,-30,-10,0,5,10,20,30,60,120,300])
out={'wallet_lag_hist_vs_goal_wallclock':{f'[{a},{b})':int(c) for a,b,c in zip(e[:-1],e[1:],h)}}
bins=[(0,5),(5,10),(10,20),(20,30),(30,60),(60,120),(120,300),(300,10**7)]
rows={}
for lo,hi in bins:
    x=A[(A.outcome=='Over')&(A.since>=lo)&(A.since<hi)&(A.price>=0.05)&(A.price<=0.95)]
    bo=backtest(x[~x.is_wallet]); bw=backtest(x[x.is_wallet])
    rows[f'{lo}-{hi}s']={'others_trades':bo.get('trades'),'others_ret':bo.get('ret'),'others_p':bo.get('per_event_p'),'wallet_trades':bw.get('trades'),'wallet_ret':bw.get('ret')}
out['over_return_by_seconds_after_goal']=rows
# wallet own soccer-totals PnL split: within 300 s after a goal vs other times
wa=A[A.is_wallet]
for nm,mask in [('within300_after_goal',(wa.since>=0)&(wa.since<300)),('other_times',~((wa.since>=0)&(wa.since<300)))]:
    out[f'wallet_{nm}']=backtest(wa[mask])
print(json.dumps(out,indent=1,default=float)); json.dump(out,open(f'{S}/h7_lag_result.json','w'),indent=1,default=float)
