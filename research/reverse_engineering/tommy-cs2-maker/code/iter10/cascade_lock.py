"""X136 (mechanics panel iter-9 P1): is the wallet's message re-pricing EVENT-locked (its own feed at ~+51 ms) or
LEADER-locked (a book reaction to the fastest co-receiver maker, 0xed446954 at ~+14 ms, or 0x2005d16a at ~+40 ms)?

Development data only: decoded V2 calldata of 16-22 Oct (calldata_all = every tx with the wallet, calldata_pub =
public txs of its markets). Unit = a P4e message: P4e taker signings on an event, merged within 50 ms.

Leader-locked predicts: the wallet's first signing after the message comes AFTER the leader's signing plus the
leader's sign-to-book latency plus a book-reaction time (>= ~20 ms), on (almost) every message where both act;
SD(w - leader) small. Event-locked predicts: a share of messages where the wallet signs before (or within 20 ms
after) the leader; SD(w - leader) ~ sqrt(var_w + var_l).

Because P4e's own jitter is a common mode of all lags (iteration 9: r 0.86), the slope of the wallet's lag on the
leader's lag is reported with the message time re-estimated from OTHER subscribers' taker signings (their fixed lags
subtracted), which removes P4e's jitter.

Also: the sibling check of 0xed446954 against P4e (signature type, builder, salt magnitude, sizes, side mix, takes).
"""
import glob, json, sys
import numpy as np, pandas as pd

ROOT = '.cache/re/tommy-cs2-maker'
OUT = 'research/reverse_engineering/tommy-cs2-maker/results/cascade_lock.json'
W = '0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
P4E = '0x4ebc2722adc772bde8680792d0a6fdf15499a33d'
LEADERS = ['0xed446954', '0x2005d16a', '0x68915897', '0x52661b8e', '0x51dbdd2b', '0x893575c7']
H = 1792713600

cols = ['tx', 'idx', 'maker', 'side', 'token_id', 'price', 'shares', 'sign_ms', 'condition_id', 'sig_type', 'builder', 'salt', 'block']
P = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(f'{ROOT}/calldata_pub/*.parquet'))])
C = pd.read_parquet(f'{ROOT}/calldata_all.parquet', columns=cols + ['event', 'bts'])
ev = C.dropna(subset=['event']).drop_duplicates('condition_id').set_index('condition_id').event.to_dict()
D = pd.concat([P, C.drop(columns=['event', 'bts'])]).drop_duplicates(['tx', 'idx'])
D['maker'] = D.maker.str.lower()
D['ev'] = D.condition_id.map(ev)
D = D.dropna(subset=['ev'])
D = D[(D.sign_ms > 1.79e12) & (D.sign_ms < 1.80e12)]
assert D.sign_ms.max() < H * 1000, 'post-H signing time'
D['m8'] = D.maker.str[:10]

# message clock: P4e taker signings, merged within 50 ms per event
pt = D[(D.maker == P4E) & (D.idx == -1)].drop_duplicates('tx').sort_values(['ev', 'sign_ms'])
msgs = []
for e, g in pt.groupby('ev'):
    t = g.sign_ms.to_numpy(float); tok = g.token_id.to_numpy()
    start = t[0]; toks = {tok[0]}
    for i in range(1, len(t)):
        if t[i] - start <= 50:
            toks.add(tok[i]); continue
        msgs.append((e, start, toks)); start = t[i]; toks = {tok[i]}
    msgs.append((e, start, toks))
print('P4e messages', len(msgs))


def by_ev(df):
    return {e: np.sort(g.sign_ms.to_numpy(float)) for e, g in df.groupby('ev')}

wm = by_ev(D[(D.maker == W) & (D.idx >= 0)].drop_duplicates(['sign_ms', 'token_id', 'price']))
wt = by_ev(D[(D.maker == W) & (D.idx == -1)].drop_duplicates('tx'))
lead_m = {L: by_ev(D[(D.m8 == L) & (D.idx >= 0)].drop_duplicates(['sign_ms', 'token_id', 'price'])) for L in LEADERS}
lead_t = {L: by_ev(D[(D.m8 == L) & (D.idx == -1)].drop_duplicates('tx')) for L in LEADERS}

# other subscribers' taker signings (wallet-independent, non-P4e) for the message re-estimate
SUBS = {'0x2005d16a': None, '0x72aaaaf9': None, '0x2529c68d': None, '0xfe8a28be': None}
sub_t = {s: by_ev(D[(D.m8 == s) & (D.idx == -1)].drop_duplicates('tx')) for s in SUBS}


def first_in(xev, e, t, a, b):
    x = xev.get(e)
    if x is None:
        return np.nan
    lo = np.searchsorted(x, t + a)
    if lo < len(x) and x[lo] < t + b:
        return x[lo] - t
    return np.nan

rows = []
for e, t, toks in msgs:
    r = {'ev': e, 't': t,
         'w_mk': first_in(wm, e, t, 0, 150), 'w_tk': first_in(wt, e, t, 0, 150),
         'w_tk_any': first_in(wt, e, t, -1000, 1000)}
    for L in LEADERS:
        r[f'{L}_mk'] = first_in(lead_m[L], e, t, 0, 150)
        r[f'{L}_tk'] = first_in(lead_t[L], e, t, 0, 150)
    for s in SUBS:
        r[f'sub_{s}'] = first_in(sub_t[s], e, t, 0, 900)
    rows.append(r)
M = pd.DataFrame(rows)
res = {'messages': int(len(M))}

# fixed lags of the other subscribers (median over messages), for the message re-estimate
sub_lag = {s: float(np.nanmedian(M[f'sub_{s}'])) for s in SUBS}
res['sub_lag_median_ms'] = sub_lag

