"""H3 (coverage extension): spot-latency fair-value taker LA(theta, latency) and directional maker DM on BTC 15m
(the wallet's largest family, 21% of volume) using the repo's own match_test/backtest/maker_backtest."""
import sys, json, pickle; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
from feats import load
from polyrea.analysis.updown import match_test, backtest, wallet_replay, maker_buy_prints, taker_flow, maker_backtest
import numpy as np, pandas as pd
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'
P,spot=load('15m')
out={}
mt=match_test(P['fit']['prints'],P['test']['prints'],W,spot,n_perm=200,seed=7)
lat,th=mt['chosen_latency_s'],mt['theta']
out['taker_match']=mt
out['taker_backtest_test']=backtest(P['test']['prints'],spot,theta=th,latency=lat)
out['taker_backtest_test_lat_plus2']=backtest(P['test']['prints'],spot,theta=th,latency=lat+2)
out['wallet_replay_test']=wallet_replay(P['test']['prints'],W)
print('taker match', {k:mt['test'][k] for k in ('wallet_prints','auc','auc_null_mean','auc_perm_p')}, 'lat',lat,'theta',th)
print('taker bt', {k:out['taker_backtest_test'].get(k) for k in ('trades','pnl','return_on_traded','per_window_p')}, '+2s', {k:out['taker_backtest_test_lat_plus2'].get(k) for k in ('trades','pnl','per_window_p')})
print('wallet replay', out['wallet_replay_test'],flush=True)
fm=maker_buy_prints(P['fit']['full_tapes'],P['fit']['tapes'],P['fit']['windows']); tm=maker_buy_prints(P['test']['full_tapes'],P['test']['tapes'],P['test']['windows'])
mm=match_test(fm,tm,W,spot,n_perm=200,seed=7)
out['maker_match']=mm
lat=mm['chosen_latency_s']
ff=taker_flow(P['fit']['tapes'],P['fit']['windows']); tf=taker_flow(P['test']['tapes'],P['test']['windows'])
grid=[0.0,0.01,0.02,0.03,0.05,0.08]
fs={d:maker_backtest(ff,P['fit']['windows'],spot,d,lat) for d in grid}
bd=max(grid,key=lambda d:(fs[d].get('per_window_t') or -1e9) if fs[d].get('fills',0)>=30 else -1e9)
out['maker_fit_scan']={str(d):{k:fs[d].get(k) for k in ('fills','pnl','per_window_t')} for d in grid}
out['maker_bt_test']={k:v for k,v in maker_backtest(tf,P['test']['windows'],spot,bd,lat).items() if k!='daily_pnl'}
out['maker_bt_test_at_touch']={k:v for k,v in maker_backtest(tf,P['test']['windows'],spot,bd,lat,at_touch=True).items() if k!='daily_pnl'}
out['maker_choice']={'delta':bd,'latency':lat}
print('maker match', {k:mm['test'][k] for k in ('wallet_prints','auc','auc_null_mean','auc_perm_p')}, 'lat', lat)
print('maker bt', out['maker_choice'], {k:out['maker_bt_test'].get(k) for k in ('fills','pnl','return_on_bought','per_window_p')}, 'at-touch', {k:out['maker_bt_test_at_touch'].get(k) for k in ('fills','pnl','return_on_bought','per_window_p')})
json.dump(out,open(S+'h3_spot_btc15m_results.json','w'),indent=1,default=float)
