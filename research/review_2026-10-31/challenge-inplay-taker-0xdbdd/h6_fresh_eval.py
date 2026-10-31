"""H6 GOAL rule frozen from the first sample, evaluated on FRESH soccer totals markets/events.
Rule: buy Over at an in-play taker BUY print when max |dYes| over the event's moneyline markets in (t-L-N, t-L]
>= theta and the Over price itself moved < theta/2 in the same window; price in [0.05,0.95]. L=2."""
import sys, json, pickle, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S); sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from evalkit import backtest, perm_test
from polyrea.analysis.profile import resolution_info
W='0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'; SPLIT=1793318400-15*86400; L=2
d=pickle.load(open(f'{S}/fresh_soccer.pkl','rb'))
def last_at(ts,p,tq):
    if len(ts)==0: return np.full(len(tq),np.nan)
    j=np.searchsorted(ts,tq,side='right')-1; return np.where(j>=0,p[np.clip(j,0,None)],np.nan)
ml={}; tots=[]
for kind,cid,mm,gst,s,rows in d['tapes']:
    if not rows: continue
    tok=[str(x) for x in json.loads(mm['clobTokenIds'])]
    if kind=='ml':
        b=[r for r in rows if r.get('side')=='BUY' and str(r.get('asset')) in tok]
        if not b: continue
        ts=np.array([int(r['timestamp']) for r in b]); k=np.array([tok.index(str(r['asset'])) for r in b]); p=np.array([float(r['price']) for r in b])
        o=np.argsort(ts,kind='stable'); ml.setdefault(s,[]).append((ts[o],np.where(k==0,p,1-p)[o]))
    else: tots.append((cid,mm,gst,s,rows,tok))
units=[]
for cid,mm,gst,s,rows,tok in tots:
    if s not in ml: continue
    res=resolution_info(mm)
    if not res['resolved']: continue
    outs=json.loads(mm['outcomes'])
    if 'Over' not in outs: continue
    io=outs.index('Over')
    a=[r for r in rows if str(r.get('asset')) in tok]
    ts=np.array([int(r['timestamp']) for r in a]); k=np.array([tok.index(str(r['asset'])) for r in a]); p=np.array([float(r['price']) for r in a])
    o=np.argsort(ts,kind='stable'); ts,k,p=ts[o],k[o],p[o]; pov=np.where(k==io,p,1-p)
    sides=np.array([a[i].get('side') for i in o]); wl=np.array([(a[i].get('proxyWallet') or '').lower()==W for i in o]); sz=np.array([float(a[i]['size']) for i in o])
    keep=(sides=='BUY')&(ts>=gst)
    df=pd.DataFrame({'ts':ts[keep],'k':k[keep],'price':p[keep],'size':sz[keep],'is_wallet':wl[keep]})
    if df.empty: continue
    df['outcome']=[outs[x] for x in df.k]; df['payout']=[res['payout'].get(tok[x],np.nan) for x in df.k]
    df['fee_rate']=float((mm.get('feeSchedule') or {}).get('rate',0.05)); df['cid']=cid; df['event_slug']=s; df['gst']=gst
    units.append((s,df,ts,pov))
print('units',len(units),'events',len({u[0] for u in units}),flush=True)
def build(N,th,shifts=None):
    parts=[]
    for s,df,ts,pov in units:
        tq=df.ts.to_numpy(); own=last_at(ts,pov,tq-L)-last_at(ts,pov,tq-L-N); mx=np.zeros(len(df)); sh=(shifts or {}).get(s,0)
        for mts,mp in ml[s]:
            mx=np.fmax(mx,np.nan_to_num(np.abs(last_at(mts+sh,mp,tq-L)-last_at(mts+sh,mp,tq-L-N))))
        x=df.copy(); x['hit']=(x.outcome=='Over')&(mx>=th)&(own<th/2)&(x.price>=0.05)&(x.price<=0.95); parts.append(x)
    X=pd.concat(parts,ignore_index=True); X=X[X.payout.notna()].reset_index(drop=True); X['period']=np.where(X.gst<SPLIT,'pre_split','post_split'); return X
out={}; rng=np.random.default_rng(13); slugs=sorted({u[0] for u in units})
for nm,(N,th) in {'match_fit_N300_th0.15':(300,0.15),'profit_fit_N300_th0.03':(300,0.03)}.items():
    X=build(N,th); r={}
    for per in ['post_split','pre_split','all']:
        Y=X if per=='all' else X[X.period==per]
        r[per]={'events':int(Y.event_slug.nunique()),'prints':int(len(Y)),'wallet_prints':int(Y.is_wallet.sum()),'backtest':backtest(Y[Y.hit]),
                'backtest_excl_wallet':backtest(Y[Y.hit&~Y.is_wallet]),'wallet_own_all':backtest(Y[Y.is_wallet]),
                'match_label_perm':perm_test(Y,'hit',n_perm=1000) if Y.is_wallet.sum() else None}
    obs=X.hit[X.is_wallet].mean()-X.hit[~X.is_wallet].mean(); null=[]
    for _ in range(100):
        Z=build(N,th,{s:int(rng.integers(300,1500))*int(rng.choice([-1,1])) for s in slugs}); null.append(Z.hit[Z.is_wallet].mean()-Z.hit[~Z.is_wallet].mean())
    null=np.array(null); r['all']['match_shift_null']={'obs':float(obs),'null_p95':float(np.percentile(null,95)),'perm_p':float((1+(null>=obs).sum())/(len(null)+1))}
    out[nm]=r; print(nm,json.dumps(r,indent=1,default=float),flush=True)
json.dump(out,open(f'{S}/h6_fresh_result.json','w'),indent=1,default=float)
