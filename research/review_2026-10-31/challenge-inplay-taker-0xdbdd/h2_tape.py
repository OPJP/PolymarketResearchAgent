"""H2 TAPE-ONLY rules (all sports): momentum / contrarian on the bought token's recent price change (public tape,
known by t-L), optionally restricted to quiet books (no print for >= s s) and a price band.
Rule families are scanned on FIT only; the FIT-best (by wallet match, and separately by profit) is evaluated on TEST."""
import sys, json, itertools, numpy as np, pandas as pd
S=sys.argv[1]; L=sys.argv[2] if len(sys.argv)>2 else '2'; sys.path.insert(0,S)
from evalkit import backtest, perm_test, perm_auc, within_auc
P=pd.read_pickle(f'{S}/prints_L{L}.pkl')
B=P[(P.side=='BUY')&(P.minutes>=0)].copy()
F=B[B.period=='FIT']; T=B[B.period=='TEST']
grid=[]
for N in [10,30,60,120,300]:
    for sgn in [1,-1]:
        for th in [0.0001,0.01,0.03,0.06,0.1]:
            for s in [0,10,30]:
                for (a,b) in [(0.02,0.98),(0.1,0.9),(0.3,0.9)]:
                    grid.append((N,sgn,th,s,a,b))
def hit(x,N,sgn,th,s,a,b):
    return (sgn*x[f'mom{N}']>=th)&(x.since_last_print>=s)&(x.price>=a)&(x.price<=b)
rows=[]
for g in grid:
    h=hit(F,*g)
    if h.sum()<100: continue
    bt=backtest(F[h])
    rows.append({'params':g,'fit_t':bt['per_event_t'],'fit_ret':bt['ret'],'fit_trades':bt['trades'],
                 'fit_wallet_hit':float(h[F.is_wallet].mean()),'fit_others_hit':float(h[~F.is_wallet].mean()),
                 'fit_lift':float(h[F.is_wallet].mean()/max(h[~F.is_wallet].mean(),1e-9))})
R=pd.DataFrame(rows)
R['fit_match_diff']=R.fit_wallet_hit-R.fit_others_hit
out={'n_rules_scanned':len(R)}
# continuous-score AUCs for the momentum feature on FIT, choose N and sign, then TEST AUC with permutation
aucs={f'mom{N}':within_auc(F,f'mom{N}') for N in [10,30,60,120,300]}
bestN=max(aucs,key=lambda k:abs(aucs[k]-0.5)); sgn=1 if aucs[bestN]>0.5 else -1
T2=T.copy(); T2['score']=sgn*T2[bestN]
out['continuous_momentum']={'fit_aucs':aucs,'chosen':bestN,'sign':sgn,'test':perm_auc(T2.dropna(subset=['score']),'score',n_perm=300)}
for nm,b in [('match_fit',R.sort_values('fit_match_diff',ascending=False).iloc[0]),('profit_fit',R.sort_values('fit_t',ascending=False).iloc[0]),('lift_fit',R[R.fit_trades>=1000].sort_values('fit_lift',ascending=False).iloc[0])]:
    g=b.params; T2=T.copy(); T2['hit']=hit(T2,*g)
    out[nm]={'params(N,sign,theta,stale_s,a,b)':list(g),'fit':b.drop('params').to_dict(),
             'test_backtest':backtest(T2[T2.hit]),'test_backtest_excl_wallet':backtest(T2[T2.hit&~T2.is_wallet]),
             'test_match':perm_test(T2,'hit',n_perm=1000)}
print(json.dumps(out,indent=1,default=float))
json.dump(out,open(f'{S}/h2_tape_result_L{L}.json','w'),indent=1,default=float)
print(R.sort_values('fit_t',ascending=False).head(6).to_string()); print(R.sort_values('fit_match_diff',ascending=False).head(6).to_string())
