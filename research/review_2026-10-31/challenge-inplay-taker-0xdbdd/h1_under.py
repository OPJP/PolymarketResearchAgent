"""H1 UNDER-DRIFT: in-play soccer totals, buy Under at taker prints when the market has been quiet >= s seconds,
game minute in [m1,m2], Under price in [a,b]. Fit on FIT games (start < Oct 15), evaluate on TEST games."""
import sys, json, itertools, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S)
from evalkit import backtest, perm_test
P=pd.read_pickle(f'{S}/prints_L2.pkl')
B=P[(P.side=='BUY')&(P.minutes>=0)&(P.set=='soccer_totals')].copy()
B['is_under']=B.outcome=='Under'
out={}
for per in ['FIT','TEST']:
    x=B[B.period==per]
    out[f'baseline_all_under_{per}']=backtest(x[x.is_under])
    out[f'baseline_all_over_{per}']=backtest(x[~x.is_under])
    out[f'baseline_under_0.05-0.95_{per}']=backtest(x[x.is_under&(x.price>=0.05)&(x.price<=0.95)])
    out[f'wallet_own_{per}']=backtest(x[x.is_wallet])
grid=list(itertools.product([0,5,10,20,30,60],[0,20,45,60,75],[90,200],[0.05,0.2,0.4],[0.8,0.95]))
def hit(x,s,m1,m2,a,b): return x.is_under&(x.since_last_print>=s)&(x.minutes>=m1)&(x.minutes<m2)&(x.price>=a)&(x.price<=b)
F=B[B.period=='FIT']; T=B[B.period=='TEST']
rows=[]
for g in grid:
    h=hit(F,*g); bt=backtest(F[h]); 
    if bt.get('trades',0)<30: continue
    rows.append({'params':g,'fit_t':bt['per_event_t'],'fit_ret':bt['ret'],'fit_trades':bt['trades'],
                 'fit_match_diff':float(h[F.is_wallet].mean()-h[~F.is_wallet].mean())})
R=pd.DataFrame(rows)
best_profit=R.sort_values('fit_t',ascending=False).iloc[0]
best_match=R.sort_values('fit_match_diff',ascending=False).iloc[0]
for nm,b in [('profit_fit',best_profit),('match_fit',best_match)]:
    g=b.params; T2=T.copy(); T2['hit']=hit(T2,*g)
    out[nm]={'params(s,m1,m2,a,b)':list(g),'fit':b.drop('params').to_dict(),'test_backtest':backtest(T2[T2.hit]),
             'test_match':perm_test(T2,'hit',n_perm=2000)}
    # latency degradation: features at L=2 only; report wallet-free backtest (exclude wallet prints)
    out[nm]['test_backtest_excl_wallet_prints']=backtest(T2[T2.hit&~T2.is_wallet])
print(json.dumps(out,indent=1,default=float))
json.dump(out,open(f'{S}/h1_under_result.json','w'),indent=1,default=float)
print(R.sort_values('fit_t',ascending=False).head(8).to_string())
