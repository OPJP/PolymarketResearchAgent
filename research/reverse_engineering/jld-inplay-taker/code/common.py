"""Shared loaders + point-in-time feature builder for jld-inplay-taker.

Point-in-time rules used everywhere here:
  * a print at second t sees tape prints with ts <= t-1 only (strictly earlier seconds);
  * ESPN plays are known at wallclock + D with D >= 5 s;
  * market metadata used: outcomes, token ids, sportsMarketType, line, gameStartTime (known at listing);
  * outcomes (payout) are used for PnL settlement only.
"""
import sys, os, json, glob, re
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.adapters.espn import team_matches

W = '0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705'
H = 1792713600
CACHE = '/home/user/PolymarketResearchAgent/.cache/re/jld-inplay-taker'
VAL0 = 1791849600   # VALIDATE start (game start)
BUILD0 = 1788220800  # BUILD start 2026-09-01


def gst_of(m):
    g = m.get('gameStartTime')
    try:
        return pd.Timestamp(g).timestamp() if g else np.nan
    except Exception:
        return np.nan


def side_kind(outcome, home, away):
    o = (outcome or '').strip().lower()
    if o in ('over', 'under'):
        return o
    def comp(name):
        parts = name.split()
        return {"team": {"displayName": name, "shortDisplayName": parts[-1], "name": parts[-1], "location": " ".join(parts[:-1])}}
    if home and team_matches(outcome, comp(home)):
        return 'home'
    if away and team_matches(outcome, comp(away)):
        return 'away'
    return None


def load_tapes(paths=None):
    paths = paths or sorted(glob.glob(f'{CACHE}/tapes/chunk_*.parquet'))
    T = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    T = T[T.timestamp < H]
    T['proxyWallet'] = T.proxyWallet.str.lower()
    return T


def market_table(gm, cids):
    rows = []
    for c in cids:
        m = gm.get(c)
        if not m:
            continue
        ev = (m.get('events') or [{}])[0]
        try:
            line = float(m.get('line')) if m.get('line') is not None else np.nan
        except Exception:
            line = np.nan
        rows.append({'cid': c, 'event_slug': ev.get('slug') or '', 'mtype': m.get('sportsMarketType') or 'other',
                     'line': line, 'gst': gst_of(m), 'tokens': json.loads(m.get('clobTokenIds') or '[]'),
                     'outcomes': json.loads(m.get('outcomes') or '[]'), 'question': m.get('question') or '',
                     'outcomePrices': m.get('outcomePrices')})
    M = pd.DataFrame(rows)
    M['league'] = M.event_slug.str.split('-').str[0]
    return M


def payout_map(gm, cid):
    """Settlement only: payout per token index from resolved outcomePrices."""
    m = gm[cid]
    try:
        op = [float(x) for x in json.loads(m.get('outcomePrices') or '[]')]
    except Exception:
        return None
    if len(op) != 2 or not (m.get('closed')) or not all(x in (0.0, 1.0, 0.5) for x in op):
        return None
    return op


# ----------------------------------------------------------------------------- ESPN
class EspnGame:
    def __init__(self, g, plays, D):
        self.g = g
        p = plays.sort_values(['ts', 'seq']).reset_index(drop=True)
        p = p[p.ts > 0]
        self.D = D
        self.known = p.ts.to_numpy(np.int64) + D
        self.hs = p.home_score.ffill().fillna(0).to_numpy(float) if 'home_score' in p else np.zeros(len(p))
        self.as_ = p.away_score.ffill().fillna(0).to_numpy(float) if 'away_score' in p else np.zeros(len(p))
        wp = p.home_wp.to_numpy(float)
        # forward fill WP
        s = pd.Series(wp).ffill().to_numpy()
        self.wp = s
        self.period = p.period.fillna(0).to_numpy(float)
        # scoring events
        dh = np.diff(np.r_[0, self.hs]); da = np.diff(np.r_[0, self.as_])
        self.sc_idx = np.where((dh != 0) | (da != 0))[0]
        self.sc_known = self.known[self.sc_idx]
        self.sc_dh = dh[self.sc_idx]; self.sc_da = da[self.sc_idx]
        # possession / field position for football
        self.off_team = p.s_team.fillna('').to_numpy() if 's_team' in p else np.array([''] * len(p))
        self.ytez = p.e_ytez.to_numpy(float) if 'e_ytez' in p else np.full(len(p), np.nan)
        self.e_team = p.e_team.fillna('').to_numpy() if 'e_team' in p else np.array([''] * len(p))
        self.home_id, self.away_id = str(g['home_id']), str(g['away_id'])
        # WP-swing events: plays where WP moved by >= 0.02 vs previous WP value
        dwp = np.diff(np.r_[s[0] if len(s) else np.nan, s])
        self.dwp = np.nan_to_num(dwp)
        self.ptype = p.ptype.fillna('').to_numpy()


