"""Build point-in-time features for all taker BUY prints (in-play) in the fetched tapes; writes feats.parquet.
Adds event-level (sibling market) features: what moved elsewhere in the same game (base event slug, so the
'-more-markets' / '-halftime-result' / '-total-corners' events of a game are siblings) just before the print."""
import sys, json, glob, re, os
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker/code')
import numpy as np, pandas as pd
from features import market_meta, market_features, payout_map, LAG
from polyrea.analysis.profile import market_family

CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'
H = 1792713600; V0 = 1791849600; B0 = 1790121600
SUFFIX = r'-(more-markets|halftime-result|total-corners|exact-score|player-props|first-half.*|btts.*)$'


def base_slug(s):
    return re.sub(SUFFIX, '', s or '')


def build(tapes, gm, v0=V0, b0=B0):
    metas = {c: market_meta(gm[c]) for c in tapes.cid.unique() if c in gm}
    out = []
    ev_of = {c: base_slug(m['event_slug'] or gm[c].get('slug', '')) for c, m in metas.items()}
    by_event = {}
    for c, e in ev_of.items():
        by_event.setdefault(e, []).append(c)
    tg = dict(tuple(tapes.groupby('cid')))
    series = {}
    for c, d in tg.items():
        m = metas.get(c)
        if not m or len(m['toks']) != 2:
            continue
        d = d.sort_values('timestamp')
        tok = d.asset.astype(str).map({m['toks'][0]: 0, m['toks'][1]: 1})
        ok = tok.notna().to_numpy()
        ts = d.timestamp.to_numpy()[ok].astype(np.int64)
        p0 = np.where(tok.to_numpy()[ok] == 0, d.price.to_numpy()[ok], 1 - d.price.to_numpy()[ok])
        series[c] = (ts, p0)
    for ev, cids in by_event.items():
        for c in cids:
            m = metas[c]
            if c not in tg or c not in series:
                continue
            f = market_features(tg[c], m)
            if f is None:
                continue
            gst = m['gst'] if np.isfinite(m['gst']) else tg[c].timestamp.min()
            f = f[f.is_buy & (f.ts >= gst)].copy()
            if f.empty:
                continue
            T = f.ts.to_numpy() - LAG
            sib_n10 = np.zeros(len(f)); sib_n60 = np.zeros(len(f)); sib_mv30 = np.zeros(len(f)); sib_mv120 = np.zeros(len(f))
            sib_quiet = np.full(len(f), 1e6)
            for s in cids:
                if s == c or s not in series:
                    continue
                sts, sp = series[s]
                if len(sts) == 0:
                    continue
                j = np.searchsorted(sts, T, side='right')
                sib_n10 += j - np.searchsorted(sts, T - 10, side='right')
                sib_n60 += j - np.searchsorted(sts, T - 60, side='right')
                jl = j - 1
                last = np.where(jl >= 0, sp[np.clip(jl, 0, None)], np.nan)
                lts = np.where(jl >= 0, sts[np.clip(jl, 0, None)], -1e9)
                sib_quiet = np.minimum(sib_quiet, T + LAG - lts)
                for dt, arr in ((30, sib_mv30), (120, sib_mv120)):
                    k = np.searchsorted(sts, T - dt, side='right') - 1
                    prev = np.where(k >= 0, sp[np.clip(k, 0, None)], np.nan)
                    mv = np.abs(np.nan_to_num(last - prev))
                    np.maximum(arr, mv, out=arr)
            f['sib_n10'] = sib_n10; f['sib_n60'] = sib_n60; f['sib_mv30'] = sib_mv30; f['sib_mv120'] = sib_mv120
            f['sib_quiet'] = sib_quiet; f['n_sib'] = len(cids) - 1
            f['cid'] = c; f['event'] = m['event_slug']; f['base'] = ev; f['gst'] = gst; f['smt'] = m['smt']; f['line'] = m['line']
            f['fam'] = market_family(m['slug'])
            f['fee_rate'] = m['fee_rate']
            pay = payout_map(gm[c])
            f['payout'] = [pay.get(m['toks'][k], np.nan) for k in f.tok]
            f['period'] = np.where(gst >= v0, 'VALIDATE', np.where(gst >= b0, 'BUILD', 'PRE'))
            out.append(f)
    F = pd.concat(out, ignore_index=True)
    F['is_over'] = F.outcome.str.lower().eq('over'); F['is_under'] = F.outcome.str.lower().eq('under')
    F['is_yes'] = F.outcome.str.lower().eq('yes'); F['is_no'] = F.outcome.str.lower().eq('no')
    return F


def load_tapes():
    files = sorted(glob.glob(f'{CACHE}/tapes/chunk_*.parquet')) + sorted(glob.glob(f'{CACHE}/tapes/chunkB_*.parquet'))
    parts, seen = [], set()
    for fpath in files:
        p = pd.read_parquet(fpath)
        p = p[~p.cid.isin(seen)]
        seen |= set(p.cid.unique()); parts.append(p)
    tapes = pd.concat(parts, ignore_index=True)
    return tapes[tapes.timestamp < H]


if __name__ == '__main__':
    gm = json.load(open(f'{CACHE}/gamma.json'))
    tapes = load_tapes()
    print('tape rows', len(tapes), 'markets', tapes.cid.nunique(), flush=True)
    F = build(tapes, gm)
    F.to_parquet(f'{CACHE}/feats.parquet')
    print('feature rows', len(F), 'wallet', int(F.is_wallet.sum()), 'markets', F.cid.nunique(),
          F.groupby('period').agg(n=('ts', 'size'), w=('is_wallet', 'sum'), m=('cid', 'nunique')).to_dict(), flush=True)
