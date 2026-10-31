"""H5 frozen-rule evaluation on FRESH games (not in the 128-game sample used for fitting/testing).
Rule frozen from FIT: buy spread side X at a taker BUY print when (moneyline price of X change over N s) minus
(spread price of X change over N s), both known by t-2 s, is > 0, price in [0.05,0.95]. N=60 (profit-fit), N=120 (match-fit)."""
import sys, json, pickle, re, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S); sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from evalkit import backtest, perm_test
from polyrea.analysis.profile import resolution_info
W='0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
d=pickle.load(open(f'{S}/fresh_h5.pkl','rb')); split=d['split']
norm=lambda s:re.sub(r'[^a-z0-9]','',(s or '').lower())
by_ev={}
for slug,m,rows in d['tapes']: by_ev.setdefault(slug,[]).append((m,rows))
def series(rows,tokens,team_idx):
    b=[r for r in rows if r.get('side')=='BUY' and str(r.get('asset')) in tokens]
    if not b: return np.array([]),np.array([])
    ts=np.array([int(r['timestamp']) for r in b]); k=np.array([tokens.index(str(r['asset'])) for r in b]); p=np.array([float(r['price']) for r in b])
    pt=np.where(k==team_idx,p,1-p); o=np.argsort(ts,kind='stable'); return ts[o],pt[o]
def last_at(ts,p,tq):
    if len(ts)==0: return np.full(len(tq),np.nan)
    j=np.searchsorted(ts,tq,side='right')-1; return np.where(j>=0,p[np.clip(j,0,None)],np.nan)
def build(N,L=2,shift=None,rng=None):
    parts=[]
    for slug,lst in by_ev.items():
        mls=[(m,r) for m,r in lst if m.get('sportsMarketType')=='moneyline' and r]
        if not mls: continue
        mlm,mlr=max(mls,key=lambda x:len(x[1]))
        ml_out=[norm(o) for o in json.loads(mlm['outcomes'])]; ml_tok=[str(x) for x in json.loads(mlm['clobTokenIds'])]
        if len(ml_out)!=2: continue
        sh=0 if shift is None else int(rng.integers(300,1500))*int(rng.choice([-1,1]))
        for m,rows in lst:
            if m.get('sportsMarketType')!='spreads' or not rows: continue
            res=resolution_info(m)
            if not res['resolved']: continue
            outs=[norm(o) for o in json.loads(m['outcomes'])]; tok=[str(x) for x in json.loads(m['clobTokenIds'])]
            def mi(o):
                for i,x in enumerate(ml_out):
                    if o==x or (o and x and (o in x or x in o)): return i
                return None
            mapk=[mi(o) for o in outs]
            if None in mapk or mapk[0]==mapk[1]: continue
            gst=int(pd.Timestamp(m['gameStartTime']).timestamp())
            buys=[r for r in rows if r.get('side')=='BUY' and str(r.get('asset')) in tok and int(r['timestamp'])>=gst]
            if not buys: continue
            df=pd.DataFrame({'ts':[int(r['timestamp']) for r in buys],'k':[tok.index(str(r['asset'])) for r in buys],
                             'price':[float(r['price']) for r in buys],'size':[float(r['size']) for r in buys],
                             'is_wallet':[(r.get('proxyWallet') or '').lower()==W for r in buys]})
            df['payout']=[res['payout'].get(tok[k],np.nan) for k in df.k]
            df['fee_rate']=float((m.get('feeSchedule') or {}).get('rate',0.05)); df['cid']=m['conditionId']; df['event_slug']=slug; df['gst']=gst
            lag=np.full(len(df),np.nan); t=df.ts.to_numpy()
            for k in (0,1):
                idx=np.flatnonzero(df.k.to_numpy()==k)
                if not len(idx): continue
                mts,mp=series(mlr,ml_tok,mapk[k]); mts=mts+sh
                sts,sp=series(rows,tok,k)
                tq=t[idx]
                lag[idx]=(last_at(mts,mp,tq-L)-last_at(mts,mp,tq-L-N))-(last_at(sts,sp,tq-L)-last_at(sts,sp,tq-L-N))
            df['lag']=lag; parts.append(df)
    X=pd.concat(parts,ignore_index=True); X=X[X.payout.notna()].reset_index(drop=True)
    X['hit']=(X.lag>=0.0001)&(X.price>=0.05)&(X.price<=0.95); X['period']=np.where(X.gst<split,'pre_split','post_split'); return X
out={}
rng=np.random.default_rng(21)
for N in (60,120):
    X=build(N); r={}
    for per in ['post_split','pre_split','all']:
        Y=X if per=='all' else X[X.period==per]
        r[per]={'games':int(Y.event_slug.nunique()),'prints':int(len(Y)),'wallet_prints':int(Y.is_wallet.sum()),
                'backtest':backtest(Y[Y.hit]),'backtest_excl_wallet':backtest(Y[Y.hit&~Y.is_wallet]),'wallet_own':backtest(Y[Y.is_wallet]),
                'match_label_perm':perm_test(Y,'hit',n_perm=1000) if Y.is_wallet.sum() else None}
    Y=X[X.period=='post_split']; obs=Y.hit[Y.is_wallet].mean()-Y.hit[~Y.is_wallet].mean(); null=[]
    for _ in range(100):
        Z=build(N,shift=True,rng=rng); Z=Z[Z.period=='post_split']; null.append(Z.hit[Z.is_wallet].mean()-Z.hit[~Z.is_wallet].mean())
    null=np.array(null); r['post_split']['match_shift_null']={'obs':float(obs),'null_p95':float(np.percentile(null,95)),'perm_p':float((1+(null>=obs).sum())/(len(null)+1))}
    r['latency_post_split']={str(L):{k:backtest(build(N,L).pipe(lambda z:z[(z.period=='post_split')&z.hit])).get(k) for k in ('trades','ret','per_event_p','boot_p')} for L in (5,10,30)}
    out[f'N{N}']=r
    print(N, json.dumps(r,indent=1,default=float), flush=True)
json.dump(out,open(f'{S}/h5_fresh_result.json','w'),indent=1,default=float)
