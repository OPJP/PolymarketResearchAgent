"""H3 WP-GAP: on ESPN-covered moneylines (NBA/NFL/CFB/WNBA), buy the side whose ESPN win probability, known at
play wallclock + D, exceeds the Polymarket taker print price by >= delta. Decision at t uses only plays with
wallclock + D <= t. Games split by median start (FIT older / TEST newer, as in the original sports study)."""
import sys, json, pickle, itertools, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S)
from evalkit import backtest, perm_test, within_auc
d=pickle.load(open(f'{S}/espn_games200.pkl','rb'))
games={e['event_slug']:e for e in d['games']}
A=pd.concat(d['frames'],ignore_index=True)
A=A[(A.mtype=='moneyline')&A.side_kind.isin(['home','away'])&A.payout.notna()].copy()
A=A.rename(columns={'condition_id':'cid'})
split=int(np.median([e['start'] for e in d['games']]))
A['period']=np.where(A.event_slug.map(lambda s:games[s]['start'])<split,'FIT','TEST')
wps={}
for s,e in games.items():
    pl=[(p.ts,p.home_wp) for p in e['game'].plays if p.home_wp is not None]
    if pl: wps[s]=(np.array([x[0] for x in pl]),np.array([x[1] for x in pl],float))
A=A[A.event_slug.isin(wps)].copy()
def fair(df,D,shifts=None):
    out=np.full(len(df),np.nan)
    for s,idx in df.groupby('event_slug').indices.items():
        ts,wp=wps[s]; known=ts+D+(shifts or {}).get(s,0)
        o=np.argsort(known,kind='stable'); known=known[o]; w=wp[o]
        tq=df.ts.to_numpy()[idx]; j=np.searchsorted(known,tq,side='right')-1
        f=np.where(j>=0,w[np.clip(j,0,None)],np.nan)
        side=df.side_kind.to_numpy()[idx]
        out[idx]=np.where(side=='home',f,1-f)
    return out
grid_D=[-10,0,5,10,20,30,60]; grid_d=[0.0,0.02,0.04,0.07,0.1,0.15]
F=A[A.period=='FIT'].reset_index(drop=True); T=A[A.period=='TEST'].reset_index(drop=True)
band=lambda x:(x.price>=0.05)&(x.price<=0.95)
rows=[]
for D in grid_D:
    F['gap']=F.price*0+fair(F,D)-F.price
    for dl in grid_d:
        h=(F.gap>=dl)&band(F)
        bt=backtest(F[h])
        rows.append({'D':D,'delta':dl,'fit_t':bt.get('per_event_t'),'fit_ret':bt.get('ret'),'fit_trades':bt.get('trades'),
                     'fit_wallet_hit':float(h[F.is_wallet].mean()),'fit_others_hit':float(h[~F.is_wallet].mean())})
    F[f'gapD{D}']=F.gap
R=pd.DataFrame(rows); R['fit_match_diff']=R.fit_wallet_hit-R.fit_others_hit
out={'games_fit':int(F.event_slug.nunique()),'games_test':int(T.event_slug.nunique()),'prints_fit':len(F),'prints_test':len(T),
     'wallet_fit':int(F.is_wallet.sum()),'wallet_test':int(T.is_wallet.sum())}
out['fit_auc_gap_by_D']={D:within_auc(F.assign(g=F[f'gapD{D}']).dropna(subset=['g']),'g') for D in grid_D}
rng=np.random.default_rng(3)
for nm,b in [('match_fit',R.sort_values('fit_match_diff',ascending=False).iloc[0]),('profit_fit',R.sort_values('fit_t',ascending=False).iloc[0])]:
    D,dl=int(b.D),float(b.delta); T2=T.copy(); T2['gap']=fair(T2,D)-T2.price; T2['hit']=(T2.gap>=dl)&band(T2)
    res={'D':D,'delta':dl,'fit':b.drop(['D','delta']).to_dict(),'test_backtest':backtest(T2[T2.hit]),
         'test_backtest_excl_wallet':backtest(T2[T2.hit&~T2.is_wallet]),'test_match_label_perm':perm_test(T2,'hit',n_perm=1000)}
    # timeline-shift null: shift each game's WP clock by +-300..1500 s
    obs=res['test_match_label_perm']['diff']; null=[]
    for _ in range(300):
        sh={s:int(rng.integers(300,1500))*int(rng.choice([-1,1])) for s in T2.event_slug.unique()}
        g=fair(T2,D,sh)-T2.price; h=(g>=dl)&band(T2)
        null.append(h[T2.is_wallet].mean()-h[~T2.is_wallet].mean())
    null=np.array(null); res['test_match_shift_null']={'obs_diff':obs,'null_p95':float(np.percentile(null,95)),'perm_p':float((1+(null>=obs).sum())/(len(null)+1))}
    # latency degradation of the rule (information D+extra)
    res['latency']={}
    for extra in (5,10,30):
        T3=T.copy(); T3['gap']=fair(T3,D+extra)-T3.price; h=(T3.gap>=dl)&band(T3); bt=backtest(T3[h])
        res['latency'][str(D+extra)]={k:bt.get(k) for k in ('trades','ret','per_event_p')}
    out[nm]=res
T2=T.copy(); T2['g']=fair(T2,int(R.sort_values('fit_match_diff',ascending=False).iloc[0].D))-T2.price
out['test_auc_gap']=within_auc(T2.dropna(subset=['g']),'g')
print(json.dumps(out,indent=1,default=float))
json.dump(out,open(f'{S}/h3_espn_wp_result.json','w'),indent=1,default=float)
print(R.sort_values('fit_t',ascending=False).head(6).to_string()); print(R.sort_values('fit_match_diff',ascending=False).head(6).to_string())
