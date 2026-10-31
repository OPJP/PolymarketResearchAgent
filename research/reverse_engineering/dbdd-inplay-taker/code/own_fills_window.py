"""Wallet's own fills in the tape window (BUILD+VALIDATE, < H) joined with Gamma: PnL and choices by market type."""
import sys, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent'); sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker/code')
import numpy as np, pandas as pd
from features import market_meta, payout_map
from polyrea.analysis.profile import market_family
CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'; OUT = '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker'
B0 = 1790121600; V0 = 1791849600; H = 1792713600
gm = json.load(open(f'{CACHE}/gamma.json'))
a = pd.read_parquet(f'{CACHE}/activity.parquet'); t = a[(a.type == 'TRADE') & a.conditionId.isin(gm.keys())].copy()
meta = {c: market_meta(gm[c]) for c in t.conditionId.unique()}
pay = {c: payout_map(gm[c]) for c in t.conditionId.unique()}
t['gst'] = t.conditionId.map(lambda c: meta[c]['gst']); t['smt'] = t.conditionId.map(lambda c: meta[c]['smt'] or 'none')
t = t[(t.gst >= B0) & (t.gst < H)]
t['period'] = np.where(t.gst >= V0, 'VALIDATE', 'BUILD')
t['fam'] = [market_family(s) for s in t.slug]
t['price'] = t.price.astype(float); t['size'] = t['size'].astype(float); t['usd'] = t.usdcSize.astype(float)
t['payout'] = [pay[c].get(str(x), np.nan) for c, x in zip(t.conditionId, t.asset)]
fr = t.conditionId.map(lambda c: meta[c]['fee_rate']).fillna(0.05)
t['fee'] = fr * t.price * (1 - t.price) * t['size']
t['pnl'] = t['size'] * t.payout - t.usd  # usdcSize already includes the taker fee (usdcSize/(size*price) ~ 1.024)
t['min'] = (t.timestamp - t.gst) / 60
t['fav'] = t.price > 0.5
soccer = {'unl','conl','mls','fif','ucl','uslc','bra','arg','mex','epl','es2','col1','lal','bra2','afcq','uel','bun','sea','fl1','elc','kor','jap','spl','por','ere','nor','tur','sco','aus','acle','acl2','gtm','ukr1','per1','ecu1','chi','nwsl','itsb','den','swe','bel','aut','sui','gre'}
t['pref'] = t.eventSlug.str.split('-').str[0]
t['sport'] = np.where(t.pref.isin(soccer), 'soccer', np.where(t.pref.isin(['itf','atp','wta']), 'tennis', np.where(t.pref.isin(['cs2','dota2','lol','val']), 'esports', np.where(t.pref.isin(['nba','nfl','cfb','nhl','mlb','wnba','cbb']), 'us', 'other'))))
def agg(g):
    return pd.Series({'fills': len(g), 'usd': g.usd.sum(), 'pnl': g.pnl.sum(), 'ret': g.pnl.sum() / g.usd.sum(), 'med_usd': g.usd.median(),
                      'fav': g.fav.mean(), 'med_min': g['min'].median(), 'pre_game': (g['min'] < 0).mean(), 'win': (g.payout > 0.5).mean(), 'avg_px': g.price.mean()})
out = {}
for k in ['sport', 'period']:
    out[k] = t.groupby(k).apply(agg).round(4).reset_index().to_dict('records')
x = t.groupby(['sport', 'smt']).apply(agg); x = x[x.fills >= 150].round(3)
print(t.groupby('sport').apply(agg).round(3).to_string()); print(t.groupby('period').apply(agg).round(3).to_string()); print(x.sort_values('usd', ascending=False).head(30).to_string())
out['sport_smt'] = x.reset_index().to_dict('records')
tot = t[t.smt.str.contains('totals')]
out['totals_over_share'] = tot.groupby('sport').apply(lambda g: (g.outcome.str.lower() == 'over').mean()).round(3).to_dict()
print('over share in totals', out['totals_over_share'])
json.dump(out, open(f'{OUT}/own_fills_window.json', 'w'), indent=1, default=float)
t.to_parquet(f'{CACHE}/own_fills_window.parquet')
