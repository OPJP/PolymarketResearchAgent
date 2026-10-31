"""H1: FOMC consensus carry. PIT rule fit on 2025 meetings, tested on 2026 meetings."""
import json, sys, pickle, itertools
import numpy as np, pandas as pd
from scipy import stats
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
data=pickle.load(open(OUT+'h1_fomc.pkl','rb'))
DAY=86400; KMAX=14
rows=[]; wallet_fills=[]
for ev in data:
    dec=ev['decision_ts']
    for m in ev['markets']:
        h=sorted((int(x['t']),float(x['p'])) for x in m['hist'])
        if not h: continue
        ht=np.array([x[0] for x in h]); hp=np.array([x[1] for x in h])
        payout=[float(x) for x in json.loads(m['outcomePrices'])]
        tok_yes, tok_no = m['toks']
        buys=[a for a in m['act'] if a.get('type')=='TRADE' and a.get('side')=='BUY' and int(a['timestamp'])<dec]
        for a in m['act']:
            if a.get('type')=='TRADE': wallet_fills.append(dict(key=ev['key'], group=m['group'], ts=int(a['timestamp']), side=a['side'], asset=str(a['asset']), price=float(a['price']), usdc=float(a['usdcSize']), pre=int(a['timestamp'])<dec, hrs_before=(dec-int(a['timestamp']))/3600))
        for k in range(1,KMAX+1):
            t0=dec-k*DAY; t1=dec-(k-1)*DAY
            i=np.searchsorted(ht,t0,side='right')-1
            if i<0: continue
            p0=hp[i]  # PIT: last published hourly price at or before cell start
            cons_yes = p0>=0.5
            q0 = p0 if cons_yes else 1-p0
            ctok = tok_yes if cons_yes else tok_no
            inside=(ht>t0)&(ht<=t1)
            qpath = hp[inside] if cons_yes else 1-hp[inside]
            qmin = float(qpath.min()) if len(qpath) else q0
            wb=[a for a in buys if t0<=int(a['timestamp'])<t1]
            w_cons=[a for a in wb if str(a['asset'])==ctok]; w_anti=[a for a in wb if str(a['asset'])!=ctok]
            rows.append(dict(key=ev['key'], test=ev['key']>='2026', group=m['group'], k=k, q0=q0, qmin=qmin, cons_yes=cons_yes,
                 pay_cons=payout[0] if cons_yes else payout[1], y=int(len(w_cons)>0), y_anti=int(len(w_anti)>0),
                 usd_cons=sum(float(a['usdcSize']) for a in w_cons), usd_anti=sum(float(a['usdcSize']) for a in w_anti),
                 wpx=(sum(float(a['usdcSize']) for a in w_cons)/max(1e-9,sum(float(a['size']) for a in w_cons))) if w_cons else np.nan))
df=pd.DataFrame(rows); wf=pd.DataFrame(wallet_fills)
df.to_csv(OUT+'h1_cells.csv',index=False); wf.to_csv(OUT+'h1_wallet_fills.csv',index=False)
print('cells', len(df), 'FIT', (~df.test).sum(), 'TEST', df.test.sum())
print('wallet pre-statement buy USD: consensus', df.usd_cons.sum(), 'anti-consensus', df.usd_anti.sum())
pre=wf[wf.pre & (wf.side=='BUY')]
print('wallet BUY fills pre-statement', len(pre), 'USD', pre.usdc.sum(), ' post-statement BUY USD', wf[(~wf.pre)&(wf.side=='BUY')].usdc.sum(), 'SELL USD', wf[wf.side=='SELL'].usdc.sum())
print('hours-before-statement quantiles of wallet buy USD-weighted:')
pw=pre.sort_values('hrs_before'); cw=pw.usdc.cumsum()/pw.usdc.sum()
for qq in [0.1,0.25,0.5,0.75,0.9]: print(' ',qq, round(float(pw.hrs_before.iloc[np.searchsorted(cw.values,qq)]),1))
print('wallet buy price quantiles (USD weighted):', [round(float(pre.price.iloc[np.argsort(pre.price.values)][np.searchsorted((pre.usdc.values[np.argsort(pre.price.values)]).cumsum()/pre.usdc.sum(),qq)]),3) for qq in [0.1,0.25,0.5,0.75,0.9]])
per=pre.groupby('key').usdc.sum(); print('wallet pre-statement buy USD per meeting:'); print(per.round(0).to_string())

def predict(d,K,lo,hi): return ((d.k<=K)&(d.q0>=lo)&(d.q0<hi)).astype(int).values
def mcc(y,p):
    tp=((y==1)&(p==1)).sum(); tn=((y==0)&(p==0)).sum(); fp=((y==0)&(p==1)).sum(); fn=((y==1)&(p==0)).sum()
    den=np.sqrt(float((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)))
    return (tp*tn-fp*fn)/den if den>0 else 0.0
