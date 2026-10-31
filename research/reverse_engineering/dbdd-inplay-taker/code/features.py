"""Point-in-time features for every taker print in a market's tape.

Decision-time convention: a print stamped T may have been decided up to 2 s earlier, so every
feature of a print at T uses only tape prints with timestamp <= T - 2 (LAG), market metadata known
at listing, and (for ESPN) plays whose wallclock + >= 5 s <= T - 2.
"""
import json, re
import numpy as np, pandas as pd

W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
LAG = 2
SOCCER_PREFIX = None  # soccer detected from slug prefix / title below


def market_meta(m):
    toks = [str(x) for x in json.loads(m.get('clobTokenIds') or '[]')]
    outs = json.loads(m.get('outcomes') or '[]')
    try:
        gst = pd.Timestamp(m['gameStartTime']).timestamp() if m.get('gameStartTime') else np.nan
    except Exception:
        gst = np.nan
    fee = (m.get('feeSchedule') or {})
    try:
        fee_rate = float(fee.get('rate', np.nan)) if isinstance(fee, dict) else np.nan
    except Exception:
        fee_rate = np.nan
    q = m.get('question') or ''
    mm = re.search(r'O/U (\d+\.?\d*)', q)
    line = float(mm.group(1)) if mm else (float(m['line']) if m.get('line') not in (None, '') else np.nan)
    ev = (m.get('events') or [{}])[0] if m.get('events') else {}
    return {'toks': toks, 'outs': outs, 'gst': gst, 'smt': m.get('sportsMarketType') or '', 'line': line,
            'fee_rate': fee_rate, 'question': q, 'slug': m.get('slug') or '', 'event_slug': ev.get('slug') or '',
            'series': ev.get('seriesSlug') or ''}


def payout_map(m):
    try:
        prices = [float(x) for x in json.loads(m.get('outcomePrices') or '[]')]
        toks = [str(x) for x in json.loads(m.get('clobTokenIds') or '[]')]
    except Exception:
        return {}
    resolved = m.get('umaResolutionStatus') == 'resolved' or (m.get('closed') and prices and max(prices) >= 0.999)
    return {t: p for t, p in zip(toks, prices)} if resolved else {}


def _at(ts_sorted, vals, q):
    """Value of the last element with ts <= q (nan if none)."""
    j = np.searchsorted(ts_sorted, q, side='right') - 1
    out = np.where(j >= 0, vals[np.clip(j, 0, None)], np.nan)
    return out, j


def market_features(tape, meta):
    """tape: DataFrame of one market's taker rows. Returns one row per taker print (BUY and SELL) with features."""
    toks = meta['toks']
    if len(toks) != 2 or tape.empty:
        return None
    d = tape.sort_values(['timestamp']).reset_index(drop=True)
    d['tok'] = d.asset.astype(str).map({toks[0]: 0, toks[1]: 1})
    d = d[d.tok.notna()].reset_index(drop=True)
    if d.empty:
        return None
    ts = d.timestamp.to_numpy().astype(np.int64)
    tok = d.tok.to_numpy().astype(int)
    px = d.price.to_numpy().astype(float)
    usd = (d['size'] * d.price).to_numpy().astype(float)
    p0 = np.where(tok == 0, px, 1 - px)  # implied price of token 0 at each print
    is_buy = (d.side == 'BUY').to_numpy()
    # direction of each print in token-0 terms: +1 if it pushes token0 up (buy t0 or sell t1)
    dir0 = np.where(is_buy == (tok == 0), 1.0, -1.0)
    cum_n = np.arange(1, len(ts) + 1)
    cum_usd = np.cumsum(usd)
    cum_flow0 = np.cumsum(dir0 * usd)
    T = ts - LAG
    last_p0, j = _at(ts, p0, T)
    n_before = j + 1
    last_ts = np.where(j >= 0, ts[np.clip(j, 0, None)], np.nan)
    sgn = np.where(tok == 0, 1.0, -1.0)  # convert token-0 quantities to the print's token
    f = {}
    f['quiet'] = ts - last_ts                              # seconds since the last earlier print (>= LAG)
    f['last_pk'] = np.where(tok == 0, last_p0, 1 - last_p0)
    f['dp_print'] = px - f['last_pk']                      # print price vs last print price of its token
    for dt in (10, 30, 60, 300, 900):
        prev, _ = _at(ts, p0, T - dt)
        f[f'mv{dt}'] = sgn * (last_p0 - prev)               # move of the print's token over (T-dt, T]
        jj = np.searchsorted(ts, T - dt, side='right') - 1
        base_n = np.where(jj >= 0, cum_n[np.clip(jj, 0, None)], 0)
        base_u = np.where(jj >= 0, cum_usd[np.clip(jj, 0, None)], 0.0)
        base_f = np.where(jj >= 0, cum_flow0[np.clip(jj, 0, None)], 0.0)
        cur_n = np.where(j >= 0, cum_n[np.clip(j, 0, None)], 0)
        cur_u = np.where(j >= 0, cum_usd[np.clip(j, 0, None)], 0.0)
        cur_f = np.where(j >= 0, cum_flow0[np.clip(j, 0, None)], 0.0)
        if dt in (10, 60, 300):
            f[f'n{dt}'] = cur_n - base_n
            f[f'usd{dt}'] = cur_u - base_u
            f[f'flow{dt}'] = sgn * (cur_f - base_f)        # signed taker flow toward the print's token
    # max/min of token price over last 60 s (range) -- via rolling on p0 using index windows
    f['n_before'] = n_before
    f['minute'] = (ts - meta['gst']) / 60.0 if np.isfinite(meta['gst']) else np.nan
    f['price'] = px
    f['tok'] = tok
    f['is_buy'] = is_buy
    f['ts'] = ts
    f['usd'] = usd
    f['is_wallet'] = (d.proxyWallet.str.lower() == W).to_numpy()
    out = pd.DataFrame(f)
    out['outcome'] = [meta['outs'][k] if k < len(meta['outs']) else '' for k in tok]
    out['tx'] = d.transactionHash.to_numpy()
    return out
