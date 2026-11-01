"""E3 screen (pre-registered in NOTES iteration 2): soccer goals (ESPN wall clock) vs the wallet's decision times
(B1 signing ms), units = games, BUILD only; then the confirmation of survivors on VALIDATE.

Family (event-state dimension, ESPN keyEvents):
  goal_any   every scoring key event
  goal_lead  a goal that changes the leader (go-ahead or equaliser)
  card_red   red cards
  period     period boundaries (kick-off, half-time, second half start)
Lags: max_lag_s 120 (core |lag| < 60 s) and max_lag_s 1200 (core < 600 s), 1-s and 10-s bins.
Signed version for goal_any: decision sign +1 when the bought token is Over/Yes-on-scorer... (not available for
every market type), so only the unsigned screen is run here; direction is measured separately by market type.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE, ROOT
import pandas as pd, numpy as np
import indicators as ind

WS = os.path.join(ROOT, 'research', 'reverse_engineering', 'dbdd-inplay-taker')
VAL0, H = 1791849600, 1792713600
ke = pd.read_parquet(f'{CACHE}/espn_soccer_keyevents.parquet')
O = pd.read_parquet(f'{CACHE}/orders.parquet')
O['base'] = O.eventSlug.str.replace(r'-(more-markets|halftime-result|total-corners|exact-score|player-props|first-half.*|btts.*)$', '', regex=True)
ke = ke[ke.wallclock.notna()]
games = ke.groupby('event_slug').agg(gst=('wallclock', 'min'), gend=('wallclock', 'max'))
O = O[O.base.isin(games.index)].copy()
O['dec'] = O.t_ts_ms / 1000.0
print('soccer orders matched to ESPN games', len(O), 'games', O.base.nunique())
typ = ke.type.fillna('').str.lower()
ke['goal'] = ke.scoring.astype(bool)
ke['red'] = typ.str.contains('red')
ke['period_mark'] = typ.isin(['kickoff', 'halftime', 'start-2nd-half', 'end-regular-time'])
ke['delay_start'] = typ.eq('start-delay')
ke['delay_end'] = typ.eq('end-delay')
ke['yellow'] = typ.eq('yellow-card')
ke['subst'] = typ.eq('substitution')


def lead_change(g):
    g = g.sort_values('wallclock')
    h = a = 0
    out = []
    for r in g.itertuples():
        lc = False
        if r.goal:
            before = np.sign(h - a)
            if r.team == r.home:
                h += 1
            else:
                a += 1
            after = np.sign(h - a)
            lc = before != after
        out.append(lc)
    return pd.Series(out, index=g.index)


ke['goal_lead'] = ke.groupby('event_slug', group_keys=False).apply(lead_change)
res = {}
# Games overlap in time, and event_study needs disjoint units: put each game on its own block of a synthetic
# timeline (offset = game index * 50,000 s). Decisions and events of a game keep their offsets from its start,
# so lags are exact; only cross-game alignment (irrelevant here) is lost.
O['gidx'] = O.base.map({g: i for i, g in enumerate(games.index)})
ke['gidx'] = ke.event_slug.map({g: i for i, g in enumerate(games.index)})
SPAN = 50000.0


def syn(t, gi, g0):
    return (t - g0) + gi * SPAN + 1000.0


O['g0'] = O.base.map(games.gst)
ke['g0'] = ke.event_slug.map(games.gst)
O['sdec'] = syn(O.dec, O.gidx, O.g0)
ke['st'] = syn(ke.wallclock, ke.gidx, ke.g0)
for period, (a, b) in {'BUILD': (0, VAL0), 'VALIDATE': (VAL0, H)}.items():
    gg = games[(games.gst >= a) & (games.gst < b)]
    gi = np.array([list(games.index).index(x) for x in gg.index])
    units = np.stack([gi * SPAN + 1000.0 - 900, gi * SPAN + 1000.0 + (gg.gend.values - gg.gst.values) + 1800], 1)
    units = units[np.argsort(units[:, 0])]
    dec = O.sdec.values
    kk = ke[ke.gidx.isin(gi)]
    fam = {'goal_any': kk[kk.goal].st.values, 'goal_lead': kk[kk.goal_lead].st.values,
           'card_red': kk[kk.red].st.values, 'period': kk[kk.period_mark].st.values,
           'delay_start': kk[kk.delay_start].st.values, 'delay_end': kk[kk.delay_end].st.values,
           'yellow': kk[kk.yellow].st.values, 'sub': kk[kk['subst']].st.values}
    out, prof = {}, {}
    for lagset, (L, bs) in {'core60_1s': (120, 1.0), 'core600_10s': (1200, 10.0)}.items():
        rows = ind.screen(dec, {k: (v.astype(float), None) for k, v in fam.items()}, units, max_lag_s=L, bin_s=bs,
                          n_null=400, seed=3)
        out[lagset] = rows
        r = ind.event_study(dec, fam['goal_any'].astype(float), units, max_lag_s=L, bin_s=bs, n_null=200, seed=5)
        prof[lagset] = {'lags_s': r['lags_s'], 'lift': r['lift']}
    nd = int(sum(((dec >= u0) & (dec < u1)).sum() for u0, u1 in units))
    res[period] = {'n_units': int(len(units)), 'n_dec_in_units': nd, 'screens': out, 'goal_any_profile': prof}
    print(period, 'units', len(units), 'decisions', nd)
    for lagset, rows in out.items():
        for r in rows:
            print(' ', lagset, r.get('name'), 'n_ev', r.get('n_events'), 'peak_lag', r.get('peak_lag_s'), 'lift', None if r.get('peak_lift') is None else round(r['peak_lift'], 2),
                  'shape_lag', r.get('shape_peak_lag_s'), 'w', r.get('shape_width_s'), 'p_link', None if r.get('p_link') is None else round(r['p_link'], 5), 'q', None if r.get('q_bh') is None else round(r['q_bh'], 5),
                  'null', r.get('null'), r.get('units_in_null'), 'flank', r.get('level_peak_in_flank'))
json.dump(res, open(os.path.join(WS, 'results', 'iter2_e3_goals.json'), 'w'), indent=1, default=float)
