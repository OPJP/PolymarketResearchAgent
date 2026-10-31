"""H5 CROSS-MARKET LAG: in the same game, the moneyline leads and spread markets lag. Buy spread side X when the
moneyline price of X rose by >= theta over the last N s (known by t-L) more than the spread price of X did.
Uses only Polymarket's public tape. Games split by median start (FIT older / TEST newer)."""
import sys, json, pickle, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S)
from evalkit import backtest, perm_test, within_auc
d=pickle.load(open(f'{S}/espn_games200.pkl','rb'))
games={e['event_slug']:e for e in d['games']}
A=pd.concat(d['frames'],ignore_index=True).rename(columns={'condition_id':'cid'})
A=A[A.side_kind.isin(['home','away'])].copy()
split=int(np.median([e['start'] for e in d['games']]))
A['period']=np.where(A.event_slug.map(lambda s:games[s]['start'])<split,'FIT','TEST')
L=2; NS=[10,30,60,120]
def home_series(df):
    x=df.sort_values('ts'); p=np.where(x.side_kind=='home',x.price,1-x.price); return x.ts.to_numpy(),p
def last_at(ts,p,tq):
    j=np.searchsorted(ts,tq,side='right')-1; return np.where(j>=0,p[np.clip(j,0,None)],np.nan)
parts=[]
for s,g in A.groupby('event_slug'):
    ml=g[g.mtype=='moneyline']
    if ml.empty: continue
    if ml.cid.nunique()>1: ml=ml[ml.cid==ml.cid.value_counts().index[0]]
    mts,mp=home_series(ml)
    for cid,sp in g[g.mtype=='spreads'].groupby('cid'):
        sts,spp=home_series(sp)
        x=sp.copy(); t=x.ts.to_numpy(); sgn=np.where(x.side_kind=='home',1,-1)
        for N in NS:
            mlm=last_at(mts,mp,t-L)-last_at(mts,mp,t-L-N)
            spm=last_at(sts,spp,t-L)-last_at(sts,spp,t-L-N)
            x[f'lag{N}']=sgn*(mlm-spm)
        parts.append(x)
X=pd.concat(parts,ignore_index=True); X=X[X.payout.notna()]
F=X[X.period=='FIT'].reset_index(drop=True); T=X[X.period=='TEST'].reset_index(drop=True)
out={'spread_prints_fit':len(F),'spread_prints_test':len(T),'wallet_fit':int(F.is_wallet.sum()),'wallet_test':int(T.is_wallet.sum()),
     'fit_auc':{N:within_auc(F.dropna(subset=[f'lag{N}']),f'lag{N}') for N in NS}}
rows=[]
for N in NS:
    for th in [0.0001,0.01,0.02,0.04,0.07,0.1]:
        h=(F[f'lag{N}']>=th)&(F.price>=0.05)&(F.price<=0.95)
        if h.sum()<50: continue
        bt=backtest(F[h]); rows.append({'N':N,'theta':th,'fit_t':bt['per_event_t'],'fit_ret':bt['ret'],'fit_trades':bt['trades'],'fit_match_diff':float(h[F.is_wallet].mean()-h[~F.is_wallet].mean())})
R=pd.DataFrame(rows)
for nm,b in [('match_fit',R.sort_values('fit_match_diff',ascending=False).iloc[0]),('profit_fit',R.sort_values('fit_t',ascending=False).iloc[0])]:
    N,th=int(b.N),float(b.theta); T2=T.copy(); T2['hit']=(T2[f'lag{N}']>=th)&(T2.price>=0.05)&(T2.price<=0.95)
    out[nm]={'N':N,'theta':th,'fit':b.drop(['N','theta']).to_dict(),'test_backtest':backtest(T2[T2.hit]),'test_match':perm_test(T2,'hit',n_perm=1000)}
    T2['score']=T2[f'lag{N}']; out[nm]['test_auc']=within_auc(T2.dropna(subset=['score']),'score')
print(json.dumps(out,indent=1,default=float)); print(R.sort_values('fit_t',ascending=False).head(5).to_string())
json.dump(out,open(f'{S}/h5_crossmarket_result.json','w'),indent=1,default=float)
