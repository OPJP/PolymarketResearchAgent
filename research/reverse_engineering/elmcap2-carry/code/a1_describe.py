"""A1: describe the wallet's whole pre-H history: timing vs endDate/closedTime, price, side, families."""
import sys, json, re
import numpy as np, pandas as pd
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
H = 1792713600
a = pd.read_parquet(OUT + 'activity_preH.parquet')
g = pd.read_parquet(OUT + 'gamma_traded.parquet').set_index('conditionId')
t = a[a.type == 'TRADE'].copy()
for c in ('usdcSize', 'price', 'size'): t[c] = t[c].astype(float)
t['end'] = (pd.to_datetime(t.conditionId.map(g.endDate), utc=True, errors='coerce') - pd.Timestamp(0, tz='UTC')).dt.total_seconds()
t['closed'] = (pd.to_datetime(t.conditionId.map(g.closedTime), utc=True, errors='coerce', format='mixed') - pd.Timestamp(0, tz='UTC')).dt.total_seconds()
t.loc[t.closed < 0, 'closed'] = np.nan
t['q'] = t.conditionId.map(g.question)
def fam(row):
    s = (str(row.slug) + ' ' + str(row.q)).lower()
    if 'fed-decision' in s or 'fed ' in s and 'rate' in s or 'fomc' in s or 'interest rate' in s: return 'fomc'
    if re.search(r'\b(ufc|nfl|nba|mlb|nhl|epl|premier league|la liga|serie a|bundesliga|champions league|vs\.?|fc |match|game|world cup|tennis|atp|wta|f1|grand prix|cs2|lol|dota|valorant|boxing|fight)\b', s): return 'sports'
    if re.search(r'\b(bitcoin|btc|ethereum|eth|solana|sol|xrp|crypto|price of)\b', s): return 'crypto'
    if re.search(r'\b(election|win the|governor|senate|president|primary|nominee|mayor|parliament|prime minister|vote|seats)\b', s): return 'election'
    if re.search(r'\b(by|before|in) (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|the end|20\d\d|q[1-4])', s) or 'by ' in s and re.search(r'\d{1,2}(st|nd|rd|th)?\??$', s): return 'deadline'
    return 'other'
t['fam'] = t.apply(fam, axis=1)
win = {}
for c, r in g.iterrows():
    try:
        pays = [float(x) for x in json.loads(r.outcomePrices or '[]')]
    except Exception:
        pays = []
    win[c] = pays
t['pay'] = [ (win.get(c) or [np.nan, np.nan])[int(i)] if (win.get(c) and i is not None and not pd.isna(i) and int(i) < len(win.get(c))) else np.nan for c, i in zip(t.conditionId, t.outcomeIndex)]
b = t[t.side == 'BUY'].copy()
b['h_to_end'] = (b.end - b.timestamp) / 3600
b['h_to_closed'] = (b.closed - b.timestamp) / 3600
def wq(x, w, qs):
    o = np.argsort(x.values); xs = x.values[o]; cw = np.cumsum(w.values[o]) / w.values.sum()
    return [round(float(xs[min(len(xs)-1, np.searchsorted(cw, q))]), 3) for q in qs]
print('BUY usd total', round(b.usdcSize.sum()), 'fills', len(b))
print('USD-wtd quantiles hours to closedTime', wq(b.h_to_closed.fillna(1e6), b.usdcSize, [.05,.1,.25,.5,.75,.9,.95]))
print('USD-wtd quantiles hours to endDate', wq(b.h_to_end.fillna(1e6), b.usdcSize, [.05,.1,.25,.5,.75,.9,.95]))
print('share USD bought AFTER endDate', round(b.usdcSize[b.h_to_end < 0].sum() / b.usdcSize.sum(), 3), ' after closedTime', round(b.usdcSize[b.h_to_closed < 0].sum() / b.usdcSize.sum(), 3))
b['pb'] = pd.cut(b.price, [0, .5, .8, .9, .95, .97, .98, .99, .995, .998, .9995, 1.0], right=False)
print(b.groupby('pb', observed=True).agg(fills=('usdcSize','size'), usd=('usdcSize','sum'), win=('pay','mean'), med_h_closed=('h_to_closed','median'), med_h_end=('h_to_end','median')).round(3).to_string())
print(b.groupby('fam').agg(fills=('usdcSize','size'), usd=('usdcSize','sum'), mk=('conditionId','nunique'), med_px=('price','median'), win=('pay','mean'), med_h_closed=('h_to_closed','median')).round(3).to_string())
b.drop(columns=['pb']).to_parquet(OUT + 'buys.parquet')
t.to_parquet(OUT + 'trades.parquet')
