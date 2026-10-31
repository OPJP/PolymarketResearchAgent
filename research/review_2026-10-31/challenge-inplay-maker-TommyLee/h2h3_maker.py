"""H2 favourite-side maker, H3 momentum-lean maker (bid only the outcome that just won the tape move), H3b lean
(tight on favourite, wide on underdog). FIT picks parameters at L=2 (strict trade-through, tick 0.001 = market tick);
TEST evaluates at L in {0,2,5,10}, strict and at-touch."""
import sys, json, itertools, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
from common import *; from makerbt import maker_bt
tk,mk,pay,active,fit,test,split,event=load()
fc,tc=sorted(fit),sorted(test)
def summ(r):
    if r.get('fills',0)==0: return {'fills':0}
    s=cluster_t(r['_pm'],event); o={k:v for k,v in r.items() if not k.startswith('_')}; o.update(s); return o
fams={
 'H2_fav':[dict(side_rule='fav',theta=th,delta=d) for th in (0.55,0.65,0.75,0.85) for d in (0.005,0.01,0.02,0.03,0.05)],
 'H3_mom':[dict(side_rule='mom',D=D,theta=th,delta=d) for D in (30,60,120) for th in (0.02,0.05,0.10) for d in (0.005,0.01,0.02,0.05)],
 'H3b_lean':[dict(side_rule='lean',delta=d,delta_dog=dd) for d in (0.005,0.01,0.02) for dd in (0.03,0.05,0.10)],
}
res={}
for fam,grid in fams.items():
    scan=[]
    for p in grid:
        r=summ(maker_bt(tk,pay,active,fc,L=2,tick=0.001,**p)); scan.append((p,r))
    ok=[(p,r) for p,r in scan if r.get('fills',0)>=100]
    bp,br=max(ok,key=lambda x:x[1]['per_market_t'])
    print(fam,'FIT best',bp,{k:round(v,4) if isinstance(v,float) else v for k,v in br.items() if k in('fills','usd','pnl','ret','per_market_t','per_market_p','per_event_p')})
    print('   FIT any p<0.05:',[ (p, round(r['per_market_p'],3)) for p,r in ok if r['per_market_p']<0.05])
    tst={}
    for L in (0,2,5,10):
        for touch in (False,True):
            r=summ(maker_bt(tk,pay,active,tc,L=L,tick=0.001,at_touch=touch,**bp)); tst[f'L{L}_{"touch" if touch else "strict"}']=r
            print('   TEST',L,'touch' if touch else 'strict',{k:round(v,4) if isinstance(v,float) else v for k,v in r.items() if k in('fills','usd','pnl','ret','maker_rebate_est','per_market_p','per_event_p','per_event_boot_p')})
    res[fam]={'fit_scan':[{'params':p,**{k:v for k,v in r.items() if k in('fills','usd','pnl','ret','per_market_t','per_market_p')}} for p,r in scan],'chosen':bp,'fit_best':br,'test':tst}
json.dump(res,open(W+'/h2h3_maker.json','w'),indent=1,default=float)
