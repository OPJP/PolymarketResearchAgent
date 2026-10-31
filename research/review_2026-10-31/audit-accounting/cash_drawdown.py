"""Independent capital check: the largest drawdown of the wallet's own USDC cash flow inside the window
(buys/splits out; sells, merges, redeems, income in). Cash locked in unredeemed winners counts, so this is an upper bound."""
import _env, os, sys, pickle, json
import numpy as np
for name in sys.argv[1:]:
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    ev = []
    for r in win['activity']:
        if not (win['start'] <= r['timestamp'] < win['as_of']): continue
        u = float(r.get('usdcSize') or 0); t = r.get('type')
        if t == 'TRADE': ev.append((r['timestamp'], -u if r.get('side') == 'BUY' else u))
        elif t == 'SPLIT': ev.append((r['timestamp'], -u))
        elif t in ('MERGE', 'REDEEM', 'REWARD', 'MAKER_REBATE', 'TAKER_REBATE', 'YIELD', 'REFERRAL'): ev.append((r['timestamp'], u))
    ev.sort(key=lambda e: (e[0], e[1] < 0))  # inflows first within a second (generous)
    c = np.cumsum([e[1] for e in ev]); dd = float(np.max(np.maximum.accumulate(np.concatenate([[0], c]))[1:] - c))
    prof = json.load(open(f'/home/user/PolymarketResearchAgent/research/wallets/{win["wallet"]}/profile.json'))['derived']['capital']
    print(f'{name:15s} ledger peak ${prof["peak_capital"]:>12,.0f} (ROC {prof["monthly_roc"]:7.1%}) | max cash drawdown ${dd:>12,.0f} -> ROC {prof["window_pnl"] / dd:7.1%}')