def espn_features(eg, ts, kind):
    """Features at decision times ts (array) for bought side kind ('home','away','over','under')."""
    n = len(ts)
    out = {}
    if eg is None or len(eg.known) == 0:
        for k in ('since_play', 'since_score', 'score_fav', 'score_pts', 'dwp_last', 'dwp_30', 'dwp_120', 'wp_side',
                  'margin', 'total_pts', 'period', 'n_plays_30', 'offense', 'ytez', 'since_swing', 'swing_fav'):
            out[k] = np.full(n, np.nan)
        return out
    i = np.searchsorted(eg.known, ts, side='right') - 1
    has = i >= 0
    ic = np.clip(i, 0, None)
    sgn = np.where(kind == 'home', 1.0, np.where(kind == 'away', -1.0, np.nan))
    out['since_play'] = np.where(has, ts - eg.known[ic], np.nan)
    j = np.searchsorted(eg.sc_known, ts, side='right') - 1
    hj = j >= 0; jc = np.clip(j, 0, None)
    if len(eg.sc_known):
        dh, da = eg.sc_dh[jc], eg.sc_da[jc]
        fav_team = np.sign(dh - da) * sgn
        fav_tot = np.where(kind == 'over', 1.0, np.where(kind == 'under', -1.0, np.nan)) * (np.abs(dh) + np.abs(da) > 0)
        out['score_fav'] = np.where(hj, np.where(np.isnan(sgn), fav_tot, fav_team), np.nan)
        out['since_score'] = np.where(hj, ts - eg.sc_known[jc], np.nan)
        out['score_pts'] = np.where(hj, np.abs(dh) + np.abs(da), np.nan)
    else:
        out['score_fav'] = out['since_score'] = out['score_pts'] = np.full(n, np.nan)
    wp = eg.wp
    wpl = np.where(has, wp[ic], np.nan)
    out['wp_side'] = np.where(kind == 'home', wpl, np.where(kind == 'away', 1 - wpl, np.nan))
    out['dwp_last'] = np.where(has, eg.dwp[ic], np.nan) * sgn
    for N in (30, 120):
        i2 = np.searchsorted(eg.known, ts - N, side='right') - 1
        w2 = np.where(i2 >= 0, wp[np.clip(i2, 0, None)], np.nan)
        out[f'dwp_{N}'] = (wpl - w2) * sgn
    hs = np.where(has, eg.hs[ic], 0); as_ = np.where(has, eg.as_[ic], 0)
    out['margin'] = (hs - as_) * sgn
    out['total_pts'] = hs + as_
    out['period'] = np.where(has, eg.period[ic], 0)
    out['n_plays_30'] = i - (np.searchsorted(eg.known, ts - 30, side='right') - 1)
    tid = np.where(kind == 'home', eg.home_id, np.where(kind == 'away', eg.away_id, ''))
    offt = np.where(has, eg.e_team[ic], '')
    out['offense'] = np.where(np.isnan(sgn) | (offt == ''), np.nan, (offt == tid).astype(float))
    out['ytez'] = np.where(has, eg.ytez[ic], np.nan)
    # last WP swing >= 0.03 known
    sw = np.where(np.abs(eg.dwp) >= 0.03)[0]
    if len(sw):
        k = np.searchsorted(eg.known[sw], ts, side='right') - 1
        hk = k >= 0; kc = np.clip(k, 0, None)
        out['since_swing'] = np.where(hk, ts - eg.known[sw][kc], np.nan)
        out['swing_fav'] = np.where(hk, np.sign(eg.dwp[sw][kc]) * sgn, np.nan)
    else:
        out['since_swing'] = out['swing_fav'] = np.full(n, np.nan)
    return out


# ----------------------------------------------------------------------------- tape features
class MarketTape:
    """All taker prints of a market; p0 = implied price of token 0."""
    def __init__(self, d):
        d = d.sort_values('timestamp', kind='stable')
        self.ts_all = d.timestamp.to_numpy(np.int64)
        self.p0_all = d.p0.to_numpy(float)
        g = d.groupby('timestamp').p0.last()
        self.ts = g.index.to_numpy(np.int64)
        self.p0 = g.to_numpy(float)
        o = d[~d.is_w]
        self.o_ts = o.timestamp.to_numpy(np.int64)
        # signed flow toward token 0 by others: BUY tok0 or SELL tok1 = +1
        self.o_flow = np.where(((o.tok == 0) & (o.side == 'BUY')) | ((o.tok == 1) & (o.side == 'SELL')), 1.0, -1.0) * o.usd.to_numpy(float)
        self.o_cflow = np.r_[0, np.cumsum(self.o_flow)]

    def p0_at(self, q):
        i = np.searchsorted(self.ts, q, side='right') - 1
        return np.where(i >= 0, self.p0[np.clip(i, 0, None)], np.nan), np.where(i >= 0, self.ts[np.clip(i, 0, None)], -10 ** 9)

    def count_others(self, lo, hi):
        """others' prints with lo < ts <= hi"""
        return np.searchsorted(self.o_ts, hi, side='right') - np.searchsorted(self.o_ts, lo, side='right')

    def flow_others(self, lo, hi):
        a = np.searchsorted(self.o_ts, lo, side='right'); b = np.searchsorted(self.o_ts, hi, side='right')
        return self.o_cflow[b] - self.o_cflow[a]


def tape_features(mt, ts, tok, price):
    q = ts - 1
    s = np.where(tok == 0, 1.0, -1.0)
    p_last0, last_ts = mt.p0_at(q)
    pk_last = np.where(tok == 0, p_last0, 1 - p_last0)
    out = {'pk_last': pk_last, 'gap': price - pk_last, 'stale': q - last_ts}
    for N in (5, 15, 30, 60, 180, 600):
        b, _ = mt.p0_at(q - N)
        out[f'mom_{N}'] = (p_last0 - b) * s
    for N in (10, 60, 300):
        out[f'act_{N}'] = mt.count_others(q - N, q)
        out[f'flow_{N}'] = mt.flow_others(q - N, q) * s
    return out
