"""H6 SOCCER GOAL-LAG: a goal moves the event's moneyline (win/draw Yes) markets; totals markets may lag.
GOAL rule: buy Over at a totals BUY print when max |dYes| across the event's moneyline markets over (t-L-N, t-L]
>= theta while the Over price itself moved < theta/2 over the same window.
NO-GOAL rule: buy Under when every moneyline market moved < eps over the last M s (no goal) and minute >= m1.
All inputs are public Polymarket tapes known by t-L; FIT/TEST split by game start (Oct 15)."""
import sys, json, pickle, itertools, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S)
from evalkit import backtest, perm_test
L=2
P=pd.read_pickle(f'{S}/prints_L2.pkl')
B=P[(P.side=='BUY')&(P.minutes>=0)&(P.set=='soccer_totals')&P.outcome.isin(['Over','Under'])].copy().reset_index(drop=True)
ml=pickle.load(open(f'{S}/soccer_ml.pkl','rb'))
mls={}
for slug,m,rows in ml['tapes']:
    if not rows: continue
    tok=[str(x) for x in json.loads(m['clobTokenIds'])]
    b=[r for r in rows if r.get('side')=='BUY' and str(r.get('asset')) in tok]
    if not b: continue
    ts=np.array([int(r['timestamp']) for r in b]); k=np.array([tok.index(str(r['asset'])) for r in b]); p=np.array([float(r['price']) for r in b])
    py=np.where(k==0,p,1-p); o=np.argsort(ts,kind='stable'); mls.setdefault(slug,[]).append((ts[o],py[o]))
B=B[B.event_slug.isin(mls)].reset_index(drop=True)
def last_at(ts,p,tq):
    j=np.searchsorted(ts,tq,side='right')-1; return np.where(j>=0,p[np.clip(j,0,None)],np.nan)
def ml_move(N,shift=None,rng=None):
    out=np.zeros(len(B))
    for s,idx in B.groupby('event_slug').indices.items():
        tq=B.ts.to_numpy()[idx]; mx=np.zeros(len(idx)); sh=0 if shift is None else int(rng.integers(300,1500))*int(rng.choice([-1,1]))
        for ts,py in mls[s]:
            ts=ts+sh; d=np.abs(last_at(ts,py,tq-L)-last_at(ts,py,tq-L-N)); mx=np.fmax(mx,np.nan_to_num(d))
        out[idx]=mx
    return out
# own Over price move (token frame: Over price)
overp=np.where(B.outcome=='Over',1,-1)
for N in (30,60,120,300,600):
    B[f'ml{N}']=ml_move(N)
    B[f'own{N}']=np.where(B.outcome=='Over',B[f'mom{N}'] if f'mom{N}' in B else 0,-B[f'mom{N}'] if f'mom{N}' in B else 0) if N in (30,60,120,300) else np.nan
F=B[B.period=='FIT']; T=B[B.period=='TEST']
out={'events_fit':int(F.event_slug.nunique()),'events_test':int(T.event_slug.nunique()),'wallet_fit':int(F.is_wallet.sum()),'wallet_test':int(T.is_wallet.sum())}
def goal_hit(x,N,th): return (x.outcome=='Over')&(x[f'ml{N}']>=th)&(x[f'own{N}']<th/2)&(x.price>=0.05)&(x.price<=0.95)
def quiet_hit(x,M,eps,m1): return (x.outcome=='Under')&(x[f'ml{M}']<eps)&(x.minutes>=m1)&(x.price>=0.05)&(x.price<=0.95)
for nm,fn,grid in [('GOAL',goal_hit,list(itertools.product([30,60,120,300],[0.03,0.06,0.1,0.15]))),
                   ('NOGOAL',quiet_hit,list(itertools.product([120,300,600],[0.01,0.02,0.04],[0,20,45,60,75])))]:
    rows=[]
    for g in grid:
        h=fn(F,*g)
        if h.sum()<30: continue
        bt=backtest(F[h]); rows.append({'params':g,'fit_t':bt['per_event_t'],'fit_ret':bt['ret'],'fit_trades':bt['trades'],'fit_match_diff':float(h[F.is_wallet].mean()-h[~F.is_wallet].mean())})
    R=pd.DataFrame(rows); res={}
    for sel,b in [('profit_fit',R.sort_values('fit_t',ascending=False).iloc[0]),('match_fit',R.sort_values('fit_match_diff',ascending=False).iloc[0])]:
        T2=T.copy(); T2['hit']=fn(T2,*b.params)
        res[sel]={'params':list(b.params),'fit':b.drop('params').to_dict(),'test_backtest':backtest(T2[T2.hit]),'test_match':perm_test(T2,'hit',n_perm=1000)}
    out[nm]=res
print(json.dumps(out,indent=1,default=float))
json.dump(out,open(f'{S}/h6_soccer_lag_result.json','w'),indent=1,default=float)
