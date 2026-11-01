"""X137 (mechanics panel iter-9 P2): the maker message ledger. Localize the price gap by ORDER CLASS on the full
historical order record (16-22 Oct, development; on-chain fields only, so the same code runs on h1 / h2).

Message clock (wallet-independent): taker signings of the feed's other subscribers (group P: P4e at 0, 0x2005d16a with
its fixed lag subtracted, the slow trio with theirs), merged within 50 ms per event. Own takes are a second clock (own
state). Class of every wallet maker order (orders.parquet, filled orders only):
  own_msg  0-150 ms after one of its own takes on the event
  repair   0.9-1.2 s after one of its own takes
  msg      0-150 ms after a wallet-independent message (and not the above)
  follow   0.15-5 s after a message or an own take
  quiet    > 5 s after both
Anchors: (a) last public print on the token before signing (wallet prints and txs where it is the maker excluded),
rounded to the cent (the evaluate() anchor); (b) own state: its previous maker order's price on the same token;
(c) own state: its previous order on the complement, as K - p (K = 0.98, the pair cap). Within one tick (0.01 for
0.04-0.96) per class, BUILD (game start < 10-21) and VALIDATE. Per message on the hurt / helped token: dV = new level -
own last level before the message, and its slope on P4e's premium (limit - last print on its token).
Output: results/message_ledger.json
"""
import glob, json
import numpy as np, pandas as pd

ROOT = '.cache/re/tommy-cs2-maker'
OUT = 'research/reverse_engineering/tommy-cs2-maker/results/message_ledger.json'
W = '0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
P4E = '0x4ebc2722adc772bde8680792d0a6fdf15499a33d'
SUBLAG = {'0x2005d16a': 41.0, '0x72aaaaf9': 524.5, '0x2529c68d': 547.0, '0xfe8a28be': 523.0}
VAL0, H = 1792540800, 1792713600
K = 0.98

o = pd.read_parquet(f'{ROOT}/orders.parquet')
o = o[(o.sign_ms > 1.79e12) & (o.sign_ms < H * 1000)]
mk = o[o.role == 'maker'].copy()
tk = o[o.role == 'taker'].copy()
pm = pd.read_parquet(f'{ROOT}/per_market.parquet').set_index('cid')
mk = mk[mk.cid.isin(pm.index)]
mk['win'] = mk.cid.map(pm.win)
mk['pnl'] = mk.filled * ((mk.oi == mk.win).astype(float) - mk.price)

cols = ['tx', 'idx', 'maker', 'token_id', 'price', 'sign_ms', 'condition_id']
P = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(f'{ROOT}/calldata_pub/*.parquet'))])
C = pd.read_parquet(f'{ROOT}/calldata_all.parquet', columns=cols + ['event'])
ev_of = C.dropna(subset=['event']).drop_duplicates('condition_id').set_index('condition_id').event.to_dict()
D = pd.concat([P, C.drop(columns='event')]).drop_duplicates(['tx', 'idx'])
D['maker'] = D.maker.str.lower(); D['m8'] = D.maker.str[:10]
D['ev'] = D.condition_id.map(ev_of)
D = D.dropna(subset=['ev'])
D = D[(D.sign_ms > 1.79e12) & (D.sign_ms < H * 1000)]
tk_pub = D[D.idx == -1].drop_duplicates('tx')
msg_rows = []
p4 = tk_pub[tk_pub.maker == P4E]
msg_rows.append(pd.DataFrame({'ev': p4.ev, 't': p4.sign_ms, 'tok': p4.token_id, 'L': p4.price, 'src': 'P4e'}))
for s, lag in SUBLAG.items():
    g = tk_pub[tk_pub.m8 == s]
    msg_rows.append(pd.DataFrame({'ev': g.ev, 't': g.sign_ms - lag, 'tok': g.token_id, 'L': g.price, 'src': s}))
Mg = pd.concat(msg_rows).sort_values(['ev', 't'])
msgs = []
for e, g in Mg.groupby('ev'):
    t = g.t.to_numpy(float)
    keep = np.r_[True, np.diff(t) > 50]
    gg = g[keep]
    msgs.append(gg)
Mg = pd.concat(msgs)
msg_t = {e: np.sort(g.t.to_numpy(float)) for e, g in Mg.groupby('ev')}
own_t = {e: np.sort(g.sign_ms.to_numpy(float)) for e, g in tk.groupby('event')}


def since(times, e, t):
    x = times.get(e)
    if x is None:
        return np.full(len(t), np.inf)
    k = np.searchsorted(x, t, side='right') - 1
    return np.where(k >= 0, t - x[np.maximum(k, 0)], np.inf)

mk = mk.sort_values('sign_ms')
cls = np.empty(len(mk), object)
dm = np.full(len(mk), np.inf); do = np.full(len(mk), np.inf)
for e, idx in mk.groupby('event').groups.items():
    ii = mk.index.get_indexer(idx)
    t = mk.sign_ms.to_numpy(float)[ii]
    dm[ii] = since(msg_t, e, t)
    do[ii] = since(own_t, e, t)
mk['dmsg'] = dm; mk['down'] = do
c = np.where(mk.down <= 150, 'own_msg',
     np.where((mk.down >= 900) & (mk.down <= 1200), 'repair',
      np.where(mk.dmsg <= 150, 'msg',
       np.where((mk.dmsg <= 5000) | (mk.down <= 5000), 'follow', 'quiet'))))
mk['cls'] = c

