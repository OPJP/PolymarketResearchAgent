import _env, os, sys, pickle, json, collections
import pandas as pd
for name in _env.WALLETS:
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    t = [r for r in win['activity'] if r.get('type') == 'TRADE' and win['start'] <= r['timestamp'] < win['as_of']]
    sells = [r for r in t if r.get('side') == 'SELL']
    su = sum(float(r['usdcSize']) for r in sells); bu = sum(float(r['usdcSize']) for r in t if r.get('side') == 'BUY')
    merges = sum(float(r['usdcSize']) for r in win['activity'] if r.get('type') == 'MERGE' and win['start'] <= r['timestamp'] < win['as_of'])
    prof = json.load(open(f'/home/user/PolymarketResearchAgent/research/wallets/{win["wallet"]}/profile.json'))['derived']['profile']
    print(f'{name:15s} fills {len(t):7d} sell fills {len(sells):6d} ({len(sells)/len(t):.1%}) buy ${bu:,.0f} sell ${su:,.0f} merge ${merges:,.0f} | profile buy_share {prof["buy_share"]:.3f} settled_pnl ${prof["settled_pnl"]:,.0f} locked ${prof["settled_locked_pnl"]:,.0f} resid ${prof["settled_residual_pnl"]:,.0f}')
