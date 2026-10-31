"""Wallet's own realized FOMC carry per meeting (settled at resolution) and AUC version of H1 match test."""
import json, pickle, numpy as np, pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
data=pickle.load(open(OUT+'h1_fomc.pkl','rb'))
rows=[]
for ev in data:
    cost=0; proceeds=0; settle=0; first=None
    for m in ev['markets']:
        pay=dict(zip(m['toks'],[float(x) for x in json.loads(m['outcomePrices'])]))
        pos={}
        for a in sorted(m['act'], key=lambda a:a['timestamp']):
            if a['type']!='TRADE': continue
            sz=float(a['size']); us=float(a['usdcSize']); tk=str(a['asset'])
            if a['side']=='BUY': cost+=us; pos[tk]=pos.get(tk,0)+sz; first=min(first or 1e18,a['timestamp'])
            else: proceeds+=us; pos[tk]=pos.get(tk,0)-sz
        settle+=sum(max(0,q)*pay.get(t,0) for t,q in pos.items())
    pnl=proceeds+settle-cost
    rows.append(dict(key=ev['key'], cost=cost, pnl=pnl, ret=pnl/cost if cost else np.nan, days_held=(ev['decision_ts']-first)/86400 if first else np.nan))
r=pd.DataFrame(rows); print(r.round(4).to_string()); print('total cost', r.cost.sum(), 'total pnl', r.pnl.sum(), 'pooled', r.pnl.sum()/r.cost.sum(), 'n losing meetings', (r.pnl<0).sum())
r.to_csv(OUT+'h1_wallet_realized.csv', index=False)
# AUC version: logistic score on FIT features, AUC on TEST; null = permute labels within meeting
df=pd.read_csv(OUT+'h1_cells.csv')
def X(d): 
    e=np.clip(1-d.q0.values,1e-4,1); return np.c_[d.k.values, np.log(e), np.log(e)**2, d.k.values*np.log(e)]
fit=df[~df.test]; tst=df[df.test].reset_index(drop=True)
lr=LogisticRegression(C=1.0,max_iter=2000).fit(X(fit),fit.y)
s=lr.predict_proba(X(tst))[:,1]; auc=roc_auc_score(tst.y,s)
rng=np.random.default_rng(1); null=[]
grp=[np.where(tst.key.values==g)[0] for g in tst.key.unique()]
for _ in range(5000):
    y=tst.y.values.copy()
    for ix in grp: y[ix]=rng.permutation(y[ix])
    null.append(roc_auc_score(y,s))
null=np.array(null); p=(1+(null>=auc).sum())/(1+len(null))
# simpler 'days-only' score: -k
auck=roc_auc_score(tst.y,-tst.k)
print(f'H1 AUC (logit on k, log(1-q)) TEST={auc:.3f}, null mean={null.mean():.3f}, null p99={np.percentile(null,99):.3f}, perm p={p:.4g}; days-only AUC={auck:.3f}; FIT AUC={roc_auc_score(fit.y, lr.predict_proba(X(fit))[:,1]):.3f}')
json.dump(dict(auc_test=auc, perm_p=p, null_mean=float(null.mean()), null_p99=float(np.percentile(null,99)), auc_days_only=auck, wallet_realized=rows), open(OUT+'h1_auc_and_wallet.json','w'), indent=1, default=float)
