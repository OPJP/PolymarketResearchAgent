"""The 19 real offset walks in the cache: each one was a second with >= 500 tape rows. How many rows exist vs. kept?"""
import _env, sqlite3, zlib, json, re, collections
from polyrea.adapters.http import HttpClient
db = sqlite3.connect('file:' + _env.SCR + '/cache/http.sqlite?mode=ro', uri=True)
walks = []
for url, body in db.execute("select url, body from responses where url like 'https://data-api.polymarket.com/trades%' and url like '%offset=%' and url not like '%limit=%'"):
    q = dict(re.findall(r'([a-zA-Z]+)=([^&]+)', url.split('?', 1)[1]))
    walks.append((q['market'], int(q['start']), q['takerOnly'], len(json.loads(zlib.decompress(body)))))
# slugs from cached gamma
slugs = {}
for url, body in db.execute("select url, body from responses where url like 'https://gamma-api.polymarket.com/markets%'"):
    for m in json.loads(zlib.decompress(body)) or []:
        slugs[m.get('conditionId')] = m.get('slug')
http = HttpClient()  # scratch cache (POLYREA_CACHE_DIR), network allowed
tot_true = tot_kept = 0
for i, (mkt, ts, taker_only, kept) in enumerate(sorted(walks)):
    true_n = None
    if i < 6:  # live re-count for a few, modest
        true_n = 0
        for off in range(0, 5001, 500):
            rows, _ = http.get_json('https://data-api.polymarket.com/trades', {'market': mkt, 'takerOnly': taker_only, 'start': ts, 'end': ts, 'limit': 500, 'offset': off}, adapter='audit', max_age=None)
            true_n += len(rows)
            if len(rows) < 500: break
        tot_true += true_n; tot_kept += kept
    print(f'{mkt[:12]} {slugs.get(mkt, "?")[:48]:48s} second {ts} takerOnly={taker_only} kept {kept}' + (f' | actual rows in that second {true_n}' if true_n is not None else ''))
print(f'live re-counted seconds: kept {tot_kept} of {tot_true} rows')
