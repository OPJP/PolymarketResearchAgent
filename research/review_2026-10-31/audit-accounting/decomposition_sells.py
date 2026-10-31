"""per_market_decomposition sums SELL fills into bought shares/cost. Compare with a sign-correct version."""
import _env, os, sys, pickle, json
import numpy as np, pandas as pd
from polyrea.analysis.ledger import build_ledger
from polyrea.analysis.profile import per_market_decomposition, resolution_info, price_bucket_calibration

def correct_settled(trades, markets):
    out = []
    for cid, g in trades.groupby('condition_id'):
        m = markets.get(cid) or {}
        res = resolution_info(m)
        tokens = json.loads(m.get('clobTokenIds') or '[]') if m else []
        if not (res['resolved'] and len(tokens) == 2):
            continue
        b = g[g.side == 'BUY']; s = g[g.side == 'SELL']
        net = {i: b[b.outcome_index == i]['size'].sum() - s[s.outcome_index == i]['size'].sum() for i in (0, 1)}
        payout = sum(net[i] * res['payout'].get(str(tokens[i]), 0.0) for i in (0, 1))
        out.append({'condition_id': cid, 'pnl_correct': payout - b['usdc'].sum() + s['usdc'].sum(), 'has_sell': len(s) > 0,
                    'net_negative': min(net.values()) < -1e-6})
    return pd.DataFrame(out)

for name in sys.argv[1:]:
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    res_ts = {cid: r['closed_ts'] for cid, m in win['markets'].items() if (r := resolution_info(m))['resolved'] and r['closed_ts']}
    led = build_ledger(win['wallet'], win['activity'], res_ts)
    tr = pd.DataFrame(led.trades); tr = tr[(tr.ts >= win['start']) & (tr.ts < win['as_of'])].reset_index(drop=True)
    pm = per_market_decomposition(tr, win['markets'])
    cc = correct_settled(tr, win['markets'])
    j = pm.merge(cc, on='condition_id', how='inner')
    j = j[j.resolved]
    ws = j[j.has_sell]
    print(f'== {name}: resolved markets {len(j)}, with sells {len(ws)}')
    print(f'   settled PnL as coded ${j.pnl.sum():,.0f}  sign-correct ${j.pnl_correct.sum():,.0f}  (diff ${j.pnl.sum() - j.pnl_correct.sum():,.0f}; markets with sells: coded ${ws.pnl.sum():,.0f} vs correct ${ws.pnl_correct.sum():,.0f})')
    print(f'   markets where sold more than bought in-window (pre-window inventory): {int(j.net_negative.sum())}')
    w = ws.assign(err=ws.pnl - ws.pnl_correct).sort_values('err')
    for _, r in pd.concat([w.head(2), w.tail(2)]).iterrows():
        print(f'   e.g. {r.slug[:50]:50s} coded ${r.pnl:,.0f} correct ${r.pnl_correct:,.0f} q0 {r.q0:,.0f} q1 {r.q1:,.0f} pair_cost {r.pair_cost:.3f}')
    # profile json number check
    prof = json.load(open(f'/home/user/PolymarketResearchAgent/research/wallets/{win["wallet"]}/profile.json'))['derived']['profile']
    print(f'   profile.json settled_pnl ${prof["settled_pnl"]:,.0f} (reproduced coded ${pm[pm.resolved].pnl.sum():,.0f})')
    # calibration: SELL rows enter the win-rate buckets as if bought
    cal = price_bucket_calibration(tr, win['markets']); calb = price_bucket_calibration(tr[tr.side == 'BUY'], win['markets'])
    for a, b in zip(cal, calb):
        if abs(a['win_rate'] - b['win_rate']) > 0.005 or a['fills'] != b['fills']:
            print(f'   calib bucket {a["price_lo"]:.1f}-{a["price_hi"]:.1f}: coded fills {a["fills"]} win {a["win_rate"]:.3f} | buys only fills {b["fills"]} win {b["win_rate"]:.3f}')
