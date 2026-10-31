"""H2: late-window favorite taker (optionally spot-confirmed). Fit (T, theta, m) on FIT, evaluate on TEST.
Decisions use: print price (the ask that traded), seconds to window end (listing metadata), and Kraken spot
available at t-2s (fair_side). Settlement only via up_payout."""
import sys, json; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
from common import *
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'
CAP=25.0
def trades(df, T, th, m, spot_filter, exclude_wallet=True):
    d=df[df.up_payout.notna()]
    if exclude_wallet: d=d[d.y==0]
    fee_ps=d.fee_rate*d.price*(1-d.price)
    sel=(d.secs_to_end<=T)&(d.secs_to_end>0)&(d.price>=th)&(d.price<=0.995)
    if spot_filter: sel&=(d.fair_side-d.price-fee_ps>=m)
    s=d[sel].copy()
    if s.empty: return s
    s['usd']=np.minimum(s['size']*s.price,CAP); sh=s.usd/s.price
    pay=np.where(s.is_up,s.up_payout,1-s.up_payout)
    s['fee']=s.fee_rate*s.price*(1-s.price)*sh
    s['pnl']=sh*pay-s.usd-s.fee
    return s
res={}
for dur in ['15m','5m']:
    fit=pd.read_pickle(S+f'tk_{dur}_fit_L2.pkl'); test=pd.read_pickle(S+f'tk_{dur}_test_L2.pkl')
    span=900 if dur=='15m' else 300
    Ts=[30,60,120,180,300]+([450] if dur=='15m' else [])
    for spot_filter in (False,True):
        grid=[]
        for T in Ts:
            for th in [0.6,0.7,0.8,0.85,0.9,0.93,0.95,0.97]:
                for m in ([0.0,0.01,0.02,0.04] if spot_filter else [None]):
                    f=trades(fit,T,th,m,spot_filter)
                    if len(f)==0 or f.condition_id.nunique()<30: continue
                    s=pnl_summary(f); grid.append(((T,th,m),s))
        best=max(grid,key=lambda x:x[1]['per_window_t'])
        (T,th,m),sfit=best
        ste=pnl_summary(trades(test,T,th,m,spot_filter))
        ste_incl=pnl_summary(trades(test,T,th,m,spot_filter,exclude_wallet=False))
        # latency degradation for the spot variant is n/a here (features built at L=2); report fit grid top5
        top=sorted(grid,key=lambda x:-x[1]['per_window_t'])[:5]
        # match: score = late indicator * (price) or late * spot edge net of fee
        def score(df):
            late=((df.secs_to_end<=T)&(df.secs_to_end>0)).to_numpy()
            if spot_filter:
                v=(df.fair_side-df.price-df.fee_rate*df.price*(1-df.price)).to_numpy()
            else:
                v=df.price.to_numpy()
            return np.where(late, 1.0+v, v-10.0)  # late prints rank above early ones, then by value
        mfit=match_report(fit,score(fit),n_perm=100,seed=1)
        mte=match_report(test,score(test),n_perm=200,seed=2)
        # wallet's own late-favorite taker buys on TEST (original strategy, same rule filter)
        wt=test[test.y==1]; wsel=trades(wt.assign(y=0),T,th,m,spot_filter)
        key=f'{dur}_{"spot" if spot_filter else "plain"}'
        res[key]={'fitted':{'T':T,'theta':th,'m':m},'fit':sfit,'test':ste,'test_incl_wallet_prints':ste_incl,'fit_top5':[{'params':p,'t':s['per_window_t'],'pnl':s['pnl'],'trades':s['trades']} for p,s in top],
                  'match_fit':mfit,'match_test':mte,'wallet_rule_trades_test':pnl_summary(wsel)}
        print(key, json.dumps(res[key]['fitted']), 'FIT', {k:round(v,4) if isinstance(v,float) else v for k,v in sfit.items()})
        print('   TEST', {k:round(v,4) if isinstance(v,float) else v for k,v in ste.items()})
        print('   match fit', {k:round(v,4) if isinstance(v,float) else v for k,v in mfit.items()}, ' test', {k:round(v,4) if isinstance(v,float) else v for k,v in mte.items()}, flush=True)
json.dump(res,open(S+'h2_favorite_results.json','w'),indent=1,default=float)
