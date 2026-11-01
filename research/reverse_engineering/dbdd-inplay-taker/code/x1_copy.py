"""X1: strong-form copy trading. For each wallet in-play BUY print, other wallets' BUY prints on the same token
0-30 s before it (leader candidates) and 0-30 s after it (followers). Strong form: one leader with many pairs,
a stable size ratio (log-ratio sd small) and a stable lag, far above a +-15 min time-shift null.
Uses the sampled tapes (tapes2, BUILD + VALIDATE units). Writes results/iter2_x1_copy.json."""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE, ROOT
import pandas as pd, numpy as np

WS = os.path.join(ROOT, 'research', 'reverse_engineering', 'dbdd-inplay-taker')
W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
H = 1792713600
gm = json.load(open(f'{CACHE}/gamma2.json'))
pairs, nulls, n_w, n_w_any = [], [], 0, 0
fol = []
for f in glob.glob(f'{CACHE}/tapes2/*.parquet'):
    c = os.path.basename(f)[:-8]
    m = gm.get(c) or {}
    u = m.get('unit_ts')
    if not u or u >= H:
        continue
    try:
        d = pd.read_parquet(f, columns=['timestamp', 'side', 'proxyWallet', 'asset', 'price', 'size'])
    except Exception:
        continue
    d = d[(d.side == 'BUY') & (d.timestamp >= u)]
    if d.empty:
        continue
    d['usd'] = d.price * d['size']
    d['pw'] = d.proxyWallet.str.lower()
    for a, g in d.groupby('asset'):
        g = g.sort_values('timestamp')
        w = g[g.pw == W]
        o = g[g.pw != W]
        if w.empty or o.empty:
            continue
        ot, ou, op = o.timestamp.values, o.usd.values, o.pw.values
        for r in w.itertuples(index=False):
            n_w += 1
            for shift, store in ((0, pairs), (900, nulls), (-900, nulls)):
                t = r.timestamp + shift
                lo, hi = np.searchsorted(ot, t - 30, 'left'), np.searchsorted(ot, t, 'left')   # strictly before
                for k in range(lo, hi):
                    store.append((op[k], t - ot[k], np.log(r.usd / max(ou[k], 1e-6)), shift))
                if shift == 0 and hi > lo:
                    n_w_any += 1
            lo, hi = np.searchsorted(ot, r.timestamp, 'right'), np.searchsorted(ot, r.timestamp + 30, 'right')
            for k in range(lo, hi):
                fol.append((op[k], ot[k] - r.timestamp))
P = pd.DataFrame(pairs, columns=['leader', 'lag', 'lr', 'shift'])
N = pd.DataFrame(nulls, columns=['leader', 'lag', 'lr', 'shift'])
F = pd.DataFrame(fol, columns=['follower', 'lag'])
res = {'wallet_prints': int(n_w), 'share_with_any_same_token_buy_0_30s_before': n_w_any / max(n_w, 1),
       'pairs': int(len(P)), 'null_pairs_per_shift': len(N) / 2}
lc = P.leader.value_counts()
nc = N.leader.value_counts() / 2
top = []
for L, n in lc.head(30).items():
    g = P[P.leader == L]
    top.append({'leader': L, 'pairs': int(n), 'null_pairs': float(nc.get(L, 0)), 'ratio_vs_null': float(n / max(nc.get(L, 0), 0.5)),
                'share_of_wallet_prints': float(n / max(n_w, 1)), 'lag_med': float(g.lag.median()), 'lag_iqr': float(g.lag.quantile(.75) - g.lag.quantile(.25)),
                'logratio_sd': float(g.lr.std()), 'logratio_med': float(g.lr.median())})
res['top_leaders'] = top
fcnt = F.follower.value_counts()
res['top_followers'] = [{'follower': k, 'pairs': int(v), 'lag_med': float(F[F.follower == k].lag.median())} for k, v in fcnt.head(10).items()]
# strong form: any leader with >= 2% of wallet prints, >= 5x null, log-ratio sd < 0.3, lag IQR < 5 s
strong = [t for t in top if t['share_of_wallet_prints'] >= 0.02 and t['ratio_vs_null'] >= 5 and t['logratio_sd'] < 0.3 and t['lag_iqr'] < 5]
res['strong_form_leaders'] = strong
res['max_share_any_leader'] = max((t['share_of_wallet_prints'] for t in top), default=0)
json.dump(res, open(os.path.join(WS, 'results', 'iter2_x1_copy.json'), 'w'), indent=1)
print({k: v for k, v in res.items() if k not in ('top_leaders', 'top_followers')})
for t in top[:12]:
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in t.items()})
print('followers', res['top_followers'][:5])
