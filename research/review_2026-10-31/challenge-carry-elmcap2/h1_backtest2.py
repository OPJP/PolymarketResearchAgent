"""H1 backtest with the FIT-fitted logistic score; threshold chosen on FIT (max F1). Maker strict proxy and taker."""
import json, numpy as np, pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
df=pd.read_csv(OUT+'h1_cells.csv')
def X(d):
    e=np.clip(1-d.q0.values,1e-4,1); return np.c_[d.k.values, np.log(e), np.log(e)**2, d.k.values*np.log(e)]
fit=df[~df.test].reset_index(drop=True); tst=df[df.test].reset_index(drop=True)
lr=LogisticRegression(C=1.0,max_iter=2000).fit(X(fit),fit.y)
sf=lr.predict_proba(X(fit))[:,1]; st=lr.predict_proba(X(tst))[:,1]
ths=np.linspace(0.05,0.9,35); f1s=[f1_score(fit.y,(sf>=t).astype(int)) for t in ths]; th=ths[int(np.argmax(f1s))]
pt=(st>=th).astype(int)
tp=((tst.y==1)&(pt==1)).sum(); print(f'threshold {th:.3f} (FIT F1 {max(f1s):.3f}); TEST predicted {pt.sum()} cells, wallet {tst.y.sum()}, precision {tp/max(1,pt.sum()):.3f} recall {tp/tst.y.sum():.3f}')
rng=np.random.default_rng(2)
def bt(d,p,mode,offset=0.0):
    out=[]
    for g in d.key.unique():
        s=(d.key==g).values&(p==1); sub=d[s]
        if sub.empty: continue
        if mode=='maker':
            bid=np.floor((sub.q0.values-offset)*1000)/1000
            filled=sub.qmin.values<bid-1e-9   # strict: published price later went strictly below our bid in the same day
            px=bid; fee=np.zeros(len(sub))
        else:
            filled=np.ones(len(sub),bool); px=np.minimum(sub.q0.values+0.005,0.999); fee=0.05*px*(1-px)
        cost=(filled*1.0).sum(); pay=(filled/(px+fee)*sub.pay_cons.values).sum()
        if cost>0: out.append(dict(key=g,n=int(filled.sum()),ret=(pay-cost)/cost, losses=int(((sub.pay_cons.values==0)&filled).sum())))
    return pd.DataFrame(out)
res={}
for mode,off in [('maker',0.0),('maker',0.002),('taker',0.0)]:
    for nm,d,p in [('FIT',fit,(sf>=th).astype(int)),('TEST',tst,pt)]:
        b=bt(d,p,mode,off); r=b.ret.values
        t=stats.ttest_1samp(r,0,alternative='greater'); sg=stats.binomtest(int((r>0).sum()),len(r),0.5,alternative='greater').pvalue
        bs=np.array([rng.choice(r,len(r)).mean() for _ in range(5000)])
        print(f'{mode}(off={off}) {nm}: meetings={len(r)} rets={np.round(r,4).tolist()} mean={r.mean():.4f} t-p={t.pvalue:.3g} sign-p={sg:.3g} boot P(mean<=0)={(bs<=0).mean():.3g} losing cells={int(b.losses.sum())}')
        res[f'{mode}_{off}_{nm}']=dict(rets=r.tolist(), mean=float(r.mean()), t_p=float(t.pvalue), sign_p=float(sg))
json.dump(dict(threshold=float(th), test_pred=int(pt.sum()), precision=float(tp/max(1,pt.sum())), recall=float(tp/tst.y.sum()), backtest=res), open(OUT+'h1_backtest2.json','w'), indent=1)
