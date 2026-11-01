"""Gamma metadata for every market in the activity files. Sealed units keep only the listing projection."""
import sys, os, glob, json, time
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE
import pandas as pd, numpy as np
import sealed
from polyrea.adapters.polymarket import PolymarketData

KEY = 'dbdd-inplay-taker'
pm = PolymarketData()
act = pd.concat([pd.read_parquet(f, columns=['timestamp', 'conditionId']) for f in glob.glob(f'{CACHE}/activity/*.parquet')])
first = act.groupby('conditionId').timestamp.min()
cids = sorted(first.index)
print('markets', len(cids), flush=True)
LISTING = ['conditionId', 'question', 'slug', 'clobTokenIds', 'outcomes', 'gameStartTime', 'sportsMarketType', 'feeSchedule',
           'line', 'groupItemTitle', 'startDate', 'endDate', 'negRisk', 'createdAt', 'acceptingOrdersTimestamp', 'gameId',
           'orderMinSize', 'rewardsMinSize', 'rewardsMaxSpread', 'feesEnabled', 'makerBaseFee', 'takerBaseFee']
POSTHOC = ['outcomePrices', 'closedTime', 'umaResolutionStatus', 'closed', 'volumeNum', 'liquidityNum', 'orderPriceMinTickSize']
out = {}
t0 = time.time()
for i in range(0, len(cids), 400):
    part = cids[i:i + 400]
    got, _ = pm.markets_by_condition(part)
    for c, m in got.items():
        g = m.get('gameStartTime')
        try:
            ref = pd.Timestamp(g).timestamp() if g else float(first.get(c, np.nan))
        except Exception:
            ref = float(first.get(c, np.nan))
        s = sealed.is_sealed(ref, KEY) if np.isfinite(ref) else True
        rec = {k: m.get(k) for k in LISTING}
        ev = (m.get('events') or [{}])[:1]
        rec['events'] = [{k: e.get(k) for k in ('slug', 'title', 'seriesSlug', 'startTime', 'eventDate', 'gameId')} for e in ev]
        rec['unit_ts'] = ref
        rec['sealed'] = int(s)
        if not s:
            rec.update({k: m.get(k) for k in POSTHOC})
        out[c] = rec
    print(time.strftime('%H:%M:%S'), i + len(part), len(out), round(time.time() - t0), 's', flush=True)
json.dump(out, open(f'{CACHE}/gamma2.json', 'w'))
print('done', len(out), 'sealed', sum(v['sealed'] for v in out.values()), flush=True)
