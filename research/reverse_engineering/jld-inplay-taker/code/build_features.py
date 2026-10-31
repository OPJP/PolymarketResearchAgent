"""Point-in-time feature table for every in-play taker BUY print in the markets the wallet traded.

Usage: python build_features.py OUT.parquet GST_LO GST_HI [D]
  GST_LO/GST_HI: game-start range of markets to include (must be < H for development).
Features (all PIT; see common.py): own-market tape state from seconds <= t-1, event-level others' activity,
moneyline momentum toward the bought team, ESPN state known at wallclock + D (D >= 5).
"""
import sys, json, time
import numpy as np, pandas as pd
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/jld-inplay-taker/code')
from common import *

OUT, LO, HI = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
D = int(sys.argv[4]) if len(sys.argv) > 4 else 5
assert D >= 5 and HI <= H
t0 = time.time()
gm = json.load(open(f'{CACHE}/gamma.json'))
T = load_tapes()
M = market_table(gm, T.cid.unique())
M = M[(M.gst >= LO) & (M.gst < HI)]
T = T[T.cid.isin(set(M.cid))]
EG = pd.read_parquet(f'{CACHE}/espn_games.parquet').drop_duplicates('event_slug').set_index('event_slug')
EP = pd.read_parquet(f'{CACHE}/espn_plays.parquet')
EPg = dict(tuple(EP.groupby('event_slug')))
print('markets', len(M), 'prints', len(T), 'events', M.event_slug.nunique(), 'espn games', len(set(M.event_slug) & set(EG.index)), flush=True)

Tg = dict(tuple(T.groupby('cid')))
frames = []
for ev, Me in M.groupby('event_slug'):
    g = EG.loc[ev] if ev in EG.index else None
    eg = EspnGame(g, EPg[ev], D) if (g is not None and ev in EPg) else None
    home, away = (g['home'], g['away']) if g is not None else (None, None)
    tapes, kinds = {}, {}
    for _, m in Me.iterrows():
        d = Tg.get(m.cid)
        if d is None or len(m.tokens) != 2:
            continue
        d = d.copy()
        d['tok'] = d.asset.astype(str).map({m.tokens[0]: 0, m.tokens[1]: 1})
        d = d[d.tok.notna()]
        d['tok'] = d.tok.astype(int)
        d['price'] = d.price.astype(float); d['size'] = d['size'].astype(float)
        d['p0'] = np.where(d.tok == 0, d.price, 1 - d.price)
        d['is_w'] = d.proxyWallet == W
        d['usd'] = d.price * d['size']
        tapes[m.cid] = (d, MarketTape(d))
        kinds[m.cid] = [side_kind(o, home, away) for o in m.outcomes]
    if not tapes:
        continue
    # event-level others' print times
    ets = np.sort(np.concatenate([tp[0].timestamp.to_numpy()[~tp[0].is_w.to_numpy()] for tp in tapes.values()]))
    # moneyline market of the event with team outcomes
    ml = [c for c in tapes if Me.set_index('cid').loc[c, 'mtype'] == 'moneyline' and set(kinds[c]) == {'home', 'away'}]
    mlc = ml[0] if ml else None
    for _, m in Me.iterrows():
        if m.cid not in tapes:
            continue
        d, mt = tapes[m.cid]
        b = d[(d.side == 'BUY') & (d.timestamp >= m.gst)]
        if len(b) == 0:
            continue
        ts = b.timestamp.to_numpy(np.int64); tok = b.tok.to_numpy(); price = b.price.to_numpy(float)
        kind = np.array([kinds[m.cid][k] if kinds[m.cid][k] else '' for k in tok], dtype=object)
        f = tape_features(mt, ts, tok, price)
        q = ts - 1
        for N in (5, 30, 120):
            f[f'ev_act_{N}'] = np.searchsorted(ets, q, side='right') - np.searchsorted(ets, q - N, side='right')
        if mlc is not None:
            dml, mtl = tapes[mlc]
            k0 = kinds[mlc][0]
            sgn = np.where(kind == k0, 1.0, np.where(np.isin(kind, ['home', 'away']), -1.0, np.nan))
            a, _ = mtl.p0_at(q)
            f['ml_side'] = np.where(sgn == 1, a, np.where(sgn == -1, 1 - a, np.nan))
            for N in (5, 15, 60, 300):
                bb, _ = mtl.p0_at(q - N)
                f[f'ml_mom_{N}'] = (a - bb) * sgn
                f[f'ml_absmove_{N}'] = np.abs(a - bb)
        else:
            for k in ('ml_side', 'ml_mom_5', 'ml_mom_15', 'ml_mom_60', 'ml_mom_300', 'ml_absmove_5', 'ml_absmove_15', 'ml_absmove_60', 'ml_absmove_300'):
                f[k] = np.full(len(b), np.nan)
        f.update(espn_features(eg, ts, kind))
        F = pd.DataFrame(f)
        F['cid'] = m.cid; F['event_slug'] = ev; F['league'] = m.league; F['mtype'] = m.mtype; F['line'] = m.line
        F['gst'] = m.gst; F['ts'] = ts; F['tok'] = tok; F['kind'] = kind; F['price'] = price
        F['size'] = b['size'].to_numpy(); F['usd'] = b.usd.to_numpy(); F['is_w'] = b.is_w.to_numpy()
        F['wallet'] = b.proxyWallet.to_numpy(); F['tx'] = b.transactionHash.to_numpy()
        F['since_start'] = ts - m.gst
        po = payout_map(gm, m.cid)
        F['payout'] = np.array([po[k] for k in tok]) if po else np.nan
        F['has_espn'] = eg is not None
        frames.append(F)
X = pd.concat(frames, ignore_index=True)
X.to_parquet(OUT)
print('rows', len(X), 'wallet', int(X.is_w.sum()), 'markets', X.cid.nunique(), 'events', X.event_slug.nunique(),
      'espn share', round(X.has_espn.mean(), 3), round(time.time() - t0), 's', flush=True)
