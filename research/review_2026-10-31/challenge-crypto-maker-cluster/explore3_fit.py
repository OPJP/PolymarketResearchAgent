# FIT-only: taker-row price vs maker-row prices within a tx; fill price vs last print (PIT).
import sys; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from base import *
P = load('5m')
T, M = P['fit']['T'], P['fit']['M']
# maker rows in "taker-token space": a maker BUY of complement at q corresponds to taker BUY price 1-q
tk = T.set_index('tx')
MB = M[M.side == 'BUY'].copy()
j = MB.merge(T[['tx', 'is_up', 'side', 'price', 'sz', 'wallet']].rename(columns={'is_up': 't_up', 'side': 't_side', 'price': 't_price', 'sz': 't_sz', 'wallet': 't_wallet'}), on='tx', how='left')
mint = j[(j.t_side == 'BUY') & (j.t_up != j.is_up)].copy()
mint['implied'] = 1 - mint.price
g = mint.groupby('tx').agg(tp=('t_price', 'first'), lo=('implied', 'min'), hi=('implied', 'max'), n=('implied', 'size'), msz=('sz', 'sum'), tsz=('t_sz', 'first'))
print('mint txs', len(g), 'multi-level txs', int((g.hi - g.lo > 1e-6).sum()))
mm = g[g.hi - g.lo > 1e-6]
print('taker price == max implied:', float((abs(mm.tp - mm.hi) < 1e-6).mean()), '== min:', float((abs(mm.tp - mm.lo) < 1e-6).mean()), 'between:', float(((mm.tp > mm.lo + 1e-6) & (mm.tp < mm.hi - 1e-6)).mean()))
print('taker size vs maker sum (median ratio)', float((g.tsz / g.msz).median()))
print(mm.head(5).to_string())
