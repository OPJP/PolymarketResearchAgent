import sqlite3, zlib, json, sys, re
from urllib.parse import urlsplit, parse_qs
db = sqlite3.connect(sys.argv[1])
rows = db.execute("SELECT url, fetched_at, body FROM responses WHERE url LIKE 'https://data-api.polymarket.com/trades?%'").fetchall()
print("total cached /trades URLs:", len(rows))
walks = []
other_eq = []
for url, fa, blob in rows:
    q = parse_qs(urlsplit(url).query)
    if 'start' in q and 'end' in q and q['start'] == q['end']:
        body = json.loads(zlib.decompress(blob))
        n = len(body) if isinstance(body, list) else None
        rec = dict(url=url, n=n, has_limit='limit' in q, offset=q.get('offset'), takerOnly=q.get('takerOnly'), market=q.get('market',[None])[0], ts=int(q['start'][0]))
        (walks if not rec['has_limit'] else other_eq).append(rec)
print("start==end walks WITHOUT limit:", len(walks))
print("start==end walks WITH limit:", len(other_eq))
from collections import Counter
print("row-count distribution (no limit):", Counter(w['n'] for w in walks))
print("offset distribution (no limit):", Counter(tuple(w['offset'] or []) for w in walks))
print("takerOnly:", Counter(tuple(w['takerOnly'] or []) for w in walks))
for w in sorted(walks, key=lambda r: r['ts']):
    print(w['ts'], w['market'][:12], w['n'], w['offset'], w['takerOnly'])
json.dump(walks, open(sys.argv[2], 'w'), indent=1)
# also: how many descending (no sortBy) full pages of 500 cached with limit=500 and start/end not equal on one ts?
