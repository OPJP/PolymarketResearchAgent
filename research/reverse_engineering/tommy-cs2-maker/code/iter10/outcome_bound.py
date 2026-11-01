"""X138 (mechanics panel iter-9 P3): outcome feasibility bound with a TAKER-side knockout, 16-22 Oct (development).

Per market (the 229 markets of per_market), settlement PnL of:
  W   the wallet (per_market.pnl)
  RM  its real maker leg, RT its real taker leg (chain fills)
  A   the validated X57 engine replay of its own maker orders (knockout_markets, iteration 9)
  D   the executable public-anchor continuous ladder (knockout_markets)
  TD  its taker orders DELAYED to their first public trace: each take re-executed at t_pub = its block time + 1 s,
      buying the same token from the public taker BUY prints stamped in [t_pub, t_pub + 30 s] (wallet prints and
      txs where it is the maker excluded) at their price (TD) or their price + 1c (TD1), only at prices <= its own
      limit, size capped at its real filled shares.  Oracle-timed (the trigger is its own take): a feasibility bound,
      never a rule.
Combinations E = A + RT (sanity), F = A + TD, F1 = A + TD1, G = D + RT, H = D + TD, H1 = D + TD1, plus RM + TD.
Reports Pearson / Spearman vs W on BUILD (game start < 10-21) and VALIDATE (10-21..H), and a variance decomposition
of W into the real legs and into message pairs (each take + its complement maker fills signed 0-5 s after it).
"""
import glob, json
import numpy as np, pandas as pd
from scipy import stats

ROOT = '.cache/re/tommy-cs2-maker'
import os
OUT = 'research/reverse_engineering/tommy-cs2-maker/results/outcome_bound' + os.environ.get('OB_SUFFIX', '') + '.json'
W = '0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
VAL0, H = 1792540800, 1792713600

pm = pd.read_parquet(f'{ROOT}/per_market.parquet').set_index('cid')
ko = pd.read_parquet(f'{ROOT}/knockout_markets.parquet').set_index('cid')
o = pd.read_parquet(f'{ROOT}/orders.parquet')
tok_oi = o.drop_duplicates('token_id').set_index('token_id')[['cid', 'oi']]
f = pd.read_parquet(f'{ROOT}/chain_fills_1792108800_1792713600.parquet')
f = f[f.bts < H]
f = f.merge(tok_oi, left_on='token_id', right_index=True, how='left')
f = f[f.cid.isin(pm.index)]
f['win'] = f.cid.map(pm.win)
f['val'] = f.shares * (f.oi == f.win) - f.usdc
legs = f.groupby(['cid', 'role']).val.sum().unstack(fill_value=0.0)
maker_tx = set(f[f.role == 'maker'].tx)

# message pairs: each take + complement maker fills of orders signed 0-5 s after the take's signing
ords = o.set_index('salt')
tk = o[(o.role == 'taker') & (o.cid.isin(pm.index))].copy()
mk = o[(o.role == 'maker') & (o.cid.isin(pm.index))].copy()
# maker fill value per order (from chain fills via order_hash is not in orders; approximate by filled shares x price)
mk['val'] = mk.filled * (mk.oi == mk.cid.map(pm.win)) - mk.filled * mk.price
tk_fill = f[f.role == 'taker'].groupby('tx').agg(sh=('shares', 'sum'), usd=('usdc', 'sum'))
pair_val = {}
for cid, g in tk.groupby('cid'):
    m = mk[mk.cid == cid]
    v = 0.0
    used = set()
    for r in g.itertuples():
        sel = m[(m.oi != r.oi) & (m.sign_ms >= r.sign_ms) & (m.sign_ms < r.sign_ms + 5000)]
        for s, val in zip(sel.salt, sel.val):
            if s not in used:
                used.add(s); v += val
    pair_val[cid] = v

# delayed taker from the public tape
def tape(cid):
    fs = glob.glob(f'{ROOT}/tapes/{cid}_tkw.parquet')
    if not fs:
        return None
    t = pd.read_parquet(fs[0])
    t = t[(t.proxyWallet.str.lower() != W) & (~t.transactionHash.isin(maker_tx)) & (t.side == 'BUY')]
    return t.sort_values('timestamp')

