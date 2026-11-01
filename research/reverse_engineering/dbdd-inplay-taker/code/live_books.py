"""X2 / A7 / A5a on the live lab (development blocks only, via tools/live.py iter_live).

For every wallet fill in a development unit covered by the recorder, reconstruct the book of the bought token at
the order's signing time (B1 calldata), and compare with control times in the same market and token.
Writes .cache/re/dbdd-inplay-taker/live_books.parquet (one row per decision/control) and the reduced
per-token top-of-book arrays (live_books_arrays.npz) and last trades (live_trades.json) for reuse.
"""
import sys, os, glob, json, zlib, time
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE
import pandas as pd, numpy as np
import live

BLOCKS = [(1793449098, 1793469600), (1793512800, 1793534400)]   # recorder start .. development block ends
gm = json.load(open(f'{CACHE}/gamma2.json'))


def safe(feed, a, b):
    """iter_live hour by hour; an hour file damaged by a crash is read up to the damage."""
    h = int(a)
    while h < b:
        try:
            for r in live.iter_live(feed, h, min(h + 3600, b)):
                yield r
        except (zlib.error, EOFError, OSError):
            pass
        h = (h // 3600 + 1) * 3600


def load_maps():
    tok0, idx_of, ev_of, cid_of_tok = {}, {}, {}, {}
    for c, m in gm.items():
        try:
            toks = json.loads(m['clobTokenIds']) if isinstance(m.get('clobTokenIds'), str) else m.get('clobTokenIds')
        except Exception:
            continue
        if not toks or len(toks) != 2:
            continue
        tok0[c] = toks[0]
        idx_of[toks[0]], idx_of[toks[1]] = 0, 1
        cid_of_tok[toks[0]], cid_of_tok[toks[1]] = c, c
        ev_of[c] = ((m.get('events') or [{}])[0] or {}).get('slug')
    return tok0, idx_of, ev_of, cid_of_tok


if __name__ == '__main__':
    act = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/activity/dev_*.parquet')])
    act = act[act.conditionId.map(lambda c: (gm.get(c) or {}).get('sealed', 1) == 0)]
    tk = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/calldata/taker_*.parquet')])
    d = act.merge(tk[tk.ok == 1][['tx', 't_ts_ms', 't_px', 't_usdc', 't_fill', 't_token']], left_on='transactionHash', right_on='tx')
    d = d[[any(a <= x < b for a, b in BLOCKS) for x in d.timestamp]]
    print('wallet decisions in live blocks', len(d), flush=True)
    tok0, idx_of, ev_of, cid_of_tok = load_maps()
    need_cids = set(d.conditionId)
    need_events = {ev_of.get(c) for c in need_cids}
    sib_cids = {c for c, e in ev_of.items() if e in need_events}
    want = {tok0[c] for c in sib_cids if c in tok0}
    print('markets', len(need_cids), 'events', len(need_events), 'sibling markets', len(sib_cids), 'tokens', len(want), flush=True)
    books = {t: [] for t in want}
    trades = {t: [] for t in want}
    t0 = time.time()
    n = 0
    for a, b in BLOCKS:
        for r in safe('clob_wallets', a, b):
            n += 1
            tkn = r.get('a')
            if tkn not in want:
                continue
            k = r.get('k')
            if k in ('q', 'f'):
                bids = r.get('b') or []
                asks = r.get('o') or []
                bb = max(bids, key=lambda x: float(x[0])) if bids else None
                ba = min(asks, key=lambda x: float(x[0])) if asks else None
                books[tkn].append((r['t'], float(bb[0]) if bb else np.nan, float(bb[1]) if bb else 0.0,
                                   float(ba[0]) if ba else np.nan, float(ba[1]) if ba else 0.0))
            elif k == 'x':
                trades[tkn].append((r['t'], float(r.get('p') or np.nan), float(r.get('z') or 0), r.get('d'), r.get('h')))
    print('records scanned', n, round(time.time() - t0), 's', flush=True)
    B = {t: np.array(v, dtype=float) for t, v in books.items() if v}
    for t in B:
        B[t] = B[t][np.argsort(B[t][:, 0], kind='stable')]
    np.savez_compressed(f'{CACHE}/live_books_arrays.npz', **{f't{t}': v for t, v in B.items()})
    json.dump({t: v for t, v in trades.items() if v}, open(f'{CACHE}/live_trades.json', 'w'))

    def state(tkn0, ts_ms, idx):
        arr = B.get(tkn0)
        if arr is None:
            return None
        i = np.searchsorted(arr[:, 0], ts_ms, side='right') - 1
        if i < 0:
            return None
        row = arr[i]
        if idx == 0:
            ask, asz, bid, col = row[3], row[4], row[1], 3
        else:
            ask, asz, bid, col = 1 - row[1], row[2], 1 - row[3], 1
        j = i
        while j > 0 and arr[j - 1, col] == row[col]:
            j -= 1
        age = (ts_ms - arr[j, 0]) / 1000.0
        mid_now = (row[1] + row[3]) / 2

        def mid_at(dt):
            k = np.searchsorted(arr[:, 0], ts_ms - dt * 1000, side='right') - 1
            if k < 0:
                return np.nan
            return (arr[k, 1] + arr[k, 3]) / 2
        mv = {f'mv{dt}': ((mid_now - mid_at(dt)) * (1 if idx == 0 else -1)) for dt in (5, 10, 30, 60, 300)}
        upd10 = int(np.sum((arr[:, 0] > ts_ms - 10000) & (arr[:, 0] <= ts_ms)))
        return dict(ask=ask, ask_sz=asz, bid=bid, spread=ask - bid, ask_age=age, book_updates10=upd10,
                    staleness=(ts_ms - row[0]) / 1000.0, **mv)

    def sib_move(cid, ts_ms, dt):
        ev = ev_of.get(cid)
        best = 0.0
        for c in sib_cids:
            if c == cid or ev_of.get(c) != ev or c not in tok0:
                continue
            arr = B.get(tok0[c])
            if arr is None:
                continue
            i = np.searchsorted(arr[:, 0], ts_ms, side='right') - 1
            k = np.searchsorted(arr[:, 0], ts_ms - dt * 1000, side='right') - 1
            if i < 0 or k < 0:
                continue
            m1, m0 = (arr[i, 1] + arr[i, 3]) / 2, (arr[k, 1] + arr[k, 3]) / 2
            if np.isfinite(m1) and np.isfinite(m0):
                best = max(best, abs(m1 - m0))
        return best

    rows = []
    rng = np.random.default_rng(7)
    for r in d.itertuples(index=False):
        c = r.conditionId
        if c not in tok0:
            continue
        idx = int(r.outcomeIndex)
        ts = float(r.t_ts_ms)
        s = state(tok0[c], ts, idx)
        if s is None:
            continue
        rows.append(dict(kind='wallet', cid=c, idx=idx, ts_ms=ts, limit=r.t_px, usdc=r.t_usdc, fill_usdc=r.t_fill,
                         fill_px=r.price, sib10=sib_move(c, ts, 10), sib30=sib_move(c, ts, 30), sib60=sib_move(c, ts, 60), **s))
        for j in range(5):
            tc = ts + rng.uniform(-1800, 1800) * 1000
            s2 = state(tok0[c], tc, idx)
            if s2 is None:
                continue
            rows.append(dict(kind='control', cid=c, idx=idx, ts_ms=tc, sib10=sib_move(c, tc, 10), sib30=sib_move(c, tc, 30),
                             sib60=sib_move(c, tc, 60), **s2))
    out = pd.DataFrame(rows)
    out.to_parquet(f'{CACHE}/live_books.parquet')
    w = out[out.kind == 'wallet']
    cdf = out[out.kind == 'control']
    print('wallet rows', len(w), 'control rows', len(cdf))
    print('limit - best ask at signing: q', np.round(np.nanquantile(w.limit - w.ask, [0.05, 0.25, 0.5, 0.75, 0.95]), 4),
          'share |diff|<0.005', round(float(np.mean(np.abs(w.limit - w.ask) < 0.005)), 3))
    print('order usdc / best-ask depth usdc: q', np.round(np.nanquantile(w.usdc / (w.ask_sz * w.ask), [0.1, 0.25, 0.5, 0.75, 0.9]), 2))
    for col in ['ask_age', 'book_updates10', 'spread', 'mv5', 'mv10', 'mv30', 'mv60', 'mv300', 'sib10', 'sib30', 'sib60', 'staleness']:
        print(f'{col:14s} wallet med {np.nanmedian(w[col]):8.4f} mean {np.nanmean(w[col]):8.4f} | '
              f'control med {np.nanmedian(cdf[col]):8.4f} mean {np.nanmean(cdf[col]):8.4f}')
