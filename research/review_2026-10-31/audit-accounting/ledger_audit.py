"""Audit the capital-at-risk ledger on frozen windows: reproduce, then probe each accounting path."""
import _env, os, sys, pickle, json, collections
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.ledger import build_ledger, capital_and_roc
from polyrea.analysis.pnl import daily_frame
from polyrea.analysis.profile import resolution_info

def run(name):
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    act, markets, as_of = win['activity'], win['markets'], win['as_of']
    res_ts = {cid: r['closed_ts'] for cid, m in markets.items() if (r := resolution_info(m))['resolved'] and r['closed_ts']}
    led = build_ledger(win['wallet'], act, res_ts)
    body, _ = PolymarketData().user_pnl(win['wallet'])
    df = daily_frame(body.get('points') or [], as_of=as_of)
    daily = df['d_economic_pnl'].iloc[1:]
    roc = capital_and_roc(led, daily, 30)
    prof = json.load(open(f'/home/user/PolymarketResearchAgent/research/wallets/{win["wallet"]}/profile.json'))['derived']['capital']
    print(f'== {name}: reproduced peak ${roc["peak_capital"]:,.0f} roc {roc["monthly_roc"]:.4f} | profile.json peak ${prof["peak_capital"]:,.0f} roc {prof["monthly_roc"]:.4f}')
    types = collections.Counter(r.get('type') for r in act)
    print('   activity types:', dict(types))
    # exact duplicate rows (all fields identical)
    full = collections.Counter(json.dumps(r, sort_keys=True) for r in act)
    dups = sum(v - 1 for v in full.values() if v > 1)
    print('   exact-duplicate activity rows:', dups)
    # raw (unclipped) exposure level
    ev = sorted(led.exposure_events)
    lvl = np.cumsum([e[1] for e in ev])
    print(f'   raw cumulative exposure min {lvl.min():,.2f} max {lvl.max():,.2f}; final {lvl[-1]:,.2f}')
    # open positions at the end and their kind
    open_split = [p for k, p in led.positions.items() if k.startswith('split:') and p.shares > 1e-9 and p.closed_at is None]
    open_tok = [p for k, p in led.positions.items() if not k.startswith('split:') and p.shares > 1e-9 and p.closed_at is None]
    print(f'   never-released split positions: {len(open_split)} cost ${sum(p.cost for p in open_split):,.0f}; open token positions {len(open_tok)} cost ${sum(p.cost for p in open_tok):,.0f}')
    unres_open = [p for p in open_tok if p.condition_id not in res_ts]
    print(f'   open token positions in unresolved/unknown markets: {len(unres_open)} cost ${sum(p.cost for p in unres_open):,.0f}')
    # BUY rows after resolution time
    late = [r for r in act if r.get('type') == 'TRADE' and r.get('side') == 'BUY' and r.get('conditionId') in res_ts and r['timestamp'] > res_ts[r['conditionId']]]
    print('   BUY rows after market closedTime:', len(late), 'usdc', round(sum(float(r.get('usdcSize') or 0) for r in late), 2))
    print('   anomalies:', len(led.anomalies))
    return win, led, daily, roc, res_ts

if __name__ == '__main__':
    for n in sys.argv[1:]:
        run(n)
