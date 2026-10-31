"""ESPN expansion: for every US-sports event the wallet traded with game start in [T0, H), find the ESPN event
and store a RICH play table (not just scores/WP): period, clock, play type, down/distance/yard line/possession
(football), score value / shooting team (basketball), outs/inning etc. where present, wallclock, WP by play id.
Also game-level pregame odds from ESPN pickcenter (published before the game).

Writes .cache/re/jld-inplay-taker/espn_plays.parquet and espn_games.parquet.
Only games starting before H are fetched (no holdout data).
"""
import sys, os, json, time, re
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.espn import ESPN, BASE, LEAGUES, team_matches

H = 1792713600
T0 = int(os.environ.get('T0', 1790812800))
CACHE = '/home/user/PolymarketResearchAgent/.cache/re/jld-inplay-taker'
espn = ESPN()


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def gst(m):
    g = m.get('gameStartTime')
    try:
        return pd.Timestamp(g).timestamp() if g else np.nan
    except Exception:
        return np.nan


def teams_for_event(ms):
    ml = [m for m in ms if m.get('sportsMarketType') == 'moneyline']
    for m in ml:
        o = json.loads(m.get('outcomes') or '[]')
        if len(o) == 2 and not any(x.lower() in ('yes', 'no', 'over', 'under', 'draw') for x in o):
            return o
    for m in ms:
        ev = (m.get('events') or [{}])[0]
        for s in (ev.get('title') or '', m.get('question') or ''):
            mt = re.match(r"(.+?) vs\.? (.+?)(?:\s*[:(].*)?$", s)
            if mt:
                return [mt.group(1).strip(), mt.group(2).strip()]
    return None


def parse_summary(league, ev, data):
    comps = ev.get('competitions', [{}])[0].get('competitors', [])
    home = next((c for c in comps if c.get('homeAway') == 'home'), None)
    away = next((c for c in comps if c.get('homeAway') == 'away'), None)
    if home is None or away is None:
        return None, None
    hid, aid = str(home['team'].get('id')), str(away['team'].get('id'))
    wp = {str(w.get('playId')): w.get('homeWinPercentage') for w in data.get('winprobability') or []}
    rows = []
    drives = (data.get('drives') or {}).get('previous') or []
    if drives:
        raw = []
        for di, d in enumerate(drives):
            dteam = str((d.get('team') or {}).get('id', ''))
            for p in d.get('plays', []):
                raw.append((di, dteam, p))
    else:
        raw = [(-1, '', p) for p in (data.get('plays') or [])]
    for di, dteam, p in raw:
        wc = p.get('wallclock')
        st, en = p.get('start') or {}, p.get('end') or {}
        r = {
            'play_id': str(p.get('id')), 'seq': int(p.get('sequenceNumber') or 0) if str(p.get('sequenceNumber') or '0').isdigit() else 0,
            'ts': int(pd.Timestamp(wc).timestamp()) if wc else -1,
            'period': (p.get('period') or {}).get('number'), 'clock': (p.get('clock') or {}).get('displayValue'),
            'ptype': (p.get('type') or {}).get('text'), 'text': (p.get('text') or '')[:140],
            'home_score': p.get('homeScore'), 'away_score': p.get('awayScore'),
            'scoring': bool(p.get('scoringPlay')), 'score_value': p.get('scoreValue'),
            'team_id': str((p.get('team') or {}).get('id', '')) or dteam,
            'drive': di, 'drive_team': dteam,
            'home_wp': wp.get(str(p.get('id'))),
            's_down': st.get('down'), 's_dist': st.get('distance'), 's_ytez': st.get('yardsToEndzone'), 's_team': str((st.get('team') or {}).get('id', '')),
            'e_down': en.get('down'), 'e_dist': en.get('distance'), 'e_ytez': en.get('yardsToEndzone'), 'e_team': str((en.get('team') or {}).get('id', '')),
            'yards': p.get('statYardage'), 'turnover': p.get('isTurnover'), 'penalty': p.get('isPenalty'),
            'outs': (p.get('outs') if 'outs' in p else (p.get('situation') or {}).get('outs')),
            'modified': p.get('modified'),
        }
        rows.append(r)
    pc = (data.get('pickcenter') or [{}])
    pc0 = pc[0] if pc else {}
    g = {'espn_id': str(ev['id']), 'league': league, 'home': home['team'].get('displayName'), 'away': away['team'].get('displayName'),
         'home_id': hid, 'away_id': aid, 'espn_start': int(pd.Timestamp(ev['date']).timestamp()),
         'pc_provider': (pc0.get('provider') or {}).get('name'), 'pc_spread': pc0.get('spread'), 'pc_total': pc0.get('overUnder'),
         'pc_home_ml': (pc0.get('homeTeamOdds') or {}).get('moneyLine'), 'pc_away_ml': (pc0.get('awayTeamOdds') or {}).get('moneyLine'),
         'pc_home_fav': (pc0.get('homeTeamOdds') or {}).get('favorite'), 'n_plays': len(rows), 'n_wp': len(wp)}
    return g, rows


