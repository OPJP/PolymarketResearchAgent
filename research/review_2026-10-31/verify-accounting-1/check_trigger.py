# For each of the 19 walked seconds, find the cached descending page (limit=500, end=ts... ) that triggered it.
import sqlite3, zlib, json, sys
from urllib.parse import urlsplit, parse_qs
db = sqlite3.connect(sys.argv[1])
walks = json.load(open(sys.argv[2]))
rows = db.execute("SELECT url, body FROM responses WHERE url LIKE 'https://data-api.polymarket.com/trades?%limit=500%'").fetchall()
idx = {}
for url, blob in rows:
    q = parse_qs(urlsplit(url).query)
    if 'sortBy' in q: continue
    idx.setdefault(q['market'][0], []).append((q, blob))
for w in walks:
    found = []
    for q, blob in idx.get(w['market'], []):
        if q.get('takerOnly') != ['false']: continue
        if int(q['end'][0]) == w['ts'] or True:
            body = json.loads(zlib.decompress(blob))
            if len(body) == 500 and all(r['timestamp'] == w['ts'] for r in body):
                found.append((q.get('start'), q.get('end'), len(body)))
    print(w['ts'], w['market'][:12], 'trigger pages:', found)