def msg_shift(r):
    """Estimated message time relative to P4e from other subscribers' taker signings (lag removed)."""
    v = [r[f'sub_{s}'] - sub_lag[s] for s in SUBS if np.isfinite(r[f'sub_{s}'])]
    return np.median(v) if v else np.nan
M['j'] = M.apply(msg_shift, axis=1)

out = {}
for L in LEADERS:
    for leg in ('mk', 'tk'):
        for wl in ('w_mk', 'w_tk'):
            m = M[np.isfinite(M[f'{L}_{leg}']) & np.isfinite(M[wl])]
            if len(m) < 5:
                out[f'{L}_{leg}__{wl}'] = {'n': int(len(m))}
                continue
            d = (m[wl] - m[f'{L}_{leg}']).to_numpy()
            x = m[f'{L}_{leg}'].to_numpy(); y = m[wl].to_numpy()
            slope = float(np.polyfit(x, y, 1)[0]) if np.std(x) > 0 else np.nan
            mj = m[np.isfinite(m.j)]
            if len(mj) >= 8:
                xj = (mj[f'{L}_{leg}'] - mj.j).to_numpy(); yj = (mj[wl] - mj.j).to_numpy()
                slope_j = float(np.polyfit(xj, yj, 1)[0]) if np.std(xj) > 0 else np.nan
                corr_j = float(np.corrcoef(xj, yj)[0, 1])
            else:
                slope_j = corr_j = np.nan
            out[f'{L}_{leg}__{wl}'] = {
                'n': int(len(m)), 'leader_lag_med': float(np.median(x)), 'wallet_lag_med': float(np.median(y)),
                'w_minus_leader_p10_p50_p90': [float(np.percentile(d, q)) for q in (10, 50, 90)],
                'share_wallet_first': float(np.mean(d < 0)), 'share_lt_20ms_after': float(np.mean(d < 20)),
                'sd_w_minus_l': float(np.std(d)), 'sd_w': float(np.std(y)), 'sd_l': float(np.std(x)),
                'corr_raw': float(np.corrcoef(x, y)[0, 1]), 'slope_raw': slope,
                'n_with_msg_reestimate': int(len(mj)), 'slope_jitter_removed': slope_j, 'corr_jitter_removed': corr_j}
res['pairs'] = out

# coverage: how often does each leader act (filled order) on messages where the wallet's maker leg acts?
cov = {}
wmask = np.isfinite(M.w_mk)
for L in LEADERS:
    lm = np.isfinite(M[f'{L}_mk'])
    cov[L] = {'wallet_mk_msgs': int(wmask.sum()), 'leader_mk_msgs': int(lm.sum()), 'both': int((wmask & lm).sum()),
              'leader_before_wallet': int((wmask & lm & (M[f'{L}_mk'] < M.w_mk)).sum())}
anyL = np.zeros(len(M), bool); firstL = np.full(len(M), np.inf)
for L in LEADERS:
    v = M[f'{L}_mk'].to_numpy(); firstL = np.where(np.isfinite(v), np.minimum(firstL, v), firstL)
lead_before = wmask & (firstL < M.w_mk.to_numpy() - 20)
cov['any_leader_signed_20ms_before_wallet_mk'] = {'share_of_wallet_mk_msgs': float(lead_before.sum() / max(wmask.sum(), 1))}
res['coverage'] = cov

# wallet lag distribution on messages with vs without a leader filled order (censored, descriptive)
for nm, mask in (('with_ed', wmask & np.isfinite(M['0xed446954_mk'])), ('without_any_leader', wmask & ~np.isfinite(firstL))):
    v = M.w_mk[mask].to_numpy()
    res[f'wallet_mk_lag_{nm}'] = {'n': int(mask.sum()), 'p10_p50_p90': [float(np.percentile(v, q)) for q in (10, 50, 90)] if len(v) else None}

# sibling fingerprint: 0xed446954 vs P4e vs wallet
fp = {}
for nm, sel in (('P4e', D.maker == P4E), ('ed446954', D.m8 == '0xed446954'), ('wallet', D.maker == W), ('2005d16a', D.m8 == '0x2005d16a')):
    g = D[sel]
    sz = g.shares.round(2)
    fp[nm] = {'orders': int(len(g)), 'taker_orders': int((g.idx == -1).sum()), 'maker_orders': int((g.idx >= 0).sum()),
              'sig_type': g.sig_type.value_counts().head(3).to_dict(),
              'builder_nonzero': float((g.builder != '0x' + '0' * 64).mean()),
              'salt_log10_med': float(np.median(np.log10(g.salt.astype(float).clip(lower=1)))),
              'top_sizes': {str(k): int(v) for k, v in sz.value_counts().head(6).items()},
              'buy_share': float((g.side == 0).mean()),
              'events': int(g.ev.nunique())}
res['fingerprints'] = fp
# same-tx co-occurrence: is 0xed446954 a maker inside P4e's FAK txs (filled by P4e) and how often
p4e_tx = set(D[(D.maker == P4E) & (D.idx == -1)].tx)
edm = D[(D.m8 == '0xed446954') & (D.idx >= 0)]
res['ed_maker_orders_filled_by_P4e_share'] = float(edm.tx.isin(p4e_tx).mean())
wmk = D[(D.maker == W) & (D.idx >= 0)]
res['wallet_maker_orders_filled_by_P4e_share'] = float(wmk.tx.isin(p4e_tx).mean())

json.dump(res, open(OUT, 'w'), indent=1, default=float)
print(json.dumps({k: v for k, v in res.items() if k != 'pairs'}, indent=1, default=float)[:3500])
for k, v in out.items():
    if v.get('n', 0) >= 5:
        print(k, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()})