# anchors
maker_tx = set()
f = pd.read_parquet(f'{ROOT}/chain_fills_1792108800_1792713600.parquet', columns=['tx', 'role'])
maker_tx = set(f[f.role == 'maker'].tx)
lp = np.full(len(mk), np.nan)
for cid, idx in mk.groupby('cid').groups.items():
    fs = glob.glob(f'{ROOT}/tapes/{cid}_tkw.parquet')
    if not fs:
        continue
    d = pd.read_parquet(fs[0])
    d = d[(d.proxyWallet.str.lower() != W) & (~d.transactionHash.isin(maker_tx))].sort_values('timestamp')
    if d.empty:
        continue
    ts = d.timestamp.to_numpy(float)
    p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
    ii = mk.index.get_indexer(idx)
    t = mk.sign_ms.to_numpy(float)[ii] / 1000
    k = np.searchsorted(ts, t, side='left')
    v = np.where(k > 0, p0[np.maximum(k - 1, 0)], np.nan)
    lp[ii] = np.where(mk.oi.to_numpy()[ii] == 0, v, 1 - v)
mk['a_last'] = np.round(lp, 2)
# own previous level on the token / complement
mk['a_own'] = mk.groupby('token_id').price.shift(1)
prev_comp = np.full(len(mk), np.nan)
for cid, g in mk.groupby('cid'):
    g = g.sort_values('sign_ms')
    for z in (0, 1):
        a = g[g.oi == z]; b = g[g.oi != z]
        if a.empty or b.empty:
            continue
        k = np.searchsorted(b.sign_ms.to_numpy(float), a.sign_ms.to_numpy(float), side='left')
        v = np.where(k > 0, b.price.to_numpy(float)[np.maximum(k - 1, 0)], np.nan)
        prev_comp[mk.index.get_indexer(a.index)] = K - v
mk['a_pair'] = np.round(prev_comp, 2)
# message intensity (wallet-independent clock): messages on the event in the previous 5 / 30 s
n5 = np.zeros(len(mk)); n30 = np.zeros(len(mk))
for e, idx in mk.groupby('event').groups.items():
    x = msg_t.get(e)
    if x is None:
        continue
    ii = mk.index.get_indexer(idx)
    t = mk.sign_ms.to_numpy(float)[ii]
    n5[ii] = np.searchsorted(x, t, side='right') - np.searchsorted(x, t - 5000, side='left')
    n30[ii] = np.searchsorted(x, t, side='right') - np.searchsorted(x, t - 30000, side='left')
mk['n5'] = n5; mk['n30'] = n30


def wt(p, a):
    ok = np.isfinite(a)
    tick = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
    return round(float((np.abs(p - a) <= tick + 1e-9)[ok].mean()), 3) if ok.sum() else None, int(ok.sum())

res = {'orders': int(len(mk)), 'messages': int(len(Mg))}
for sp, sel in (('BUILD', mk.gs_ts < VAL0), ('VALIDATE', (mk.gs_ts >= VAL0) & (mk.gs_ts < H))):
    y = mk[sel]
    r = {'orders': int(len(y)), 'all': {nm: wt(y.price.to_numpy(float), y[a].to_numpy(float)) for nm, a in (('last', 'a_last'), ('own', 'a_own'), ('pair', 'a_pair'))}}
    best = np.where(np.isfinite(y.a_own), y.a_own, y.a_last)
    for cl, g in y.groupby('cls'):
        r[cl] = {'share_orders': round(len(g) / len(y), 3), 'share_pnl': round(float(g.pnl.sum() / y.pnl.sum()), 3) if y.pnl.sum() else None,
                 'pnl': round(float(g.pnl.sum()), 1),
                 'last': wt(g.price.to_numpy(float), g.a_last.to_numpy(float)),
                 'own': wt(g.price.to_numpy(float), g.a_own.to_numpy(float)),
                 'pair': wt(g.price.to_numpy(float), g.a_pair.to_numpy(float)),
                 'off_last_c_p10_p50_p90': [round(float(np.nanpercentile((g.price - g.a_last) * 100, q)), 1) for q in (10, 50, 90)]}
    res[sp] = r

# dV per message on the hurt / helped token (msg-class orders; own last level on that token before the message)
rows = []
mm = mk[mk.cls == 'msg']
Mi = {e: g for e, g in Mg.groupby('ev')}
for r_ in mm.itertuples():
    g = Mi.get(r_.event)
    if g is None:
        continue
    k = np.searchsorted(g.t.to_numpy(float), r_.sign_ms, side='right') - 1
    if k < 0:
        continue
    m = g.iloc[k]
    helped = (m.tok == r_.token_id)
    prev = mk[(mk.token_id == r_.token_id) & (mk.sign_ms < m.t)]
    if prev.empty:
        continue
    rows.append({'helped': bool(helped), 'dv': r_.price - prev.price.iloc[-1], 'L': m.L, 'lastp': r_.a_last, 'src': m.src,
                 'same_market': bool(m.tok in set(mk[mk.cid == r_.cid].token_id))})
V = pd.DataFrame(rows)
if len(V):
    out = {}
    for (h, sm), g in V.groupby(['helped', 'same_market']):
        out[f'helped={h}_samemkt={sm}'] = {'n': int(len(g)), 'dv_c_p10_p50_p90': [round(float(np.percentile(g.dv * 100, q)), 1) for q in (10, 50, 90)],
                                            'share_dv_zero': round(float((np.abs(g.dv) < 0.005).mean()), 3)}
    res['dv_by_side'] = out
json.dump(res, open(OUT, 'w'), indent=1)
mk[['salt','sign_ms','cid','oi','event','gs_ts','price','filled','pnl','cls','dmsg','down','a_last','a_own','a_pair','n5','n30']].to_parquet(f'{ROOT}/ledger_rows_iter10.parquet', index=False)
print(json.dumps(res, indent=1)[:2000])