LAG_S = float(__import__('os').environ.get('OB_LAG', '1.0'))
TOL = float(__import__('os').environ.get('OB_TOL', '0.0'))
TD = {}; TD1 = {}; cov = []
for cid, g in tk.groupby('cid'):
    t = tape(cid)
    win = int(pm.loc[cid, 'win'])
    v0 = v1 = 0.0
    for r in g.itertuples():
        if r.filled <= 0:
            continue
        tp = float(r.first_fill_ts) + LAG_S
        if t is None:
            cov.append(0.0); continue
        c = t[(t.asset == r.token_id) & (t.timestamp >= tp) & (t.timestamp <= tp + 30)]
        left = float(r.filled); got0 = got1 = 0.0; cost0 = cost1 = 0.0
        for px, sz in zip(c.price.to_numpy(float), c['size'].to_numpy(float)):
            if left <= 1e-9:
                break
            q = min(left, sz)
            if px <= r.price + TOL + 1e-9:
                got0 += q; cost0 += q * px
            if px + 0.01 <= r.price + TOL + 1e-9:
                got1 += q; cost1 += q * (px + 0.01)
            left -= q
        cov.append(got0 / float(r.filled))
        v0 += got0 * (r.oi == win) - cost0
        v1 += got1 * (r.oi == win) - cost1
    TD[cid] = v0; TD1[cid] = v1

X = pd.DataFrame({'W': pm.pnl, 'gs': pm.gs})
X['RM'] = legs.get('maker', pd.Series(dtype=float)).reindex(X.index).fillna(0.0)
X['RT'] = legs.get('taker', pd.Series(dtype=float)).reindex(X.index).fillna(0.0)
X['A'] = ko.A_pnl.reindex(X.index)
X['D'] = ko.D_pnl.reindex(X.index)
X['TD'] = pd.Series(TD).reindex(X.index).fillna(0.0)
X['TD1'] = pd.Series(TD1).reindex(X.index).fillna(0.0)
X['PAIR'] = pd.Series(pair_val).reindex(X.index).fillna(0.0) + X.RT
X['E'] = X.A + X.RT; X['F'] = X.A + X.TD; X['F1'] = X.A + X.TD1
X['G'] = X.D + X.RT; X['Hh'] = X.D + X.TD; X['H1'] = X.D + X.TD1
X['RM_TD'] = X.RM + X.TD; X['RM_RT'] = X.RM + X.RT


def corr(a, b):
    k = np.isfinite(a) & np.isfinite(b)
    if k.sum() < 5 or np.std(a[k]) == 0:
        return None
    return [round(float(stats.pearsonr(a[k], b[k])[0]), 3), round(float(stats.spearmanr(a[k], b[k])[0]), 3), int(k.sum())]

res = {'take_fill_coverage_delayed_mean': float(np.mean(cov)) if cov else None, 'n_takes': int((tk.filled > 0).sum())}
for sp, sel in (('BUILD', X.gs < VAL0), ('VALIDATE', (X.gs >= VAL0) & (X.gs < H)), ('ALL', X.gs < H)):
    y = X[sel]
    r = {'markets': int(len(y)), 'sums': {k: round(float(y[k].sum()), 1) for k in ['W', 'RM', 'RT', 'A', 'D', 'TD', 'TD1', 'PAIR']}}
    for k in ['RM_RT', 'RM', 'RT', 'A', 'D', 'PAIR', 'E', 'F', 'F1', 'G', 'Hh', 'H1', 'RM_TD', 'TD']:
        r[k] = corr(y[k].to_numpy(float), y.W.to_numpy(float))
    # variance decomposition of W = RM + RT (+ small rounding)
    vW = np.var(y.W)
    r['cov_share_RM'] = round(float(np.cov(y.RM, y.W)[0, 1] / vW), 3)
    r['cov_share_RT'] = round(float(np.cov(y.RT, y.W)[0, 1] / vW), 3)
    r['cov_share_PAIR'] = round(float(np.cov(y.PAIR, y.W)[0, 1] / vW), 3)
    r['corr_RM_RT'] = round(float(np.corrcoef(y.RM, y.RT)[0, 1]), 3)
    res[sp] = r
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps(res, indent=1))
