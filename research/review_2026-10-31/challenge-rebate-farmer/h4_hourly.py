"""H4: slow spot-vs-open fair-value taker on BTC hourly windows (resolve on Binance 1h candle close >= open; proxied by
Kraken per-second spot available 1 s after each second). Fit latency/theta on FIT windows, test on TEST windows."""
import sys, json, pickle; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
from feats import load
from polyrea.analysis.updown import match_test, backtest, wallet_replay, taker_buy_prints, score_prints
import numpy as np, pandas as pd
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'
_,spot=load('15m')
H=pickle.load(open(S+'period_btc_1h.pkl','rb'))
fp=taker_buy_prints(H['fit']['tapes'],H['fit']['windows']); tp=taker_buy_prints(H['test']['tapes'],H['test']['windows'])
# spot coverage check: blocks cover [block_start-1920, block_end+120]; decisions in window use t-lat >= start-? fine
print('prints fit/test', len(fp), len(tp), 'wallet', int((fp.wallet==W).sum()), int((tp.wallet==W).sum()))
mt=match_test(fp,tp,W,spot,lags=[0,1,2,3,5,10,20,30,60],n_perm=200,seed=7)
lat,th=mt['chosen_latency_s'],mt['theta']
out={'match':mt}
print('match lag scan fit', {k:round(v,3) for k,v in mt['lag_scan_auc_fit'].items()})
print('match test', {k:mt['test'][k] for k in ('wallet_prints','auc','auc_null_mean','auc_null_p95','auc_perm_p')}, 'lat',lat,'theta',th, 'mcc', mt['test']['decision']['mcc'], 'mcc p', mt['test']['mcc_perm_p'])
# backtest: fit theta for PnL on FIT (separately from match theta), latencies 5 and 30 (normal connection / slow)
grid=np.round(np.arange(0.0,0.21,0.02),2)
out['bt']={}
for L in (2,5,30):
    fs={float(g):backtest(fp,spot,theta=float(g),latency=L) for g in grid}
    ok={g:v for g,v in fs.items() if v.get('trades',0)>=30 and v.get('windows',0)>=8}
    g=max(ok,key=lambda k:ok[k]['per_window_hac_t'])
    te=backtest(tp,spot,theta=g,latency=L); te_ex=backtest(tp,spot,theta=g,latency=L,exclude_wallet=W)
    out['bt'][str(L)]={'theta':g,'fit':{k:fs[g].get(k) for k in ('trades','windows','pnl','return_on_traded','per_window_hac_t','per_window_p')},'test':{k:v for k,v in te.items() if k!='daily_pnl'},'test_excl_wallet':{k:v for k,v in te_ex.items() if k!='daily_pnl'}}
    print('bt L',L,'theta',g,'FIT',out['bt'][str(L)]['fit'],'\n   TEST',{k:te.get(k) for k in ('trades','windows','usd_traded','pnl','return_on_traded','per_window_p','per_window_bootstrap_p')})
out['wallet_replay_test']=wallet_replay(tp,W); out['wallet_replay_fit']=wallet_replay(fp,W)
print('wallet replay test', out['wallet_replay_test'], 'fit', out['wallet_replay_fit'])
json.dump(out,open(S+'h4_hourly_results.json','w'),indent=1,default=float)
