"""H2: deadline 'nothing happens' NO carry. Fit on Jul31/Aug31 deadlines, test on Sep30/Oct15 deadlines."""
import json, pickle, numpy as np, pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, f1_score
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
data=pickle.load(open(OUT+'h2_deadline.pkl','rb'))
DAY=86400; KMAX=10
rows=[]
for m in data:
    h=sorted((int(x['t']),float(x['p'])) for x in m['hist'])
    if len(h)<24: continue
    ht=np.array([x[0] for x in h]); hp=np.array([x[1] for x in h])
    yes,no=m['toks']; end=m['end']
    buys=[a for a in m['act'] if a.get('type')=='TRADE' and a.get('side')=='BUY']
    for k in range(1,KMAX+1):
        t0=end-k*DAY; t1=end-(k-1)*DAY
        i=np.searchsorted(ht,t0,side='right')-1
        if i<0: continue
        q0=hp[i]; ins=(ht>t0)&(ht<=t1); qmin=float(hp[ins].min()) if ins.any() else q0
        wb=[a for a in buys if t0<=int(a['timestamp'])<t1]
        wno=[a for a in wb if str(a['asset'])==no]; wyes=[a for a in wb if str(a['asset'])==yes]
        rows.append(dict(key=m['key'], test=m['split']=='TEST', cid=m['cid'], event=m['event'], q=m['q'][:80], k=k, q0=q0, qmin=qmin, tick=m['tick'], fee_rate=m['fee_rate'],
                         pay_no=m['pays'][1], y=int(len(wno)>0), y_yes=int(len(wyes)>0), usd_no=sum(float(a['usdcSize']) for a in wno), usd_yes=sum(float(a['usdcSize']) for a in wyes)))
df=pd.DataFrame(rows); df.to_csv(OUT+'h2_cells.csv',index=False)
mk=df.groupby('cid').agg(key=('key','first'),test=('test','first'),traded=('y','max'),pay_no=('pay_no','first'))
print('markets per deadline:', mk.groupby('key').agg(n=('traded','size'),wallet_traded=('traded','sum'),no_won=('pay_no','mean')).to_string())
print('cells FIT', (~df.test).sum(), 'TEST', df.test.sum(), 'wallet NO-buy cells FIT', df[~df.test].y.sum(), 'TEST', df[df.test].y.sum(), 'wallet YES-buy cells', df.y_yes.sum())
print('wallet NO USD by deadline', df.groupby('key').usd_no.sum().round(0).to_dict(), 'YES USD', df.groupby('key').usd_yes.sum().round(0).to_dict())
df['qb']=pd.cut(df.q0,[0,0.5,0.8,0.9,0.95,0.97,0.98,0.99,0.995,1.0001],right=False)
print(df.groupby(['test','qb'],observed=False).agg(cells=('y','size'),wallet_rate=('y','mean'),no_win=('pay_no','mean')).round(3).to_string())
def mcc(y,p):
    tp=((y==1)&(p==1)).sum(); tn=((y==0)&(p==0)).sum(); fp=((y==0)&(p==1)).sum(); fn=((y==1)&(p==0)).sum()
    den=np.sqrt(float((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))); return (tp*tn-fp*fn)/den if den>0 else 0.0
fit=df[~df.test].reset_index(drop=True); tst=df[df.test].reset_index(drop=True)
def pred(d,K,lo,hi): return ((d.k<=K)&(d.q0>=lo)&(d.q0<hi)).astype(int).values
grid=sorted(((mcc(fit.y.values,pred(fit,K,lo,hi)),K,lo,hi) for K in range(1,KMAX+1) for lo in [0.8,0.85,0.9,0.93,0.95,0.97,0.98,0.99] for hi in [0.97,0.98,0.99,0.995,0.998,1.0001] if hi>lo), reverse=True)
best=grid[0]; _,K,lo,hi=best; print('FIT best rule (MCC,K,lo,hi)', best)
pt=pred(tst,K,lo,hi); obs=mcc(tst.y.values,pt)
def X(d):
    e=np.clip(1-d.q0.values,1e-4,1); return np.c_[d.k.values, np.log(e), np.log(e)**2, d.k.values*np.log(e)]
