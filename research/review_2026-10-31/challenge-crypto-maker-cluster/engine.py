"""PIT features + exact maker-row fill simulator (scratch code for the challenge).

Tape availability: a trade stamped at second ts is treated as visible at ts + TAPE_LAG (block time).
Decision at t uses only trades with ts + TAPE_LAG <= t - L (L = extra reaction latency) and spot available at t - L.
"""
import sys; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from base import *
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue
TAPE_LAG = 2

def trade_stream(M):
    """All maker rows as Up-space trade prices (exact level prices)."""
    up_px = np.where(M.is_up, M.price, 1 - M.price)
    return pd.DataFrame({'condition_id': M.condition_id.values, 'ts': M.ts.values, 'up_px': up_px, 'sz': M.sz.values})

def ref_up_at(ts_tr, px_tr, t_query, L):
    """Last Up-space trade price visible at t_query - L (visible = ts + TAPE_LAG). NaN if none."""
    i = np.searchsorted(ts_tr + TAPE_LAG, t_query - L, side='right') - 1
    return np.where(i >= 0, px_tr[np.clip(i, 0, None)], np.nan)

def ref_up_lag(ts_tr, px_tr, t_query, L, back):
    return ref_up_at(ts_tr, px_tr, t_query - back, L)

def preemption_events(M):
    """Events that would fill a resting bid on side s at q if p_eff < q (strict) or == q (touch)."""
    # maker BUY s at p -> bid-side event on s with p_eff = p ; maker SELL s' at p' -> event on s with p_eff = 1 - p'
    buy = M[M.side == 'BUY']; sell = M[M.side == 'SELL']
    e1 = pd.DataFrame({'condition_id': buy.condition_id.values, 'ts': buy.ts.values, 'bid_up': buy.is_up.values, 'p_eff': buy.price.values, 'sz': buy.sz.values})
    e2 = pd.DataFrame({'condition_id': sell.condition_id.values, 'ts': sell.ts.values, 'bid_up': ~sell.is_up.values, 'p_eff': 1 - sell.price.values, 'sz': sell.sz.values})
    return pd.concat([e1, e2], ignore_index=True)

def simulate(windows, M, quote_fn, R=5, size_shares=20.0, queue_share=0.0, exclude=None):
    """quote_fn(w, ticks, tr_ts, tr_px) -> (q_up, q_dn) arrays (NaN = no quote), decided with PIT data only.
    queue_share: fraction of at-touch volume we receive (0 = strict trade-through only)."""
    by = {w.condition_id: w for w in windows}
    Mx = M if exclude is None else M[~M.wallet.isin(exclude)]
    E = preemption_events(Mx)
    TR = trade_stream(M)  # reference uses the full public tape
    Eg = dict(tuple(E.groupby('condition_id'))); TRg = dict(tuple(TR.sort_values(['condition_id', 'ts'], kind='stable').groupby('condition_id')))
    out = []
    for cid, w in by.items():
        if w.up_payout is None or cid not in Eg or cid not in TRg: continue
        ticks = np.arange(w.start_ts, w.end_ts, R)
        tr = TRg[cid]; q_up, q_dn = quote_fn(w, ticks, tr.ts.to_numpy(), tr.up_px.to_numpy())
        e = Eg[cid]; ts = e.ts.to_numpy(); j = (ts - w.start_ts - 1) // R
        ok = (ts > w.start_ts) & (j >= 0) & (j < len(ticks))
        if not ok.any(): continue
        j, bid_up, p, sz = j[ok], e.bid_up.to_numpy()[ok], e.p_eff.to_numpy()[ok], e.sz.to_numpy()[ok]
        for side_up, q in ((True, q_up), (False, q_dn)):
            qj = q[j]
            mine = (bid_up == side_up) & np.isfinite(qj)
            thr = mine & (p < qj - 1e-9)
            touch = mine & (np.abs(p - qj) <= 1e-9)
            avail = np.bincount(j[thr], weights=sz[thr], minlength=len(ticks)) + queue_share * np.bincount(j[touch], weights=sz[touch], minlength=len(ticks))
            filled = np.where(np.isfinite(q), np.minimum(size_shares, avail), 0.0)
            idx = np.nonzero(filled > 1e-9)[0]
            pay = w.up_payout if side_up else 1 - w.up_payout
            for i in idx:
                out.append((cid, int(ticks[i]), side_up, float(q[i]), float(filled[i]), float(filled[i] * (pay - q[i])), w.end_ts))
    return summarize(out)

def summarize(out):
    if not out: return {'fills': 0}
    f = pd.DataFrame(out, columns=['condition_id', 'ts', 'is_up', 'price', 'shares', 'pnl', 'end_ts'])
    pw = f.groupby('condition_id').pnl.sum()
    t = hac_t_test(pw.to_numpy()); usd = float((f.price * f.shares).sum())
    bp = stationary_bootstrap_pvalue(pw.to_numpy(), n_boot=2000).p_value if len(pw) >= 5 else None
    return {'fills': int(len(f)), 'windows': int(pw.size), 'usd': usd, 'pnl': float(f.pnl.sum()), 'ret': float(f.pnl.sum() / usd) if usd else None,
            'per_window_t': t.statistic, 'p': t.p_value, 'boot_p': bp, 'fill_win_rate': float((f.pnl > 0).mean())}

def auc(score, y):
    from scipy import stats
    ok = np.isfinite(score); s, yy = score[ok], y[ok]
    n1 = int(yy.sum()); n0 = len(yy) - n1
    if n1 == 0 or n0 == 0: return float('nan')
    r = stats.rankdata(s)
    return float((r[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

def circular_shift_null(df, y, score, n_perm=500, seed=0):
    """Null: within each window, circularly shift the wallet-label sequence (time-ordered) by a random offset.
    Keeps per-window counts and label clustering, destroys alignment between labels and the score."""
    rng = np.random.default_rng(seed)
    order = np.lexsort((df.ts.to_numpy(), df.condition_id.to_numpy()))
    cid = df.condition_id.to_numpy()[order]; ys = y[order]; sc = score[order]
    bounds = np.r_[0, np.nonzero(cid[1:] != cid[:-1])[0] + 1, len(cid)]
    obs = auc(sc, ys); null = []
    for _ in range(n_perm):
        yp = np.empty_like(ys)
        for a, b in zip(bounds[:-1], bounds[1:]):
            n = b - a; k = rng.integers(0, n) if n > 1 else 0
            yp[a:b] = np.roll(ys[a:b], k)
        null.append(auc(sc, yp))
    null = np.array(null)
    return {'auc': obs, 'null_mean': float(np.nanmean(null)), 'null_p95': float(np.nanpercentile(null, 95)), 'null_p99': float(np.nanpercentile(null, 99)), 'perm_p': float((1 + np.sum(null >= obs)) / (1 + len(null)))}
