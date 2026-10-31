import pickle, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.analysis.ledger import build_ledger
from polyrea.analysis.profile import resolution_info
from polyrea.adapters.polymarket import PolymarketData
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
W='0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'; AS_OF=1793318400
d=pickle.load(open(OUT+'win.pkl','rb')); win=d['win']; act=win['activity']; mk=win['markets']
res_ts={c: resolution_info(m)['closed_ts'] for c,m in mk.items() if resolution_info(m)['resolved'] and resolution_info(m)['closed_ts']}
def stats(led, label):
    s=led.exposure_series()
    start=pd.Timestamp(AS_OF-30*86400,unit='s',tz='UTC'); end=pd.Timestamp(AS_OF,unit='s',tz='UTC')
    prev=s[s.index<=start]; lvl0=float(prev.iloc[-1]) if len(prev) else 0.0
    sw=s[(s.index>start)&(s.index<=end)]
    t=np.r_[start.timestamp(), [x.timestamp() for x in sw.index], end.timestamp()]; lv=np.r_[lvl0, sw.values]
    dur=np.diff(t); twa=float((lv*dur).sum()/dur.sum())
    dp=led.daily_peak_exposure(); dp=dp[(dp.index>start)&(dp.index<=end)]
    out=dict(label=label, peak=float(sw.max()), peak_time=str(sw.idxmax()), p95=float(np.percentile(dp,95)), twa=twa, roc_peak=242046.5/float(sw.max()), roc_p95=242046.5/float(np.percentile(dp,95)), roc_twa=242046.5/twa)
    print(out); return out
r=[]
r.append(stats(win['ledger'],'as recorded (splits counted)'))
# drop SPLIT/MERGE rows of the JD Vance complete-set parking market (no trades there): complete sets carry no outcome risk
jd='0x7ad403c3508f8e3912940fd1a913f227591145ca0614074208e0b962d5fcc422'
act2=[x for x in act if not (x.get('type') in ('SPLIT','MERGE') and x.get('conditionId')==jd)]
led2=build_ledger(W, act2, res_ts)
r.append(stats(led2,'complete sets excluded'))
# fed only sub-book
fed={'0xdf9bf27ee5757c55b44b8b9826ddc9ec3a8809aa3278634c45edbb7fc8f1a3e3','0x12aa13b3da17ceae1b0a59b5d5b77121e91bb79b4bb0b52bf6543ed3f8d0953b','0x9cf563d7b55aa9aa876d5d7e55126347eee473f0ae56d799e325fdef2bf25297','0xde5d75ab7702875623ba509bc923241e1211da74a113521b3b70ddac930d7316'}
p=pd.read_csv('/home/user/PolymarketResearchAgent/research/wallets/'+W+'/per_market.csv.gz')
fp=p[p.condition_id.isin(fed)]; print('Fed markets cost', fp.cost.sum(), 'pnl', fp.pnl.sum(), 'return', fp.pnl.sum()/fp.cost.sum())
pos,src=PolymarketData().positions(W)
pdf=pd.DataFrame(pos)
print('positions rows', len(pdf), 'cols', list(pdf.columns)[:30])
pdf['initialValue']=pd.to_numeric(pdf.initialValue); pdf['currentValue']=pd.to_numeric(pdf.currentValue)
print('sum initialValue', pdf.initialValue.sum(), 'sum currentValue', pdf.currentValue.sum())
print(pdf.sort_values('initialValue',ascending=False)[['title','outcome','size','avgPrice','initialValue','currentValue','endDate']].head(25).to_string())
# which current positions are unknown to the ledger (opened before warm-up)
known=set(a for a,pp in win['ledger'].positions.items() if pp.bought_shares>0)
pdf['in_ledger']=pdf.asset.astype(str).isin(known)
print('initialValue of positions not bought inside ledger window', pdf[~pdf.in_ledger].initialValue.sum())
print(pdf[~pdf.in_ledger].sort_values('initialValue',ascending=False)[['title','outcome','size','avgPrice','initialValue','endDate']].head(15).to_string())
pdf.to_csv(OUT+'positions_now.csv',index=False)
json.dump(r, open(OUT+'capital_variants.json','w'), indent=1)
