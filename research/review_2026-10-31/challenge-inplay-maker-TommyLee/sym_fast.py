"""Robustness of the recorded result: symmetric two-sided maker on the real 0.001 tick, faster requote (R=2,5 s),
tight offsets, strict and at-touch fills. Chosen on FIT (L=2, strict), reported on TEST."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *; from makerbt import maker_bt
tk,mk,pay,active,fit,test,split,event=load()
fc,tc=sorted(fit),sorted(test)
def summ(r):
    if r.get('fills',0)==0: return {'fills':0}
    s=cluster_t(r['_pm'],event); o={k:v for k,v in r.items() if not k.startswith('_')}; o.update(s); return o
rows=[]
for R in (2,5,10):
    for d in (0.0,0.002,0.005,0.01,0.02):
        for touch in (False,True):
            for half,cs in (('FIT',fc),('TEST',tc)):
                r=summ(maker_bt(tk,pay,active,cs,d,L=2,R=R,tick=0.001,at_touch=touch))
                rows.append({'R':R,'delta':d,'fill':'touch' if touch else 'strict','half':half,**{k:r.get(k) for k in ('fills','usd','pnl','ret','maker_rebate_est','per_market_p','per_event_p')}})
df=pd.DataFrame(rows); pd.set_option('display.width',250)
print(df.round(4).to_string())
df.to_csv(W+'/sym_fast.csv',index=False)