lr=LogisticRegression(max_iter=3000).fit(X(fit),fit.y); s=lr.predict_proba(X(tst))[:,1]; auc=roc_auc_score(tst.y,s)
rng=np.random.default_rng(3); grp=[np.where(tst.key.values==g)[0] for g in tst.key.unique()]
nm=[]; na=[]
for _ in range(3000):
    y=tst.y.values.copy()
    for ix in grp: y[ix]=rng.permutation(y[ix])
    nm.append(mcc(y,pt)); na.append(roc_auc_score(y,s))
nm=np.array(nm); na=np.array(na)
p_m=(1+(nm>=obs).sum())/(1+len(nm)); p_a=(1+(na>=auc).sum())/(1+len(na))
tp=((tst.y==1)&(pt==1)).sum()
print(f'TEST rule MCC={obs:.3f} (null mean {nm.mean():.3f}, perm p={p_m:.4g}); precision={tp/max(1,pt.sum()):.3f} recall={tp/max(1,tst.y.sum()):.3f}; logistic AUC={auc:.3f} (null mean {na.mean():.3f}, p99 {np.percentile(na,99):.3f}, perm p={p_a:.4g}); FIT AUC={roc_auc_score(fit.y,lr.predict_proba(X(fit))[:,1]):.3f}')
# per-market wallet capture
cap=tst.usd_no[pt==1].sum()/max(1,tst.usd_no.sum()); print('share of wallet TEST NO-USD in rule cells', round(cap,3))
# backtest: rule cells; one $1 order per market (first firing cell only, hold to resolution)
def bt(d,p,mode):
    out=[]
    for cid,g in d[p==1].groupby('cid'):
        g=g.sort_values('k',ascending=False)
        for _,c in g.iterrows():
            tick=c.tick if c.tick>0 else 0.01
            if mode=='maker':
                bid=np.floor(c.q0/tick+1e-9)*tick
                if bid<=0 or not (c.qmin<bid-1e-9): continue
                px=bid; fee=0.0
            else:
                px=min(c.q0+tick/2,0.999); fee=c.fee_rate*px*(1-px)
            out.append(dict(cid=cid,key=c.key,event=c.event,k=c.k,px=px,ret=c.pay_no/(px+fee)-1)); break
    return pd.DataFrame(out)
res={}
for mode in ['maker','taker']:
    for nmn,d,p in [('FIT',fit,pred(fit,K,lo,hi)),('TEST',tst,pt)]:
        b=bt(d,p,mode)
        if b.empty: print(mode,nmn,'no trades'); continue
        r=b.ret.values; ev=b.groupby('event').ret.mean().values
        bs=np.array([rng.choice(ev,len(ev)).mean() for _ in range(5000)])
        t=stats.ttest_1samp(ev,0,alternative='greater') if len(ev)>1 else None
        print(f'{mode} {nmn}: markets={len(b)} events={len(ev)} losers={(r<-0.5).sum()} mean ret/market={r.mean():.4f} median={np.median(r):.4f} event-cluster t-p={t.pvalue if t else np.nan:.3g} boot P(mean<=0)={(bs<=0).mean():.3g} mean entry px={b.px.mean():.3f} mean k={b.k.mean():.1f}')
        res[f'{mode}_{nmn}']=dict(n=len(b), events=len(ev), losers=int((r<-0.5).sum()), mean=float(r.mean()), t_p=float(t.pvalue) if t else None, boot_p=float((bs<=0).mean()))
        b.to_csv(OUT+f'h2_bt_{mode}_{nmn}.csv',index=False)
json.dump(dict(best=best, test_mcc=obs, perm_p_mcc=p_m, auc=auc, perm_p_auc=p_a, precision=float(tp/max(1,pt.sum())), recall=float(tp/max(1,tst.y.sum())), usd_capture=cap, backtest=res), open(OUT+'h2_results.json','w'), indent=1, default=float)
