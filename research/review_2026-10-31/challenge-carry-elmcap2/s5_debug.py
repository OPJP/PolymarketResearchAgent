import pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.analysis.profile import resolution_info
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
d=pickle.load(open(OUT+'win.pkl','rb')); win=d['win']; led=win['ledger']; mk=win['markets']
fed=['0xdf9bf27ee5757c55b44b8b9826ddc9ec3a8809aa3278634c45edbb7fc8f1a3e3','0x12aa13b3da17ceae1b0a59b5d5b77121e91bb79b4bb0b52bf6543ed3f8d0953b','0x9cf563d7b55aa9aa876d5d7e55126347eee473f0ae56d799e325fdef2bf25297','0xde5d75ab7702875623ba509bc923241e1211da74a113521b3b70ddac930d7316']
for c in fed:
    m=mk[c]; ri=resolution_info(m)
    print(c[:10], m.get('closedTime'), m.get('umaResolutionStatus'), m.get('closed'), m.get('outcomePrices'), ri['closed_ts'])
for a,p in led.positions.items():
    if p.condition_id in fed:
        print(a[:10], p.outcome_index, round(p.shares), round(p.cost), p.opened_at, p.closed_at, p.close_kind, round(p.bought_usdc))
act=win['activity']
ty=pd.Series([r.get('type') for r in act]).value_counts(); print(ty)
ev=sorted(led.exposure_events); ts=np.array([e[0] for e in ev]); dl=np.array([e[1] for e in ev])
lvl=np.cumsum(dl)
for t0 in [1793217600, 1793217700, 1793217800, 1793260000, 1793318000]:
    i=np.searchsorted(ts,t0); print(t0, pd.to_datetime(t0,unit='s'), lvl[i-1] if i>0 else None)
big=[(pd.to_datetime(t,unit='s'),round(x)) for t,x in ev if abs(x)>200000]; print(big)
# total buys/sells in window
