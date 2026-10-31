"""Positions opened before the 7-day warm-up but still open inside the 30-day window are invisible to the ledger.
Proxy: REDEEM/MERGE rows (no earlier fill in loaded history) whose market resolved inside the window."""
import _env, os, sys, pickle
from polyrea.analysis.profile import resolution_info
for name in sys.argv[1:]:
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    first = {}
    for r in win['activity']:
        if r.get('type') in ('TRADE', 'SPLIT'): first.setdefault(r['conditionId'], r['timestamp'])
    n = usd = 0; slugs = []
    for r in win['activity']:
        if r.get('type') not in ('REDEEM', 'MERGE'): continue
        cid = r['conditionId']
        if cid in first and first[cid] <= r['timestamp']: continue
        m = win['markets'].get(cid) or {}
        ri = resolution_info(m)
        if r['type'] == 'MERGE' or (ri['closed_ts'] and ri['closed_ts'] >= win['start']):
            n += 1; usd += float(r.get('usdcSize') or 0); slugs.append((r['type'], (r.get('slug') or '')[:45], round(float(r.get('usdcSize') or 0))))
    print(f'{name:15s} invisible positions live inside window: {n} rows, ${usd:,.0f} paid out/merged', sorted(slugs, key=lambda x: -x[2])[:4])
