import sys, json, pickle; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
from common import *
from feats import implied_up_series
from tapemaker_vec import tape_maker_vec
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
def prem_shift(df, ser, L, shift=0):
    out=np.full(len(df),np.nan); ts=df.ts.to_numpy().astype(np.int64)+shift; cid=df.condition_id.to_numpy()
    for c in np.unique(cid):
        m=cid==c; s_ts,up=ser.get(c,(np.array([],dtype=np.int64),np.array([])))
        if len(s_ts)==0: continue
        i=np.searchsorted(s_ts, ts[m]-L+1, side='left')-1
        out[m]=np.where(i>=0, up[np.clip(i,0,None)], np.nan)
    side=np.where(df.is_up, out, 1-out)
    return df.price.to_numpy()-side
res=json.load(open(S+'h1_tapemaker_results.json'))
for dur,(lo,hi) in (('15m',(60,600)),('5m',(30,240))):
    P=pickle.load(open(S+f'period_btc_{dur}.pkl','rb'))
    testm=pd.read_pickle(S+f'mk_{dur}_test_L2.pkl'); tf=pd.read_pickle(S+f'flow_{dur}_test.pkl'); ff=pd.read_pickle(S+f'flow_{dur}_fit.pkl')
    ser=implied_up_series(tf)
    L=res[dur]['match_choice']['L']; d=res[dur]['match_choice']['delta']
    y=testm.y.to_numpy()
    a=auc(-np.abs(prem_shift(testm,ser,L)+d),y)
    rng=np.random.default_rng(11); null=[]
    for _ in range(200):
        sh=int(rng.integers(lo,hi))*int(rng.choice([-1,1]))
        null.append(auc(-np.abs(prem_shift(testm,ser,L,sh)+d),y))
    null=np.array([x for x in null if np.isfinite(x)])
    rc={'auc':a,'null_mean':float(null.mean()),'null_p95':float(np.percentile(null,95)),'perm_p':permutation_pvalue(a,null),'shift_range_s':[lo,hi]}
    print(dur,'reference-clock-shift null:',{k:(round(v,4) if isinstance(v,float) else v) for k,v in rc.items()},flush=True)
    res[dur]['match_test_reference_shift_null']=rc
    # wallet passive prem distribution vs others (TEST)
    pr=prem_shift(testm,ser,L)
    res[dur]['prem_quantiles']={'wallet':np.nanpercentile(pr[y==1],[5,25,50,75,95]).round(3).tolist(),'others':np.nanpercentile(pr[y==0],[5,25,50,75,95]).round(3).tolist()}
    print('  prem quantiles', res[dur]['prem_quantiles'])
    # equivalence check of vectorized maker vs repo function on 15m chosen params
    lat=res[dur]['bt_choice']['latency']; dl=res[dur]['bt_choice']['delta']
    v=tape_maker_vec(tf,P['test']['windows'],dl,lat)
    print('  vec check pnl', round(v['pnl'],4), 'repo', round(res[dur]['bt_test']['pnl'],4), 'fills', v['fills'], res[dur]['bt_test']['fills'])
    # extended grid on FIT incl. deeper deltas and at-touch optimistic bound
    ext={}
    for at in (False,True):
        for lat in (2,5):
            for dl in (0.0,0.01,0.02,0.03,0.05,0.08,0.12,0.16,0.20):
                r=tape_maker_vec(ff,P['fit']['windows'],dl,lat,at_touch=at); r.pop('_fills',None)
                ext[(at,lat,dl)]=r
    for at in (False,True):
        cand={k:v for k,v in ext.items() if k[0]==at and v.get('fills',0)>=30}
        best=max(cand,key=lambda k:cand[k]['per_market_t'])
        te=tape_maker_vec(tf,P['test']['windows'],best[2],best[1],at_touch=at); te.pop('_fills',None)
        print(f'  at_touch={at} FIT best lat={best[1]} delta={best[2]}', {k:round(cand[best][k],4) if isinstance(cand[best][k],float) else cand[best][k] for k in ('fills','pnl','return_on_bought','per_market_t')}, 'TEST', {k:(round(te[k],4) if isinstance(te[k],float) else te[k]) for k in ('fills','pnl','return_on_bought','per_market_t','per_market_p','per_market_bootstrap_p')},flush=True)
        res[dur][f'ext_grid_at_touch_{at}']={'fit_best':{'latency':best[1],'delta':best[2],**cand[best]},'test':te,'fit_all':{f'lat={k[1]},d={k[2]}':{kk:v.get(kk) for kk in ('fills','pnl','per_market_t')} for k,v in ext.items() if k[0]==at}}
json.dump(res,open(S+'h1_tapemaker_results.json','w'),indent=1,default=float)
