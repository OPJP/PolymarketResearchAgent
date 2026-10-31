"""Confirmatory test on 60 fresh maker-phase markets (never inspected). Pre-registered: H4 match score = fall of the
bought outcome's last-print price over D=120 s ending fill_ts-2 s (D fixed on FITm); pass if circular-shift
permutation p < 0.01. Also: H4 rule backtest with FIT-chosen params, symmetric maker, wallet's own fills."""
import sys, json, pickle, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee')
import common
from common import *
from makerbt import maker_bt
F=pickle.load(open(W+'/frames_fresh60.pkl','rb'))
tk=F['tk'].sort_values(['cid','ts'],kind='stable').reset_index(drop=True); mk=F['mk'].sort_values(['cid','ts'],kind='stable').reset_index(drop=True)
tk['p0']=np.where(tk.outcome==0,tk.price,1-tk.price)
tk['dir0']=np.where(((tk.outcome==0)&(tk.side=='BUY'))|((tk.outcome==1)&(tk.side=='SELL')),1,-1); tk['usd']=tk['size']*tk.price
pay,active,cids=F['payouts'],F['active'],F['cids']; meta=F['meta']
event={c:str(meta.loc[c,'slug']).rsplit('-game',1)[0] for c in cids}
S=Series(tk)
def score(P,D,L=2,shift=None):
    out=np.full(len(P),np.nan)
    for cid,idx in P.groupby('cid').indices.items():
        g=P.iloc[idx]; t=g.ts.to_numpy()-L
        if shift is not None:
            a,b=active[cid]; span=max(b-a,1); t=a+((t-a+shift[cid])%span)
        v0=S.p0(cid,t)-S.p0(cid,t-D); out[idx]=np.where(g.outcome.to_numpy()==0,-v0,v0)
    return out
P=mk[mk.side=='BUY'].reset_index(drop=True); y=(P.wallet==WALLET).to_numpy()
res={'markets':len(cids),'events':len(set(event.values())),'n_pop':int(len(P)),'n_wallet':int(y.sum())}
rng=np.random.default_rng(5)
for D in (120,60):
    obs=auc(score(P,D),y); null=[]
    for i in range(500):
        sh={c:int(rng.integers(300,max(301,active[c][1]-active[c][0]-300))) for c in cids}; null.append(auc(score(P,D,shift=sh),y))
    null=np.array(null)
    res[f'match_D{D}']={'auc':float(obs),'null_mean':float(np.nanmean(null)),'null_p99':float(np.nanpercentile(null,99)),'perm_p':float((1+np.sum(null>=obs))/(1+len(null)))}
    print('match D',D,res[f'match_D{D}'],flush=True)
# precision/lift at a fixed threshold (fall >= 0.05 over 120 s)
s=score(P,120); fire=s>=0.05
res['decision_at_0.05']={'wallet_share_firing':float(fire[y].mean()),'others_share_firing':float(fire[~y].mean()),'precision':float(y[fire].mean()),'base_rate':float(y.mean())}
print(res['decision_at_0.05'])
def summ(r):
    if r.get('fills',0)==0: return {'fills':0}
    s=cluster_t(r['_pm'],event); o={k:v for k,v in r.items() if not k.startswith('_')}; o.update(s); return o
res['h4_rule_backtest']={}
for L in (0,2,5):
    for touch in (False,True):
        r=summ(maker_bt(tk,pay,active,cids,0.05,L,tick=0.001,side_rule='antimom',D=60,theta=0.05,at_touch=touch)); res['h4_rule_backtest'][f'L{L}_{"touch" if touch else "strict"}']=r
        print('H4 rule',L,touch,{k:round(v,4) if isinstance(v,float) else v for k,v in r.items() if k in('fills','usd','pnl','ret','per_market_p','per_event_p')},flush=True)
res['symmetric']={}
for (R,dlt) in ((2,0.005),(5,0.0),(10,0.05)):
    for touch in (False,True):
        r=summ(maker_bt(tk,pay,active,cids,dlt,2,R=R,tick=0.001,at_touch=touch)); res['symmetric'][f'R{R}_d{dlt}_{"touch" if touch else "strict"}']=r
        print('sym',R,dlt,touch,{k:round(v,4) if isinstance(v,float) else v for k,v in r.items() if k in('fills','usd','pnl','ret','per_market_p','per_event_p')},flush=True)
# wallet's own fills
w=pd.concat([tk[tk.wallet==WALLET].assign(role='taker'),mk[mk.wallet==WALLET].assign(role='maker')])
sg=np.where(w.side=='BUY',1,-1); w['gross']=sg*w['size']*(w.pay-w.price); w['fee']=np.where(w.role=='taker',w['size']*FEE_RATE*w.price*(1-w.price),0); w['usd']=w['size']*w.price
res['wallet_fills']=w.groupby(['role','side']).agg(n=('ts','size'),usd=('usd','sum'),gross=('gross','sum'),fee=('fee','sum')).reset_index().to_dict('records')
pmw=(w.gross-w.fee).groupby(w.cid).sum(); res['wallet_fills_net_test']=cluster_t(pmw,event); res['wallet_fills_net_total']=float(pmw.sum())
mb=w[(w.role=='maker')&(w.side=='BUY')]; pmm=mb.gross.groupby(mb.cid).sum(); res['wallet_maker_buys']=dict(ret=float(mb.gross.sum()/mb.usd.sum()),**cluster_t(pmm,event))
print(res['wallet_fills'],res['wallet_fills_net_test'],res['wallet_maker_buys'])
json.dump(res,open(W+'/confirm_fresh60.json','w'),indent=1,default=float)
