"""Sweep structure of the wallet's fills in the dev window (BUILD period only for fitting decisions;
here descriptive over [2026-09-01, 2026-10-13))."""
import json, numpy as np, pandas as pd
CACHE='/home/user/PolymarketResearchAgent/.cache/re/jld-inplay-taker'
B0,B1=1790812800,1791849600
a=pd.read_parquet(f'{CACHE}/activity.parquet'); gm=json.load(open(f'{CACHE}/gamma.json'))
t=a[(a.type=='TRADE')&(a.timestamp>=B0-86400)&(a.timestamp<B1+86400)].copy()
t=t[t.conditionId.isin(gm.keys())]
def gst(c):
    g=gm[c].get('gameStartTime')
    try: return pd.Timestamp(g).timestamp()
    except Exception: return np.nan
t['gst']=t.conditionId.map(gst); t=t[(t.gst>=B0)&(t.gst<B1)]
t['mtype']=t.conditionId.map(lambda c: gm[c].get('sportsMarketType') or 'other')
t['lg']=t.eventSlug.str.split('-').str[0]
t['usd']=t.usdcSize.astype(float); t['price']=t.price.astype(float)
t['rel']=t.timestamp-t.gst
print('BUILD fills', len(t), 'markets', t.conditionId.nunique(), 'events', t.eventSlug.nunique())
print('by league fills', t.lg.value_counts().head(8).to_dict())
print('by mtype fills', t.mtype.value_counts().head(8).to_dict())
print('usd by mtype', t.groupby('mtype').usd.sum().round(-3).sort_values(ascending=False).head(8).to_dict())
print('pre-game share', (t.rel<0).mean().round(4), 'rel hours q', (t.rel/3600).quantile([.05,.25,.5,.75,.95]).round(2).tolist())
# sweeps: group by (eventSlug, timestamp)
g=t.groupby(['eventSlug','timestamp'])
sw=g.agg(n=('conditionId','size'),nm=('conditionId','nunique'),types=('mtype',lambda x: '+'.join(sorted(set(x)))),usd=('usd','sum'))
print('event-seconds', len(sw), 'share multi-market', (sw.nm>1).mean().round(3), 'fills in multi', (sw.n[sw.nm>1].sum()/sw.n.sum()).round(3))
print('n markets per event-second dist', sw.nm.value_counts().sort_index().head(10).to_dict())
print('top type combos', sw.types.value_counts().head(10).to_dict())
# within a sweep: does it buy the same team across ML and spread? outcome names
t['out']=t.outcome.astype(str)
sw2=t[t.groupby(['eventSlug','timestamp']).conditionId.transform('nunique')>1]
cons=sw2.groupby(['eventSlug','timestamp']).out.apply(lambda x: len(set([o for o in x if o not in ('Over','Under')])))
print('sweeps: distinct team outcomes among team-side buys', cons.value_counts().head(5).to_dict())
# gaps between consecutive fill-seconds within an event
es=t.groupby('eventSlug').timestamp.apply(lambda x: np.diff(np.unique(x)))
gaps=np.concatenate([x for x in es if len(x)])
print('gap between fill-seconds in an event q', np.quantile(gaps,[.1,.25,.5,.75,.9]).tolist())
print('fills per event q', t.groupby('eventSlug').size().quantile([.25,.5,.75,.9]).tolist(), 'fill-seconds per event median', t.groupby('eventSlug').timestamp.nunique().median())
