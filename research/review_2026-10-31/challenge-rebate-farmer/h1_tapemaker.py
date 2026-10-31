"""H1: tape-anchored two-sided maker (no spot): every R s rest BUY bids on Up and Down at (last public implied
price known at t-L) - delta; strict trade-through fills (polyrea.analysis.tape_maker). Match: do the wallet's passive
buys sit at a fixed offset delta below the implied price L s earlier? Fit (L, delta) on FIT, evaluate on TEST."""
import sys, json, pickle; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
from common import *
from feats import implied_up_series, last_before
from polyrea.analysis.tape_maker import tape_maker_backtest
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
MAKER_REBATE_PER_USD=8693.3677/1933500.0   # wallet's observed maker rebate / maker notional (30d)
def prem_at(df, flow, L):
    ser=implied_up_series(flow)
    out=np.full(len(df),np.nan); ts=df.ts.to_numpy().astype(np.int64); cid=df.condition_id.to_numpy()
    for c in np.unique(cid):
        m=cid==c; out[m]=last_before(ser,c,ts[m],L)
    side=np.where(df.is_up, out, 1-out)
    return df.price.to_numpy()-side
res={}
for dur in ['15m','5m']:
    P=pickle.load(open(S+f'period_btc_{dur}.pkl','rb'))
    fitm=pd.read_pickle(S+f'mk_{dur}_fit_L2.pkl'); testm=pd.read_pickle(S+f'mk_{dur}_test_L2.pkl')
    ff=pd.read_pickle(S+f'flow_{dur}_fit.pkl'); tf=pd.read_pickle(S+f'flow_{dur}_test.pkl')
    scan={}
    pf={L:prem_at(fitm,ff,L) for L in (1,2,5,10,30)}
    for L in pf:
        for d in (0.0,0.01,0.02,0.03,0.05,0.08):
            sc=-np.abs(pf[L]+d)
            scan[(L,d)]=auc(sc,fitm.y.to_numpy())
    (L,d)=max(scan,key=scan.get)
    pt=prem_at(testm,tf,L)
    mte=match_report(testm,-np.abs(pt+d),n_perm=200,seed=3)
    # backtest
    def bt_inputs(p,flow):
        fl=flow.rename(columns={}).copy(); fl['outcome']=np.where(fl.is_up,0,1)
        pay={w.condition_id:w.up_payout for w in p['windows'] if w.up_payout is not None}
        act={w.condition_id:(w.start_ts,w.end_ts) for w in p['windows']}
        return fl[['condition_id','ts','outcome','side','price','size']],pay,act
    fl_f,pay_f,act_f=bt_inputs(P['fit'],ff); fl_t,pay_t,act_t=bt_inputs(P['test'],tf)
    fscan={}
    for lat in (2,5):
        for dl in (0.0,0.01,0.02,0.03,0.05,0.08):
            r=tape_maker_backtest(fl_f,pay_f,dl,lat,requote_s=10,active=act_f)
            fscan[(lat,dl)]=r
    best=max(fscan,key=lambda k:(fscan[k].get('per_market_t') or -1e9) if fscan[k].get('fills',0)>=30 else -1e9)
    lat,dl=best
    te=tape_maker_backtest(fl_t,pay_t,dl,lat,requote_s=10,active=act_t)
    te_q=tape_maker_backtest(fl_t,pay_t,dl,lat,requote_s=10,active=act_t,queue_share=0.5)
    te_slow=tape_maker_backtest(fl_t,pay_t,dl,lat+5,requote_s=10,active=act_t)
    # rebate-inclusive (newcomer maker rebate at the wallet's observed maker rebate per USD)
    reb=te['usd_bought']*MAKER_REBATE_PER_USD if te.get('fills') else 0
    # wallet's own passive buys on TEST windows
    w=testm[testm.y==1]; pay=np.where(w.is_up,w.up_payout,1-w.up_payout)
    wp=pd.DataFrame({'condition_id':w.condition_id,'pnl':w['size']*(pay-w.price),'usd':w['size']*w.price})
    res[dur]={'match_scan_fit_auc':{f'L={k[0]},d={k[1]}':v for k,v in scan.items()},'match_choice':{'L':L,'delta':d,'fit_auc':scan[(L,d)]},'match_test':mte,
              'bt_fit_scan':{f'lat={k[0]},d={k[1]}':{kk:v.get(kk) for kk in ('fills','pnl','return_on_bought','per_market_t','per_market_p')} for k,v in fscan.items()},
              'bt_choice':{'latency':lat,'delta':dl},'bt_test':te,'bt_test_queue_half':te_q,'bt_test_latency_plus5':te_slow,'bt_test_maker_rebate_added_usd':reb,
              'wallet_passive_test':pnl_summary(wp)}
    print(dur,'match choice',res[dur]['match_choice'],'TEST',{k:round(v,4) if isinstance(v,float) else v for k,v in mte.items()})
    print(dur,'bt choice',res[dur]['bt_choice'],'FIT',{kk:fscan[best].get(kk) for kk in ('fills','pnl','return_on_bought','per_market_t','per_market_p')})
    print('   TEST',{k:(round(v,4) if isinstance(v,float) else v) for k,v in te.items()}, 'rebate add', round(reb,1))
    print('   TEST q=0.5',{k:te_q.get(k) for k in ('fills','pnl','per_market_p')},' lat+5',{k:te_slow.get(k) for k in ('fills','pnl','per_market_p')})
    print('   wallet passive TEST',res[dur]['wallet_passive_test'],flush=True)
json.dump(res,open(S+'h1_tapemaker_results.json','w'),indent=1,default=float)
