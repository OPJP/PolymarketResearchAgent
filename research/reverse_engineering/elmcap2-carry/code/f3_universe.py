"""F3: pre-registered universe U(W): Gamma closed markets with endDate in [D0, D1), volumeNum>=20k,
closedTime < H, not sports (gameStartTime/sportsMarketType null), not crypto up/down.
Then CLOB hourly price history of token 0 over [endDate-14d, endDate+14d] (chunk 1 to endDate+1d; chunk 2 only if still open).
Rows whose closedTime >= H are dropped immediately without inspection (holdout discipline)."""
import sys, json, re, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import pandas as pd, numpy as np
from polyrea.adapters.http import shared_client, HttpError
H = 1792713600
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
h = shared_client()
D0, D1 = sys.argv[1], sys.argv[2]
tag = sys.argv[3]
def ts(s):
    try: return pd.Timestamp(s).timestamp()
    except Exception: return np.nan
def scan(a, b):
    got = []; off = 0
    while True:
        try:
            d, _ = h.get_json('https://gamma-api.polymarket.com/markets', {'closed': 'true', 'end_date_min': pd.Timestamp(a, unit='s', tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'end_date_max': pd.Timestamp(b, unit='s', tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ'), 'volume_num_min': 20000, 'limit': 100, 'offset': off}, adapter='gamma.markets', max_age=None)
        except HttpError as e:
            if b - a > 60:
                mid = (a + b) // 2; return scan(a, mid) + scan(mid + 1, b)
            print('gamma error', a, b, off, e.status, flush=True); return got
        got += d or []
        if not d or len(d) < 100: return got
        off += 100
        if off >= 1500:
            if b - a <= 60:
                print('gamma truncated', a, flush=True); return got
            mid = (a + b) // 2; return scan(a, mid) + scan(mid + 1, b)
SPORT_SLUG = re.compile(r'^(nfl|nba|mlb|nhl|epl|ucl|uel|atp|wta|ufc|mma|cs2|lol|dota2|val|cbb|cfb|ncaab|kbo|npb|bra|arg|lib|sud|mex|ser|lal|bun|fl1|ere|por|tur|el1|crint|cricipl|cricetpl|f1|box|wnba|mls|aus|jpn|kor|chn|sau|ufl|nascar|golf|pga)-')
keep = ['conditionId','question','slug','outcomes','clobTokenIds','endDate','startDate','createdAt','closedTime','outcomePrices','volumeNum','liquidityNum','negRisk','negRiskMarketID',
        'groupItemTitle','orderPriceMinTickSize','orderMinSize','feesEnabled','feeType','umaResolutionStatus','gameStartTime','sportsMarketType','rewardsMinSize','rewardsMaxSpread']
rows = []
days = pd.date_range(D0, D1, freq='D', tz='UTC')
for d0, d1 in zip(days[:-1], days[1:]):
    ms = scan(int(d0.timestamp()), int(d1.timestamp()) - 1)
    for m in ms:
        ct = ts(m.get('closedTime'))
        if not (ct < H): continue  # holdout rows dropped unseen
        r = {k: m.get(k) for k in keep}
        ev = (m.get('events') or [{}])[0]
        r['event_slug'] = ev.get('slug'); r['event_id'] = ev.get('id'); r['event_title'] = ev.get('title')
        r['closed_ts'] = ct; r['end_ts'] = ts(m.get('endDate')); r['start_ts'] = ts(m.get('startDate') or m.get('createdAt'))
        rows.append(r)
    print(d0.date(), 'gamma', len(ms), 'kept so far', len(rows), flush=True)
u = pd.DataFrame(rows).drop_duplicates('conditionId')
u['is_sport'] = u.gameStartTime.notna() | u.sportsMarketType.notna() | u.slug.fillna('').str.match(SPORT_SLUG)
u['is_updown'] = u.slug.fillna('').str.contains('updown|up-or-down') | u.question.fillna('').str.contains('Up or Down')
u.to_parquet(OUT + f'universe_meta_{tag}.parquet')
uu = u[~u.is_sport & ~u.is_updown]
print('universe all', len(u), 'non-sport non-updown', len(uu), flush=True)
if len(sys.argv) > 4 and sys.argv[4] == 'gamma_only': sys.exit(0)
# prices (thread pool; the shared client rate-limits per host and the cache is safe for concurrent use)
from concurrent.futures import ThreadPoolExecutor
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
P = {}
t0 = time.time()
with ThreadPoolExecutor(6) as ex:
    for i, (c, pts) in enumerate(ex.map(fetch, list(uu.itertuples()))):
        P[c] = pts
        if i % 500 == 0: print('prices', i, len(uu), round(time.time() - t0), flush=True)
pd.to_pickle(P, OUT + f'universe_prices_{tag}.pkl')
print('done', len(P), flush=True)
