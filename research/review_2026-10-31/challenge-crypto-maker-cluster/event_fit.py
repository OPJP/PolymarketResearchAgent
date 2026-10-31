# FIT-only characterization: spot path around passive fills (ex-post, descriptive), by maker group.
import sys; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from base import *
P = load('5m'); spot, _ = spot_index(P)
T, M = P['fit']['T'], P['fit']['M']
MB = M[M.side == 'BUY'].copy()
MB['usd'] = MB.price * MB.sz; MB['pnl'] = MB.sz * (MB.payout - MB.price)
ev = spot.ev; px = spot.px
def spot_at_event(t):  # spot by event time (descriptive only)
    i = np.searchsorted(ev, t, side='right') - 1
    return np.where(i >= 0, px[np.clip(i, 0, None)], np.nan)
ks = [-60, -30, -10, -5, -2, 0, 2, 5, 10, 30, 60]
sgn = np.where(MB.is_up, 1.0, -1.0)
base_ = spot_at_event(MB.ts.to_numpy())
for k in ks:
    MB[f'r{k}'] = sgn * (np.log(spot_at_event(MB.ts.to_numpy() + k)) - np.log(base_)) * 1e4  # bps signed toward side bought
grp = np.where(MB.wallet == BOS, 'bosona', np.where(MB.wallet == ALM, 'almach', 'others'))
MB['grp'] = grp
# strike distance: log(S_t / S0) signed toward side, in bps
s0 = spot_at_event(MB.start_ts.to_numpy())
MB['moneyness_bps'] = sgn * (np.log(base_) - np.log(s0)) * 1e4
cols = [f'r{k}' for k in ks]
print('mean signed spot return (bps) relative to fill time, by group (FIT, BTC 5m passive buys)')
print(MB.groupby('grp')[cols].mean().round(2).to_string())
print('usd-weighted:')
print(MB.groupby('grp').apply(lambda g: pd.Series({c: np.average(g[c].fillna(0), weights=g.usd) for c in cols})).round(2).to_string())
# same for price buckets
MB['pb'] = pd.cut(MB.price, [0, .1, .3, .5, .7, .9, 1])
print(MB.groupby(['pb', 'grp'], observed=True)[['r-30', 'r-5', 'r5', 'r30', 'moneyness_bps']].mean().round(2).to_string())
print(MB.groupby('grp').agg(n=('ts', 'size'), frac=('frac', 'median'), price=('price', 'median'), usd=('usd', 'median'), ret=('pnl', 'sum')).to_string())
