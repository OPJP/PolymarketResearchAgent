"""Whole-history description of the wallet's activity (< H)."""
import sys, json
import numpy as np, pandas as pd
CACHE='/home/user/PolymarketResearchAgent/.cache/re/jld-inplay-taker'
a=pd.read_parquet(f'{CACHE}/activity.parquet')
print(a.type.value_counts().to_dict())
t=a[a.type=='TRADE'].copy()
print('sides', t.side.value_counts().to_dict())
t['lg']=t.eventSlug.fillna('').str.split('-').str[0]
t['mon']=pd.to_datetime(t.timestamp,unit='s').dt.strftime('%Y-%m')
t['usd']=t.usdcSize.astype(float)
print(t.pivot_table(index='lg',columns='mon',values='usd',aggfunc='sum').fillna(0).round(-3).astype(int).loc[lambda d: d.sum(1).sort_values(ascending=False).index].head(14).to_string())
print('fills per month', t.groupby('mon').size().to_dict())
print('median usd', t.usd.median(), 'q', t.usd.quantile([.1,.25,.5,.75,.9,.99]).round(2).tolist())
print('usd/(size*price)', (t.usd/(t['size'].astype(float)*t.price.astype(float))).describe().round(4).to_dict())
# fills per tx
print('rows per tx', t.groupby('transactionHash').size().value_counts().head(5).to_dict())
# fills per market
fpm=t.groupby('conditionId').size(); print('fills/market q', fpm.quantile([.5,.75,.9,.99]).tolist(), 'markets', len(fpm))
# same-second multi-market
s=t.groupby('timestamp').conditionId.nunique(); print('share seconds w >1 market', (s>1).mean().round(3), 'share fills in such seconds', t.timestamp.map(s).gt(1).mean().round(3))
e=t.groupby('timestamp').eventSlug.nunique(); print('share seconds w >1 event', (e>1).mean().round(3))
# integer shares
print('integer share frac', (np.abs(t['size'].astype(float)-np.round(t['size'].astype(float)))<1e-6).mean().round(3))
print('price q', t.price.astype(float).quantile([.05,.25,.5,.75,.95]).tolist())
# both tokens per market
bt=t.groupby('conditionId').outcomeIndex.nunique(); print('two-sided markets', (bt>1).mean().round(3))
r=a[a.type!='TRADE']; print(r.groupby('type').usdcSize.sum().round(0).to_dict())
