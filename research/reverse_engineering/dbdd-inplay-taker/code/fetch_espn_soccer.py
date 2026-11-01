"""ESPN soccer key events (with wall clocks) for every soccer game the wallet traded in the tape window (< H).
Saves every key event (goals, cards, subs, period starts/ends) so later iterations can test any event family."""
import sys, json, re, time
import os; sys.path.insert(0, os.path.dirname(__file__)); from polyrea_path import CACHE
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.http import shared_client
from polyrea.adapters.espn import team_matches

import glob
H = 1792713600
LG = {'epl': 'eng.1', 'elc': 'eng.2', 'el1': 'eng.3', 'lal': 'esp.1', 'es2': 'esp.2', 'bun': 'ger.1', 'bl2': 'ger.2', 'sea': 'ita.1',
      'itsb': 'ita.2', 'fl1': 'fra.1', 'fl2': 'fra.2', 'ucl': 'uefa.champions', 'uel': 'uefa.europa', 'uecl': 'uefa.europa.conf',
      'mls': 'usa.1', 'uslc': 'usa.usl.1', 'mex': 'mex.1', 'bra': 'bra.1', 'bra2': 'bra.2', 'arg': 'arg.1', 'col1': 'col.1',
      'kor': 'kor.1', 'jap': 'jpn.1', 'spl': 'ksa.1', 'por': 'por.1', 'ere': 'ned.1', 'nor': 'nor.1', 'per1': 'per.1',
      'ecu1': 'ecu.1', 'tur': 'tur.1', 'sco': 'sco.1', 'aus': 'aus.1', 'chi': 'chn.1', 'nwsl': 'usa.nwsl', 'bel': 'bel.1',
      'aut': 'aut.1', 'den': 'den.1', 'swe': 'swe.1', 'sui': 'sui.1', 'gre': 'gre.1', 'chl': 'chi.1', 'uru': 'uru.1',
      'par': 'par.1', 'bol': 'bol.1', 'ven': 'ven.1', 'lib': 'conmebol.libertadores', 'sud': 'conmebol.sudamericana',
      'wcq': 'fifa.worldq', 'cdr': 'esp.copa_del_rey', 'fac': 'eng.fa', 'efl': 'eng.league_cup', 'ukr1': 'ukr.1',
      'rus': 'rus.1', 'pol': 'pol.1', 'cze': 'cze.1', 'rou': 'rou.1', 'irl': 'irl.1', 'jpn': 'jpn.1', 'ind': 'ind.1',
      'mar': 'mar.1', 'egy': 'egy.1', 'ksa': 'ksa.1', 'cro': 'cro.1', 'srb': 'srb.1', 'isr': 'isr.1', 'cyp': 'cyp.1',
      'unl': 'uefa.nations', 'conl': ['concacaf.nations.league', 'uefa.europa.conf'], 'fif': ['fifa.friendly', 'fifa.worldq.caf', 'fifa.worldq.afc'],
      'afcq': ['caf.nations_qual', 'afc.cupq'], 'acle': 'afc.champions', 'acl2': 'afc.cup', 'gtm': 'gua.1', 'hon': 'hon.1', 'crc': 'crc.1', 'slv': 'slv.1',
      'cdm': 'concacaf.champions', 'lc': 'concacaf.leagues.cup', 'cafq': 'fifa.worldq.caf', 'uwcl': 'uefa.wchampions'}
h = shared_client()


def find(row):
    slug, title, gst = row
    pref = slug.split('-')[0]
    lgs = LG.get(pref)
    mt = re.match(r'(.+?) vs\.? (.+?)(?::| -|$)', title or '')
    if not lgs or not mt or not np.isfinite(gst):
        return slug, None
    a, b = mt.group(1).strip(), mt.group(2).strip()
    for lg, off in [(l, o) for l in (lgs if isinstance(lgs, list) else [lgs]) for o in (0, -1, 1)]:
        day = pd.Timestamp(int(gst) + off * 86400, unit='s', tz='UTC').strftime('%Y%m%d')
        try:
            sb, _ = h.get_json(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard', {'dates': day}, adapter='espn.scoreboard', max_age=None)
        except Exception:
            continue
        for ev in sb.get('events') or []:
            comps = ev.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) == 2 and any(team_matches(a, c) for c in comps) and any(team_matches(b, c) for c in comps) \
                    and abs(pd.Timestamp(ev['date']).timestamp() - gst) < 4 * 3600:
                try:
                    sm, _ = h.get_json(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/summary', {'event': ev['id']}, adapter='espn.summary', max_age=None)
                except Exception:
                    return slug, None
                home = next((c for c in comps if c.get('homeAway') == 'home'), comps[0])
                out = []
                for k in sm.get('keyEvents') or []:
                    wc = k.get('wallclock')
                    out.append({'event_slug': slug, 'espn_id': ev['id'], 'league': lg,
                                'type': (k.get('type') or {}).get('type') or (k.get('type') or {}).get('text'),
                                'scoring': bool(k.get('scoringPlay')),
                                'wallclock': int(pd.Timestamp(wc).timestamp()) if wc else np.nan,
                                'clock': (k.get('clock') or {}).get('value'), 'period': (k.get('period') or {}).get('number'),
                                'team': ((k.get('team') or {}).get('displayName')), 'home': home.get('team', {}).get('displayName'),
                                'text': (k.get('text') or '')[:100]})
                return slug, out
    return slug, None


if __name__ == '__main__':
    # iteration 2 (local): activity from per-chunk files, Gamma from gamma2.json; development units only
    act = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/activity/*.parquet')])
    gm = json.load(open(f'{CACHE}/gamma2.json'))
    tr = act[(act.type == 'TRADE')].copy()
    tr = tr[tr.conditionId.map(lambda c: (gm.get(c) or {}).get('sealed', 1) == 0)]
    tr['base'] = tr.eventSlug.str.replace(r'-(more-markets|halftime-result|total-corners|exact-score|player-props|first-half.*|btts.*)$', '', regex=True)
    tr['vs'] = tr.title.str.contains(r' vs\.? ', regex=True)
    tr = tr.sort_values('vs', ascending=False)
    ev = tr.groupby('base').agg(cid=('conditionId', 'first'), title=('title', 'first')).reset_index().rename(columns={'base': 'eventSlug'})
    ev['pref'] = ev.eventSlug.str.split('-').str[0]
    ev = ev[ev.pref.isin(LG)]

    def gst_of(c):
        m = gm.get(c) or {}
        try:
            return pd.Timestamp(m['gameStartTime']).timestamp()
        except Exception:
            return np.nan
    ev['gst'] = ev.cid.map(gst_of)
    ev = ev[(ev.gst < time.time() - 3 * 3600)]
    print('soccer events', len(ev), ev.pref.value_counts().head(15).to_dict(), flush=True)
    t0 = time.time()
    rows, matched = [], 0
    with ThreadPoolExecutor(4) as ex:
        for i, (slug, out) in enumerate(ex.map(find, ev[['eventSlug', 'title', 'gst']].itertuples(index=False, name=None))):
            if out:
                matched += 1
                rows.extend(out)
            if i % 100 == 0:
                print(i, matched, round(time.time() - t0), flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(f'{CACHE}/espn_soccer_keyevents.parquet')
    print('done events', len(ev), 'matched', matched, 'key events', len(df), round(time.time() - t0), flush=True)
