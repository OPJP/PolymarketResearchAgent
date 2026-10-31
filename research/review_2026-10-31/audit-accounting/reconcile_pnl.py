"""Reconcile the per-market settled PnL (as coded vs sign-correct) with the user-pnl trade_pnl series over the same window."""
import _env, os, pickle, json
import pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame
from polyrea.analysis.ledger import build_ledger
from polyrea.analysis.profile import per_market_decomposition, resolution_info
from decomposition_sells import correct_settled
for name in ('Tommy', 'elmcap2', 'RN1', 'justaluckydude'):
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    df = daily_frame(PolymarketData().user_pnl(win['wallet'])[0]['points'], as_of=win['as_of'])
    trade30 = df['d_trade_pnl'].iloc[-30:].sum(); econ30 = df['d_economic_pnl'].iloc[-30:].sum(); inc30 = df['d_wallet_income'].iloc[-30:].sum()
    res_ts = {cid: r['closed_ts'] for cid, m in win['markets'].items() if (r := resolution_info(m))['resolved'] and r['closed_ts']}
    led = build_ledger(win['wallet'], win['activity'], res_ts)
    tr = pd.DataFrame(led.trades); tr = tr[(tr.ts >= win['start']) & (tr.ts < win['as_of'])].reset_index(drop=True)
    pm = per_market_decomposition(tr, win['markets']); cc = correct_settled(tr, win['markets'])
    fee30 = df['d_fees_paid'].iloc[-30:].sum()
    print(f'{name:15s} user-pnl 30d: economic ${econ30:,.0f} = trade ${trade30:,.0f} + income ${inc30:,.0f} + fees ${fee30:,.0f}; trade+fees ${trade30+fee30:,.0f} | per-market settled as coded ${pm[pm.resolved].pnl.sum():,.0f}, sign-correct ${cc.pnl_correct.sum():,.0f}')
