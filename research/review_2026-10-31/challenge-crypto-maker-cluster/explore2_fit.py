# FIT-only: price granularity, sizes, timing, co-fill with twin, taker counterparties.
import sys; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from base import *
P = load('5m')
T, M = P['fit']['T'], P['fit']['M']
MB = M[M.side == 'BUY'].copy()
MB['usd'] = MB.price * MB.sz; MB['pnl'] = MB.sz * (MB.payout - MB.price)
MB['grp'] = np.where(MB.wallet == BOS, 'bosona', np.where(MB.wallet == ALM, 'almach', 'others'))
mills = np.round(MB.price * 1000).astype(int)
MB['cent'] = (mills % 10 == 0)
MB['halfcent'] = (mills % 5 == 0)
print(MB.groupby('grp')[['cent', 'halfcent']].mean().round(3))
print('wallet price value counts (bosona top 25):'); print(MB[MB.grp == 'bosona'].price.round(3).value_counts().head(25).to_string())
print('sizes bosona quantiles', MB[MB.grp == 'bosona'].sz.quantile([.1, .25, .5, .75, .9]).round(2).tolist(), 'others', MB[MB.grp == 'others'].sz.quantile([.1, .25, .5, .75, .9]).round(2).tolist())
print('window frac quantiles bosona', MB[MB.grp == 'bosona'].frac.quantile([0, .05, .25, .5, .75, .95, 1]).round(3).tolist())
print('secs into window (bosona) first-5%:', ((MB[MB.grp == 'bosona'].ts - MB[MB.grp == 'bosona'].start_ts)).quantile([0, .05, .1]).tolist())
# co-fill with twin: same tx
b_tx = set(MB[MB.grp == 'bosona'].tx); a_tx = set(MB[MB.grp == 'almach'].tx)
print('bosona txs', len(b_tx), 'almach txs', len(a_tx), 'shared', len(b_tx & a_tx))
# in shared txs: same price? same side?
sh = MB[MB.tx.isin(b_tx & a_tx) & MB.grp.isin(['bosona', 'almach'])]
piv = sh.groupby(['tx', 'grp']).agg(price=('price', 'mean'), up=('is_up', 'mean')).unstack()
print('shared tx: same side share', float((piv[('up', 'bosona')] == piv[('up', 'almach')]).mean()), 'abs price diff median', float((piv[('price', 'bosona')] - piv[('price', 'almach')]).abs().median()))
# who are the takers in txs hitting the cluster
tk = T.groupby('tx').wallet.first()
cl = MB[MB.grp != 'others']
cp = cl.tx.map(tk)
print('taker counterparties hitting cluster: unique', cp.nunique(), 'top 10 share', cp.value_counts(normalize=True).head(10).round(3).to_dict())
print('is taker the twin?', float(cp.isin([BOS, ALM]).mean()))
# taker side in those txs (SELL same token vs BUY complement)
tside = T.groupby('tx').agg(tside=('side', 'first'), tup=('is_up', 'first'))
x = cl.join(tside, on='tx')
x['mech'] = np.where(x.tside == 'SELL', 'taker_sell_same', np.where(x.tup != x.is_up, 'taker_buy_complement(mint)', 'taker_buy_same?'))
print(x.groupby(['grp', 'mech']).size())
y = MB[MB.grp == 'others'].join(tside, on='tx'); y['mech'] = np.where(y.tside == 'SELL', 'sell', np.where(y.tup != y.is_up, 'mint', 'same'))
print('others mech', y.mech.value_counts(normalize=True).round(3).to_dict())