fit=df[~df.test].reset_index(drop=True); tst=df[df.test].reset_index(drop=True)
grid=[]
for K in range(1,KMAX+1):
    for lo in [0.5,0.6,0.7,0.8,0.85,0.88,0.9,0.92,0.94,0.96]:
        for hi in [0.96,0.97,0.98,0.99,0.995,1.0001]:
            if hi<=lo: continue
            grid.append((mcc(fit.y.values,predict(fit,K,lo,hi)),K,lo,hi))
grid.sort(reverse=True); best=grid[0]; print('FIT best (MCC,K,lo,hi):', best, 'next', grid[1:4])
_,K,lo,hi=best
pt=predict(tst,K,lo,hi); obs=mcc(tst.y.values,pt)
rng=np.random.default_rng(0); null=[]
groups=[np.where(tst.key.values==g)[0] for g in tst.key.unique()]
yv=tst.y.values.copy()
for _ in range(5000):
    yp=yv.copy()
    for ix in groups: yp[ix]=rng.permutation(yv[ix])
    null.append(mcc(yp,pt))
null=np.array(null); pperm=(1+(null>=obs).sum())/(1+len(null))
acc=(pt==yv).mean(); base=max(yv.mean(),1-yv.mean())
usd_cap=tst.usd_cons[pt==1].sum()/tst.usd_cons.sum()
print(f'TEST: MCC={obs:.3f} null mean={null.mean():.3f} p95={np.percentile(null,95):.3f} perm p={pperm:.4g}; accuracy={acc:.3f} vs majority {base:.3f}; share of wallet consensus-USD in predicted cells={usd_cap:.3f}; predicted cells={pt.sum()} wallet cells={yv.sum()}')
tp=((yv==1)&(pt==1)).sum(); print('TEST precision', tp/max(1,pt.sum()), 'recall', tp/max(1,yv.sum()))
# per-meeting TEST recall
for g in tst.key.unique():
    s=tst.key==g; print('  ',g,'wallet cells',int(tst.y[s].sum()),'pred',int(pt[s].sum()),'hit',int(((tst.y==1)&(pt==1))[s].sum()))
# ---------------- backtest (TEST) -----------------
def backtest(d, pmask, mode):
    out=[]
    for g in d.key.unique():
        s=(d.key==g).values & (pmask==1)
        sub=d[s]
        if sub.empty: out.append(dict(key=g, n=0, cost=0, pnl=0, ret=np.nan)); continue
        if mode=='maker':
            bid=np.floor(sub.q0.values*1000)/1000  # join at last published price, tick 0.001
            filled=sub.qmin.values<=bid-1e-9  # price later traded at/below our bid within the day
            px=bid; fee=0
        else:
            filled=np.ones(len(sub),bool); px=np.minimum(sub.q0.values+0.005,0.999); fee=0.05*px*(1-px)
        usd=1.0
        sh=usd/(px+fee)
        cost=(usd*filled).sum(); pay=(sh*sub.pay_cons.values*filled).sum()
        out.append(dict(key=g, n=int(filled.sum()), cost=float(cost), pnl=float(pay-cost), ret=float((pay-cost)/cost) if cost>0 else np.nan))
    return pd.DataFrame(out)
res={}
for mode in ['maker','taker']:
    for nm,d,pm in [('FIT',fit,predict(fit,K,lo,hi)),('TEST',tst,pt)]:
        b=backtest(d,pm,mode); r=b.ret.dropna().values
        t=stats.ttest_1samp(r,0,alternative='greater') if len(r)>1 else None
        sign=stats.binomtest(int((r>0).sum()),len(r),0.5,alternative='greater').pvalue if len(r) else np.nan
        # bootstrap over meetings of the mean return
        bs=np.array([rng.choice(r,len(r)).mean() for _ in range(5000)]) if len(r) else np.array([np.nan])
        print(f'{mode} {nm}: meetings={len(r)} per-meeting returns={np.round(r,4).tolist()} mean={r.mean():.4f} t-p={t.pvalue if t else np.nan:.3g} sign-p={sign:.3g} boot P(mean<=0)={(bs<=0).mean():.3g} pooled ret={b.pnl.sum()/b.cost.sum():.4f}')
        res[f'{mode}_{nm}']=dict(per_meeting=b.to_dict('records'), mean=float(r.mean()), t_p=float(t.pvalue) if t else None, sign_p=float(sign), pooled=float(b.pnl.sum()/b.cost.sum()))
# Wallet's own realized carry per meeting (settled at resolution)
wf2=wf[wf.side=='BUY'].copy()
json.dump(dict(best=best, test_mcc=obs, perm_p=pperm, null_mean=float(null.mean()), precision=float(tp/max(1,pt.sum())), recall=float(tp/max(1,yv.sum())), usd_capture=float(usd_cap), backtest=res), open(OUT+'h1_results.json','w'), indent=1, default=str)
