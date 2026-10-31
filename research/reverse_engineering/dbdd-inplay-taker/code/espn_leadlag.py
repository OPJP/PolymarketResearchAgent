"""Soccer: timing of in-play taker BUY prints relative to ESPN goal wall clocks (wallet vs other takers).
Descriptive lead-lag (uses goal times on both sides of the print); decision features must use goals with
wallclock + D <= T - 2 only."""
import sys, json
import numpy as np, pandas as pd
CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'
OUT = '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker'
F = pd.read_parquet(f'{CACHE}/feats.parquet', columns=['cid', 'event', 'ts', 'is_wallet', 'outcome', 'smt', 'price', 'tok', 'payout', 'period', 'mv60', 'quiet'])
K = pd.read_parquet(f'{CACHE}/espn_soccer_keyevents.parquet')
F['base'] = F.event.str.replace(r'-(more-markets|halftime-result|total-corners|exact-score|player-props|first-half.*|btts.*)$', '', regex=True)
goals = K[K.scoring & K.wallclock.notna()].groupby('event_slug').wallclock.apply(lambda s: np.sort(s.to_numpy().astype(float))).to_dict()
have = set(K.event_slug.unique())
PER = sys.argv[1] if len(sys.argv) > 1 else 'BUILD'
S = F[F.base.isin(have) & (F.period == PER)].copy()
S = S[S.groupby('cid').is_wallet.transform('max').astype(bool)]
print('soccer prints with ESPN', len(S), 'wallet', int(S.is_wallet.sum()), 'events', S.base.nunique(), 'goals', sum(len(v) for v in goals.values()))
lag_prev = np.full(len(S), np.nan); lag_next = np.full(len(S), np.nan)
for b, idx in S.groupby('base').indices.items():
    g = goals.get(b)
    if g is None or len(g) == 0:
        continue
    t = S.ts.to_numpy()[idx].astype(float)
    j = np.searchsorted(g, t, side='right')
    lag_prev[idx] = np.where(j > 0, t - g[np.clip(j - 1, 0, None)], np.nan)
    lag_next[idx] = np.where(j < len(g), g[np.clip(j, 0, len(g) - 1)] - t, np.nan)
S['since_goal'] = lag_prev; S['to_goal'] = lag_next
out = {}
edges = [-300, -120, -60, -30, -10, 0, 5, 10, 20, 30, 45, 60, 90, 120, 180, 300]
for k, g in S.groupby('is_wallet'):
    rel = np.concatenate([g.since_goal.dropna().to_numpy(), -g.to_goal.dropna().to_numpy()])
    # nearest goal (signed): positive = after goal
    near = np.where(np.nan_to_num(g.since_goal, nan=1e9) <= np.nan_to_num(g.to_goal, nan=1e9), g.since_goal, -g.to_goal)
    h, _ = np.histogram(near[np.isfinite(near)], bins=edges)
    out['wallet' if k else 'others'] = {'n': int(len(g)), 'hist_nearest_goal': dict(zip([f'{a}..{b}' for a, b in zip(edges[:-1], edges[1:])], (h / len(g)).round(4).tolist())),
                                        'share_within_60s_after': float(((g.since_goal >= 0) & (g.since_goal <= 60)).mean()),
                                        'share_within_60s_before': float(((g.to_goal >= 0) & (g.to_goal <= 60)).mean())}
# per market type, wallet share within 0-60 s after a goal vs others
by = []
for smt, g in S.groupby('smt'):
    w = g[g.is_wallet]; o = g[~g.is_wallet]
    if len(w) < 30:
        continue
    by.append({'smt': smt, 'n_w': len(w), 'w_0_60': float(((w.since_goal >= 0) & (w.since_goal <= 60)).mean()),
               'o_0_60': float(((o.since_goal >= 0) & (o.since_goal <= 60)).mean()),
               'w_over_share_0_60': float((w[(w.since_goal >= 0) & (w.since_goal <= 60)].outcome.str.lower() == 'over').mean()) if len(w) else None})
out['by_smt'] = by
json.dump(out, open(f'{OUT}/espn_leadlag_result_{PER}.json', 'w'), indent=1, default=float)
print(json.dumps(out, indent=0, default=float)[:3000])
S.to_parquet(f'{CACHE}/soccer_goal_lags_{PER}.parquet')
