import sys, pickle, json, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import os; os.chdir('/home/user/PolymarketResearchAgent')
import pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.updown import Window
from polyrea.workflows.updown_study import sample_blocks, DAY
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
AS_OF=1793318400
d=pickle.load(open(S+'win.pkl','rb')); mk=d['markets']
P5=pickle.load(open(S+'period_btc_15m.pkl','rb'))
def hourly_windows(blocks):
    out=[]
    for cid,m in mk.items():
        s=m.get('slug','')
        if not s.startswith('bitcoin-up-or-down-'): continue
        st=int(pd.Timestamp(m['eventStartTime']).timestamp()); en=int(pd.Timestamp(m['endDate']).timestamp())
        if en-st!=3600: continue
        if not any(a<=st and en<=b for a,b in blocks): continue
        tok=json.loads(m['clobTokenIds']); oc=json.loads(m['outcomes']); pr=[float(x) for x in json.loads(m['outcomePrices'])]
        if oc[:2]!=['Up','Down']: continue
        res=m.get('umaResolutionStatus')=='resolved' and max(pr)>=0.999
        fs=m.get('feeSchedule') or {}
        out.append(Window(cid,'btc','1h',st,en,str(tok[0]),str(tok[1]),twap_seconds=1,fee_rate=float(fs.get('rate',0.07)) if m.get('feesEnabled') else 0.0, up_payout=pr[0] if res else None))
    return sorted(out,key=lambda w:w.start_ts)
pm=PolymarketData()
res={}
for per in ('fit','test'):
    ws=hourly_windows(P5[per]['blocks'])
    t=time.time()
    def tape(w):
        rows,_,cov=pm.market_trades(w.condition_id,start=w.start_ts-600,end=w.end_ts+60,taker_only=True)
        return w.condition_id,rows,cov.status
    with ThreadPoolExecutor(3) as ex: tl=list(ex.map(tape,ws))
    print(per,'hourly windows',len(ws),'tape rows',sum(len(r) for _,r,_ in tl),'partial',sum(s=='partial' for *_,s in tl),'secs',round(time.time()-t,1),flush=True)
    res[per]={'windows':ws,'tapes':{c:r for c,r,_ in tl}}
pickle.dump(res,open(S+'period_btc_1h.pkl','wb'))
