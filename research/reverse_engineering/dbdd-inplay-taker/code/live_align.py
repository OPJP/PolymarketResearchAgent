"""Clock alignment and the book just before each wallet decision (live lab, development blocks).

1. Find the wallet's own trades in the recorder's last-trade stream (k='x', field h = tx hash) and measure
   recv_ms(own trade) - signing_ms: the client-to-CLOB-to-recorder delay including any clock offset.
2. For each decision, take the book strictly before the wallet's own trade reached the recorder, and describe
   what changed in the 10 s before signing: best ask moves of the bought token, trades by others (k='x').
Writes results/iter2_live_align.json.
"""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE, ROOT
import pandas as pd, numpy as np
from live_books import load_maps, BLOCKS

WS = os.path.join(ROOT, 'research', 'reverse_engineering', 'dbdd-inplay-taker')
gm = json.load(open(f'{CACHE}/gamma2.json'))
tok0, idx_of, ev_of, cid_of_tok = load_maps()
Z = np.load(f'{CACHE}/live_books_arrays.npz')
B = {k[1:]: Z[k] for k in Z.files}
TR = json.load(open(f'{CACHE}/live_trades.json'))
act = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/activity/dev_*.parquet')])
act = act[act.conditionId.map(lambda c: (gm.get(c) or {}).get('sealed', 1) == 0)]
tk = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/calldata/taker_*.parquet')])
d = act.merge(tk[tk.ok == 1][['tx', 't_ts_ms', 't_px', 't_usdc', 't_fill']], left_on='transactionHash', right_on='tx')
d = d[[any(a <= x < b for a, b in BLOCKS) for x in d.timestamp]].copy()
own_tx = set(d.tx.str.lower())
# own trades in the x stream
xrec = []
for t, lst in TR.items():
    for (ms, p, z, side, h) in lst:
        xrec.append((t, ms, p, z, side, (h or '').lower()))
X = pd.DataFrame(xrec, columns=['tok', 'ms', 'p', 'z', 'side', 'h'])
X['own'] = X.h.isin(own_tx)
first_own = X[X.own].groupby('h').ms.min()
d['own_recv_ms'] = d.tx.str.lower().map(first_own)
lag = (d.own_recv_ms - d.t_ts_ms) / 1000.0
res = {'n_decisions': int(len(d)), 'n_with_own_trade_in_stream': int(lag.notna().sum()),
       'own_trade_recv_minus_sign_s_q': {str(q): float(np.nanquantile(lag, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)} if lag.notna().any() else None,
       'block_minus_sign_s_median': float(np.median(d.timestamp - d.t_ts_ms / 1000.0))}
print(res)

rows = []
for r in d.itertuples(index=False):
    c = r.conditionId
    if c not in tok0 or tok0[c] not in B:
        continue
    arr = B[tok0[c]]
    idx = int(r.outcomeIndex)
    cut = r.own_recv_ms if np.isfinite(r.own_recv_ms) else r.t_ts_ms + 300   # book strictly before its own trade
    i = np.searchsorted(arr[:, 0], cut, side='left') - 1
    if i < 1:
        continue
    row = arr[i]
    ask = row[3] if idx == 0 else 1 - row[1]
    asz = row[4] if idx == 0 else row[2]
    col = 3 if idx == 0 else 1
    j = i
    while j > 0 and arr[j - 1, col] == row[col]:
        j -= 1
    ask_age = (r.t_ts_ms - arr[j, 0]) / 1000.0
    prev_ask = (arr[j - 1, 3] if idx == 0 else 1 - arr[j - 1, 1]) if j > 0 else np.nan
    k10 = np.searchsorted(arr[:, 0], r.t_ts_ms - 10000, side='right') - 1
    ask10 = (arr[k10, 3] if idx == 0 else 1 - arr[k10, 1]) if k10 >= 0 else np.nan
    bid10 = (arr[k10, 1] if idx == 0 else 1 - arr[k10, 3]) if k10 >= 0 else np.nan
    bid = row[1] if idx == 0 else 1 - row[3]
    # others' trades in this market (either token's stream: only token 0 is recorded) in the 10 s before signing
    tx = X[(X.tok == tok0[c]) & (~X.own) & (X.ms <= r.t_ts_ms) & (X.ms > r.t_ts_ms - 10000)]
    rows.append(dict(cid=c, idx=idx, limit=r.t_px, ask_before_own=ask, ask_sz=asz, ask_age_at_sign=ask_age,
                     prev_ask=prev_ask, ask_change=ask - prev_ask, ask_minus_ask10=ask - ask10, bid_minus_bid10=bid - bid10,
                     others_trades_10s=len(tx), usdc=r.t_usdc, fill=r.t_fill, fill_px=r.price))
A = pd.DataFrame(rows)
A.to_parquet(f'{CACHE}/live_align.parquet')
if len(A):
    res.update({
        'n_rows': int(len(A)),
        'limit_minus_ask_before_own_q': {str(q): float(np.nanquantile(A.limit - A.ask_before_own, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
        'share_limit_eq_ask_before_own': float(np.mean(np.abs(A.limit - A.ask_before_own) < 0.005)),
        'ask_age_at_sign_q': {str(q): float(np.nanquantile(A.ask_age_at_sign, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
        'share_ask_changed_within_1s_before_sign': float(np.mean((A.ask_age_at_sign >= 0) & (A.ask_age_at_sign < 1))),
        'share_ask_appeared_after_sign': float(np.mean(A.ask_age_at_sign < 0)),
        'last_ask_change_sign': {'down': float(np.mean(A.ask_change < 0)), 'up': float(np.mean(A.ask_change > 0))},
        'ask_minus_ask10_q': {str(q): float(np.nanquantile(A.ask_minus_ask10, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
        'bid_minus_bid10_q': {str(q): float(np.nanquantile(A.bid_minus_bid10, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
        'share_others_trade_in_10s_before': float(np.mean(A.others_trades_10s > 0)),
        'order_usdc_over_ask_depth_usdc_q': {str(q): float(np.nanquantile(A.usdc / (A.ask_sz * A.ask_before_own), q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
    })
json.dump(res, open(os.path.join(WS, 'results', 'iter2_live_align.json'), 'w'), indent=1)
for k, v in res.items():
    print(k, v)
