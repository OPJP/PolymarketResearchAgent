"""Inspect cached /trades and /activity responses: do start/end bound the rows, inclusive or exclusive?"""
import sqlite3, zlib, json, collections
from urllib.parse import urlsplit, parse_qs
db = sqlite3.connect('file:/home/user/PolymarketResearchAgent/.cache/http.sqlite?mode=ro', uri=True)
stats = collections.Counter()
examples = []
for ep in ('data-api.polymarket.com/trades', 'data-api.polymarket.com/activity'):
    n = 0
    for url, body in db.execute("select url, body from responses where url like ? limit 4000", (f'https://{ep}%',)):
        q = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        rows = json.loads(zlib.decompress(body))
        if not isinstance(rows, list) or not rows:
            stats[(ep, 'empty')] += 1
            continue
        ts = [r['timestamp'] for r in rows]
        s, e = q.get('start'), q.get('end')
        if e is not None:
            e = int(e)
            stats[(ep, 'max>end')] += max(ts) > e
            stats[(ep, 'has_row_at_end')] += (e in ts)
        if s is not None:
            s = int(s)
            stats[(ep, 'min<start')] += min(ts) < s
            stats[(ep, 'has_row_at_start')] += (s in ts)
        order = 'asc' if ts == sorted(ts) else ('desc' if ts == sorted(ts, reverse=True) else 'mixed')
        stats[(ep, 'order_' + order)] += 1
        stats[(ep, 'len_' + ('500' if len(rows) == 500 else '<500'))] += 1
        stats[(ep, 'n')] += 1
        if len(examples) < 4 and ep.endswith('trades'):
            examples.append((url, len(rows), min(ts), max(ts)))
for k in sorted(stats): print(k, stats[k])
for e in examples: print(e)
