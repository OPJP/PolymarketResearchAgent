"""Universe U(W) and hourly prices, as pre-registered (same filters as f3_universe.py), as importable functions.
closed_before: markets whose closedTime >= closed_before are dropped unseen."""
import sys, json, re, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.http import shared_client, HttpError
SPORT_SLUG = re.compile(r'^(nfl|nba|mlb|nhl|epl|ucl|uel|atp|wta|ufc|mma|cs2|lol|dota2|val|cbb|cfb|ncaab|kbo|npb|bra|arg|lib|sud|mex|ser|lal|bun|fl1|ere|por|tur|el1|crint|cricipl|cricetpl|f1|box|wnba|mls|aus|jpn|kor|chn|sau|ufl|nascar|golf|pga)-')
KEEP = ['conditionId','question','slug','outcomes','clobTokenIds','endDate','startDate','createdAt','closedTime','outcomePrices','volumeNum','negRisk','negRiskMarketID',
        'groupItemTitle','orderPriceMinTickSize','feesEnabled','feeType','gameStartTime','sportsMarketType']
def _ts(s):
    try: return pd.Timestamp(s).timestamp()
    except Exception: return np.nan
def gamma_scan(h, a, b):
    got = []; off = 0
    while True:
        try:
            d, _ = h.get_json('https://gamma-api.polymarket.com/markets', {'closed': 'true', 'end_date_min': pd.Timestamp(a, unit='s', tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'end_date_max': pd.Timestamp(b, unit='s', tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ'), 'volume_num_min': 20000, 'limit': 100, 'offset': off}, adapter='gamma.markets', max_age=None)
        except HttpError:
            if b - a > 60:
                mid = (a + b) // 2; return gamma_scan(h, a, mid) + gamma_scan(h, mid + 1, b)
            return got
        got += d or []
        if not d or len(d) < 100: return got
        off += 100
        if off >= 1500:
            if b - a <= 60: return got
            mid = (a + b) // 2; return gamma_scan(h, a, mid) + gamma_scan(h, mid + 1, b)
def universe(start_ts, end_ts, closed_before):
    h = shared_client(); rows = []
    days = pd.date_range(pd.Timestamp(start_ts, unit='s', tz='UTC').floor('D'), pd.Timestamp(end_ts, unit='s', tz='UTC').ceil('D'), freq='D')
    for d0, d1 in zip(days[:-1], days[1:]):
        a, b = max(int(d0.timestamp()), int(start_ts)), min(int(d1.timestamp()), int(end_ts)) - 1
        if b <= a: continue
        for m in gamma_scan(h, a, b):
            ct = _ts(m.get('closedTime'))
            if not (ct < closed_before): continue
            r = {k: m.get(k) for k in KEEP}
            r['closed_ts'] = ct; r['end_ts'] = _ts(m.get('endDate')); r['start_ts'] = _ts(m.get('startDate') or m.get('createdAt'))
            rows.append(r)
    u = pd.DataFrame(rows).drop_duplicates('conditionId')
    if not len(u): return u
    u['is_sport'] = u.gameStartTime.notna() | u.sportsMarketType.notna() | u.slug.fillna('').str.match(SPORT_SLUG)
    u['is_updown'] = u.slug.fillna('').str.contains('updown|up-or-down') | u.question.fillna('').str.contains('Up or Down')
    return u[~u.is_sport & ~u.is_updown].copy()
def prices(u):
    h = shared_client()
    def fetch(r):
        try: tok = json.loads(r.clobTokenIds)[0]
        except Exception: return r.conditionId, []
        pts = {}
        chunks = [(r.end_ts - 14 * 86400, r.end_ts + 86400)]
        if r.closed_ts > r.end_ts + 86400: chunks.append((r.end_ts + 86400, r.end_ts + 14 * 86400))
        for a, b in chunks:
            a = int(max(a, (r.start_ts if r.start_ts == r.start_ts else a))); b = int(min(b, r.closed_ts + 3600))
            if b <= a: continue
            try:
                d, _ = h.get_json('https://clob.polymarket.com/prices-history', {'market': tok, 'startTs': a, 'endTs': b, 'fidelity': 60}, adapter='clob.prices-history', max_age=None)
            except Exception:
                continue
            for p in (d or {}).get('history') or []:
                pts[int(p['t'])] = float(p['p'])
        return r.conditionId, sorted(pts.items())
    with ThreadPoolExecutor(6) as ex:
        return dict(ex.map(fetch, list(u.itertuples())))
