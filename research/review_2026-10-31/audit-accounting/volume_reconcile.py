"""Independent completeness check of the activity pagination: 30-day TRADE usdcSize vs user-pnl volume_usdc and fees_paid."""
import _env, os, pickle
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame
for name in _env.WALLETS:
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    df = daily_frame(PolymarketData().user_pnl(win['wallet'])[0]['points'], as_of=win['as_of'])
    vol = df['d_volume_usdc'].iloc[-30:].sum(); fees = -df['d_fees_paid'].iloc[-30:].sum(); cnt = df['d_trade_count'].iloc[-30:].sum()
    t = [r for r in win['activity'] if r.get('type') == 'TRADE' and win['start'] <= r['timestamp'] < win['as_of']]
    au = sum(float(r['usdcSize']) for r in t)
    print(f'{name:15s} activity usdc ${au:>13,.0f}  series volume ${vol:>13,.0f}  fees ${fees:>9,.0f}  activity - volume - fees = ${au - vol - fees:>9,.0f} ({(au - vol - fees) / vol:+.3%})  rows {len(t)} vs series trade_count {cnt:,.0f}')