def main():
    gm = json.load(open(f'{CACHE}/gamma.json'))
    act = pd.read_parquet(f'{CACHE}/activity.parquet')
    tr = act[act.type == 'TRADE']
    traded = set(tr.conditionId.unique())
    ev = {}
    for cid, m in gm.items():
        if cid not in traded:
            continue
        evs = (m.get('events') or [{}])[0]
        slug = evs.get('slug') or ''
        lg = slug.split('-')[0]
        if lg not in LEAGUES:
            continue
        t = gst(m)
        if not np.isfinite(t) or t < T0 or t >= H:
            continue
        ev.setdefault(slug, {'league': lg, 'start': t, 'ms': []})['ms'].append(m)
    log('events to match', len(ev))

    def job(item):
        slug, e = item
        teams = teams_for_event(e['ms'])
        if not teams:
            return slug, None, None, 'noteams'
        try:
            hit = espn.find_event(e['league'], int(e['start']), teams[0], teams[1])
            if hit is None:
                return slug, None, None, 'nomatch'
            path, _ = LEAGUES[e['league']]
            data, _ = espn.http.get_json(f"{BASE}/{path}/summary", {"event": hit["id"]}, adapter="espn.summary", max_age=None)
            g, rows = parse_summary(e['league'], hit, data)
            return slug, g, rows, 'ok'
        except Exception as ex:
            return slug, None, None, 'err ' + str(ex)[:80]

    G, Pl, stat = [], [], {}
    t0 = time.time()
    with ThreadPoolExecutor(3) as ex:
        for i, (slug, g, rows, st) in enumerate(ex.map(job, sorted(ev.items(), key=lambda kv: -kv[1]['start']))):
            stat[st.split(' ')[0]] = stat.get(st.split(' ')[0], 0) + 1
            if g is not None:
                g['event_slug'] = slug
                G.append(g)
                for r in rows:
                    r['event_slug'] = slug
                Pl.extend(rows)
            if (i + 1) % 100 == 0:
                log(i + 1, '/', len(ev), stat, round(time.time() - t0), 's')
    G = pd.DataFrame(G)
    P = pd.DataFrame(Pl)
    for c in ('home_wp', 'score_value', 'yards', 's_down', 's_dist', 's_ytez', 'e_down', 'e_dist', 'e_ytez', 'outs', 'period', 'home_score', 'away_score'):
        if c in P:
            P[c] = pd.to_numeric(P[c], errors='coerce')
    for c in ('turnover', 'penalty'):
        if c in P:
            P[c] = P[c].astype('float')
    G.to_parquet(f'{CACHE}/espn_games.parquet')
    P.to_parquet(f'{CACHE}/espn_plays.parquet')
    log('done', stat, 'games', len(G), 'plays', len(P))


if __name__ == '__main__':
    main()
