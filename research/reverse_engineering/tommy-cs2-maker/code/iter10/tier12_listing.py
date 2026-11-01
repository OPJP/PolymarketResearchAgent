"""X140 (assumptions panel iter-9 P1), step 1: the non-GRID tier-1/2 stratum of the exam lots, from the LISTING
PROJECTION only (no prices, volume, liquidity, closed flags, resolution or tick size are read, printed or stored; the
HTTP fetch bypasses the shared cache, nothing raw is persisted).

For CS2 (series 10310) and Dota 2 (10309) events whose earliest moneyline gameStartTime lies in [10-14, T0 + 3 d):
lot (dev / h1 / h2 / fwd), league, tier, grid flag, scheduled start. Output (aggregates + league strings):
  - per lot: non-GRID tier <= 2 events by league; whether each league string is known to the v2 (CS2) / v4 (Dota)
    exam tables; how many of these events have NO earlier event of the same league starting in [gs - 72 h, gs) in the
    listing (gp72 = 0 by construction, whatever group P does);
  - development (before H): every non-GRID tier <= 2 league and its events (the only analogues).
results/tier12_listing.json
"""
from __future__ import annotations

import json, time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
RES = ROOT / 'research/reverse_engineering/tommy-cs2-maker/results'
CODE = ROOT / 'research/reverse_engineering/tommy-cs2-maker/code'
H, T0 = 1792713600, 1793404800
H1_DAYS = {'2026-10-23', '2026-10-25', '2026-10-27', '2026-10-29'}
H2_DAYS = {'2026-10-24', '2026-10-26', '2026-10-28', '2026-10-30'}


def ts(s):
    try:
        t = pd.Timestamp(s)
        return int((t.tz_convert('UTC') if t.tzinfo else t.tz_localize('UTC')).timestamp())
    except Exception:  # noqa: BLE001
        return None


def project(events, title):
    rows = []
    for e in events:
        mk = e.get('markets') or []
        gss = [ts(m.get('gameStartTime')) for m in mk
               if m.get('gameStartTime') and m.get('sportsMarketType') in ('moneyline', 'child_moneyline')]
        gss = [g for g in gss if g]
        if not gss:
            continue
        g0 = min(gss)
        meta = e.get('eventMetadata')
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:  # noqa: BLE001
                meta = {}
        meta = meta or {}
        day = pd.Timestamp(g0, unit='s', tz='UTC').strftime('%Y-%m-%d')
        lot = 'dev' if g0 < H else ('h1' if day in H1_DAYS else ('h2' if day in H2_DAYS else 'fwd'))
        rows.append({'title': title, 'slug': e.get('slug'), 'gs': g0, 'lot': lot, 'league': meta.get('league'),
                     'tier': str(meta.get('leagueTier')).replace('.0', ''), 'grid': bool(meta.get('gridSeriesId'))})
    return rows


def main():
    rows = []
    with httpx.Client(timeout=30, headers={'User-Agent': 'research'}) as c:
        for sid, title in (('10310', 'cs2'), ('10309', 'dota2')):
            off = 0
            while True:
                params = {'series_id': sid, 'start_date_min': '2026-10-10T00:00:00Z',
                          'start_date_max': '2026-11-04T00:00:00Z', 'limit': 100, 'offset': off}
                r = c.get('https://gamma-api.polymarket.com/events', params=params)
                r.raise_for_status()
                d = r.json(); n = len(d)
                rows.extend(project(d, title))
                del d, r
                if n < 100 or off > 4000:
                    break
                off += 100
                time.sleep(0.6)
    L = pd.DataFrame(rows).drop_duplicates('slug')
    L = L[L.gs >= 1792022400]  # 10-14
    v2 = json.loads((CODE / 'final_rule_v2_constants.json').read_text())
    v4 = json.loads((CODE / 'final_rule_v4_dota.json').read_text())
    known = {'cs2': set(v2['exam']['league_n'].keys()), 'dota2': set((v4.get('exam') or v4).get('league_n', {}).keys())}
    L['known'] = [lg in known[t] for lg, t in zip(L.league, L.title)]
    # gp72 = 0 by construction: no earlier event of the same league (same title) in [gs - 72 h, gs)
    first72 = []
    for r in L.itertuples():
        g = L[(L.title == r.title) & (L.league == r.league) & (L.gs >= r.gs - 72 * 3600) & (L.gs < r.gs)]
        first72.append(len(g) == 0)
    L['first72'] = first72
    big = L[(~L.grid) & (L.tier.isin(['1', '2']))]
    res = {'tables_known_leagues': {k: len(v) for k, v in known.items()}}
    for (title, lot), x in big.groupby(['title', 'lot']):
        res[f'{title}_{lot}'] = {
            'events': int(len(x)),
            'by_league': {str(lg): {'events': int(len(g)), 'tier': sorted(g.tier.unique().tolist()), 'known_to_table': bool(g.known.iloc[0]),
                                    'gp72_zero_by_construction': int(g.first72.sum())} for lg, g in x.groupby('league')}}
    for title in ('cs2', 'dota2'):
        x = L[L.title == title]
        res[f'{title}_lot_mix'] = {lot: {'events': int(len(g)), 'grid': int(g.grid.sum()),
                                         'nongrid_by_tier': g[~g.grid].tier.value_counts().to_dict(),
                                         'grid_by_tier': g[g.grid].tier.value_counts().to_dict()} for lot, g in x.groupby('lot')}
    (RES / 'tier12_listing.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res, indent=1)[:6000])


if __name__ == '__main__':
    main()
