"""Descriptive profile of the wallet's own fills over its whole development history (< H)."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.analysis.profile import market_family

CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'
OUT = '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker'
act = pd.read_parquet(f'{CACHE}/activity.parquet')
print('rows', len(act), act.type.value_counts().to_dict())
tr = act[act.type == 'TRADE'].copy()
tr['usd'] = tr.usdcSize.astype(float)
tr['day'] = pd.to_datetime(tr.timestamp, unit='s').dt.to_period('M')
tr['fam'] = [market_family(s) for s in tr.slug]
res = {}
res['first_trade'] = str(pd.Timestamp(tr.timestamp.min(), unit='s'))
res['last_trade_before_H'] = str(pd.Timestamp(tr.timestamp.max(), unit='s'))
res['fills'] = int(len(tr)); res['usd'] = float(tr.usd.sum()); res['markets'] = int(tr.conditionId.nunique())
res['side'] = tr.side.value_counts().to_dict()
res['by_month'] = tr.groupby('day').agg(fills=('usd', 'size'), usd=('usd', 'sum'), markets=('conditionId', 'nunique'),
                                         med_fill=('usd', 'median')).reset_index().astype({'day': str}).to_dict('records')
fam = tr.groupby('fam').agg(fills=('usd', 'size'), usd=('usd', 'sum')).sort_values('usd', ascending=False)
res['fam_top'] = fam.head(25).reset_index().to_dict('records')
# transaction structure: fills per tx, markets per tx, fills per (second)
g = tr.groupby('transactionHash').agg(n=('usd', 'size'), m=('conditionId', 'nunique'), a=('asset', 'nunique'))
res['fills_per_tx'] = g.n.describe().to_dict(); res['share_tx_multi_market'] = float((g.m > 1).mean())
s = tr.groupby('timestamp').agg(n=('usd', 'size'), m=('conditionId', 'nunique'), ev=('eventSlug', 'nunique'))
res['share_seconds_multi_market'] = float((s.m > 1).mean()); res['share_seconds_multi_event'] = float((s.ev > 1).mean())
# within a market: inter-fill gaps
tr = tr.sort_values('timestamp')
gap = tr.groupby('conditionId').timestamp.diff().dropna()
res['gap_quantiles_s'] = gap.quantile([.1, .25, .5, .75, .9]).to_dict()
res['fills_per_market_q'] = tr.groupby('conditionId').size().quantile([.25, .5, .75, .9, .99]).to_dict()
two = tr.groupby('conditionId').asset.nunique()
res['share_markets_both_tokens'] = float((two > 1).mean())
res['usd_q'] = tr.usd.quantile([.1, .25, .5, .75, .9, .99]).to_dict()
res['price_q'] = tr.price.astype(float).quantile([.1, .25, .5, .75, .9]).to_dict()
# size rounding: shares and usd granularity
res['size_round_int_share'] = float((np.abs(tr['size'].astype(float) - np.round(tr['size'].astype(float))) < 1e-6).mean())
json.dump(res, open(f'{OUT}/describe_wallet.json', 'w'), indent=1, default=str)
for k in ['first_trade', 'last_trade_before_H', 'fills', 'usd', 'markets', 'side', 'share_tx_multi_market',
          'share_seconds_multi_market', 'share_seconds_multi_event', 'gap_quantiles_s', 'fills_per_market_q',
          'share_markets_both_tokens', 'usd_q', 'price_q', 'size_round_int_share', 'fills_per_tx']:
    print(k, res[k])
print(pd.DataFrame(res['by_month']).to_string())
print(fam.head(25).to_string())
