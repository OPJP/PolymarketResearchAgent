"""F1: full wallet activity history from first trade up to H (exclusive). Development data only."""
import sys, json, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import pandas as pd
from polyrea.adapters.polymarket import PolymarketData
W = '0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'
H = 1792713600
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
pm = PolymarketData()
body, src = pm.user_pnl(W)
pts = body.get('points') or []
print('pnl points', len(pts), pts[:2], pts[-1:] if pts else None, flush=True)
json.dump(pts, open(OUT + 'user_pnl.json', 'w'))
t0 = time.time()
rows, srcs, cov = pm.activity(W, start=0, end=H - 1)
print('activity rows', len(rows), cov, 'requests', len(srcs), 'secs', round(time.time() - t0), flush=True)
df = pd.DataFrame(rows)
df.to_parquet(OUT + 'activity_preH.parquet')
print(df.type.value_counts().to_string())
print('first', pd.to_datetime(df.timestamp.min(), unit='s'), 'last', pd.to_datetime(df.timestamp.max(), unit='s'))
