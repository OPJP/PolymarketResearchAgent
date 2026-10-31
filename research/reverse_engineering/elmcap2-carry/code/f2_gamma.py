"""F2: Gamma metadata for every market the wallet traded before H."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import pandas as pd
from polyrea.adapters.polymarket import PolymarketData
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
df = pd.read_parquet(OUT + 'activity_preH.parquet')
cids = sorted(df.conditionId.dropna().unique().tolist())
pm = PolymarketData()
meta, srcs = pm.markets_by_condition(cids)
print('cids', len(cids), 'found', len(meta), 'requests', len(srcs), flush=True)
keep = ['conditionId','question','slug','outcomes','clobTokenIds','endDate','startDate','createdAt','closedTime','umaEndDate','outcomePrices','volumeNum','liquidityNum',
        'negRisk','negRiskMarketID','groupItemTitle','orderPriceMinTickSize','orderMinSize','feesEnabled','feeType','umaResolutionStatus','resolutionSource','category','enableOrderBook','rewardsMinSize','rewardsMaxSpread','clobRewards','acceptingOrdersTimestamp','gameStartTime','sportsMarketType','description']
rows = []
for c, m in meta.items():
    r = {k: m.get(k) for k in keep}
    for k in ('clobRewards',):
        r[k] = json.dumps(r[k]) if r[k] is not None else None
    ev = (m.get('events') or [{}])[0]
    r['event_slug'] = ev.get('slug'); r['event_title'] = ev.get('title'); r['event_id'] = ev.get('id')
    r['event_tags'] = json.dumps([t.get('slug') for t in (ev.get('tags') or [])]) if ev.get('tags') else None
    r['event_endDate'] = ev.get('endDate'); r['series'] = json.dumps([s.get('slug') for s in (ev.get('series') or [])]) if ev.get('series') else None
    r['description'] = (r['description'] or '')[:600]
    rows.append(r)
g = pd.DataFrame(rows)
g.to_parquet(OUT + 'gamma_traded.parquet')
print(g[['endDate','closedTime','negRisk','feeType']].head(3).to_string())
print('missing', len(set(cids) - set(meta)))
print('tags present', g.event_tags.notna().mean())
