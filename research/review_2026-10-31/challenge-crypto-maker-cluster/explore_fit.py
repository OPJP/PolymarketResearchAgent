# Exploration on FIT period ONLY (hypothesis generation); TEST untouched here.
import sys; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from base import *
P = load('5m')
T, M = P['fit']['T'], P['fit']['M']
for X in (T, M):
    X['usd'] = X.price * X.sz; X['pnl'] = X.sz * (X.payout - X.price)
MB = M[M.side == 'BUY'].copy()
print('fit taker rows', len(T), 'passive BUY', len(MB), 'passive SELL', (M.side == 'SELL').sum())
for nm, w in (('bosona', BOS), ('almach', ALM)):
    x = MB[MB.wallet == w]; xt = T[T.wallet == w]
    print(nm, 'passive buys', len(x), 'usd', round(x.usd.sum()), 'pnl', round(x.pnl.sum(), 1), 'ret', round(x.pnl.sum() / x.usd.sum(), 4), 'windows', x.condition_id.nunique(), '| taker rows', len(xt), 'usd', round(xt.usd.sum()), xt.side.value_counts().to_dict(), '| passive sells', ((M.side == 'SELL') & (M.wallet == w)).sum())
b = np.arange(0, 1.01, 0.1)
def calib(X, label):
    X = X.copy(); X['bk'] = pd.cut(X.price, b)
    g = X.groupby('bk', observed=True).agg(n=('ts', 'size'), usd=('usd', 'sum'), sh=('sz', 'sum'), pnl=('pnl', 'sum'))
    g['avgp'] = g.usd / g.sh; g['win'] = (g.pnl + g.usd) / g.sh; g['ret'] = g.pnl / g.usd
    print(label, 'total ret', round(X.pnl.sum() / X.usd.sum(), 4), 'pnl', round(X.pnl.sum())); print(g.round(4).to_string())
calib(MB, 'ALL passive buys FIT')
calib(T[T.side == 'BUY'], 'ALL taker buys FIT')
calib(MB[MB.wallet.isin([BOS, ALM])], 'cluster passive buys FIT')
g = MB.groupby('wallet').agg(n=('ts', 'size'), usd=('usd', 'sum'), pnl=('pnl', 'sum'), windows=('condition_id', 'nunique'))
g['ret'] = g.pnl / g.usd
print('n maker wallets', len(g)); print(g.sort_values('pnl', ascending=False).head(15).round(3).to_string())
print('bosona rank', (g.pnl > g.loc[BOS, 'pnl']).sum(), 'almach rank', (g.pnl > g.loc[ALM, 'pnl']).sum())
print('total maker buy pnl', round(g.pnl.sum()), 'usd', round(g.usd.sum()))
