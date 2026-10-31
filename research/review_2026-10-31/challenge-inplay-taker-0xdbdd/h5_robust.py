"""H5 robustness on TEST: moneyline-clock shift null for the match, latency degradation, per-league split."""
import sys, json, pickle, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S)
from evalkit import backtest, perm_test
d=pickle.load(open(f'{S}/espn_games200.pkl','rb'))
games={e['event_slug']:e for e in d['games']}
A=pd.concat(d['frames'],ignore_index=True).rename(columns={'condition_id':'cid'})
A=A[A.side_kind.isin(['home','away'])].copy()
split=int(np.median([e['start'] for e in d['games']]))
A['period']=np.where(A.event_slug.map(lambda s:games[s]['start'])<split,'FIT','TEST')
A=A[A.period=='TEST']
def home_series(df):
    x=df.sort_values('ts'); p=np.where(x.side_kind=='home',x.price,1-x.price); return x.ts.to_numpy(),p
def last_at(ts,p,tq):
    j=np.searchsorted(ts,tq,side='right')-1; return np.where(j>=0,p[np.clip(j,0,None)],np.nan)
def build(N,L,shift_fn=None):
    parts=[]
    for s,g in A.groupby('event_slug'):
        ml=g[g.mtype=='moneyline']
        if ml.empty: continue
        if ml.cid.nunique()>1: ml=ml[ml.cid==ml.cid.value_counts().index[0]]
        mts,mp=home_series(ml); sh=shift_fn(s) if shift_fn else 0; mts=mts+sh
        for cid,sp in g[g.mtype=='spreads'].groupby('cid'):
            sts,spp=home_series(sp); x=sp.copy(); t=x.ts.to_numpy(); sgn=np.where(x.side_kind=='home',1,-1)
            x['lag']=sgn*((last_at(mts,mp,t-L)-last_at(mts,mp,t-L-N))-(last_at(sts,spp,t-L)-last_at(sts,spp,t-L-N)))
            parts.append(x)
    X=pd.concat(parts,ignore_index=True); X=X[X.payout.notna()].reset_index(drop=True)
    X['hit']=(X.lag>=0.0001)&(X.price>=0.05)&(X.price<=0.95); return X
out={}
rng=np.random.default_rng(9)
for N in (60,120):
    X=build(N,2); obs=X.hit[X.is_wallet].mean()-X.hit[~X.is_wallet].mean(); null=[]
    for _ in range(200):
        shifts={}
        Y=build(N,2,lambda s: shifts.setdefault(s,int(rng.integers(300,1500))*int(rng.choice([-1,1]))))
        null.append(Y.hit[Y.is_wallet].mean()-Y.hit[~Y.is_wallet].mean())
    null=np.array(null)
    out[f'N{N}']={'obs_diff':float(obs),'shift_null_p95':float(np.percentile(null,95)),'shift_null_mean':float(null.mean()),'shift_perm_p':float((1+(null>=obs).sum())/(len(null)+1)),
                  'latency':{str(L):{k:backtest(build(N,L).pipe(lambda z:z[z.hit])).get(k) for k in ('trades','ret','per_event_p','boot_p')} for L in (2,5,10,20,30)}}
    X['league']=X.event_slug.str.split('-').str[0]
    out[f'N{N}']['by_league']={lg:{k:v for k,v in backtest(g[g.hit]).items() if k in ('trades','events','ret','per_event_p')} for lg,g in X.groupby('league')}
print(json.dumps(out,indent=1,default=float))
json.dump(out,open(f'{S}/h5_robust_result.json','w'),indent=1,default=float)
