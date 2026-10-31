# Direct reproduction through the real market_trades() on one affected window, offline on the cache copy.
import sys, json
from collections import Counter
sys.path.insert(0, sys.argv[1])
from polyrea.adapters.http import HttpClient
from polyrea.adapters.polymarket import PolymarketData
import fixed_scan
W = sys.argv[1]
http = HttpClient(cache_dir=__import__('pathlib').Path(W) / 'cache', offline=True)
pm = PolymarketData(http)
cid_prefix = '0x0d70225ec4'
walks = [w for w in json.load(open(W + '/walks.json')) if w['market'].startswith(cid_prefix)]
cid = walks[0]['market']
start = 1792760100
# find end from the cached first descending request
import sqlite3
db = sqlite3.connect(W + '/cache/http.sqlite')
ends = [u for (u,) in db.execute("select url from responses where url like ?", (f"%market={cid}&takerOnly=false&limit=500&start={start}&end=%",))]
from urllib.parse import parse_qs, urlsplit
end = max(int(parse_qs(urlsplit(u).query)['end'][0]) for u in ends)
print('market', cid, 'start', start, 'end', end)
rows, src, cov = pm.market_trades(cid, start=start, end=end, taker_only=False)
c = Counter(r['timestamp'] for r in rows)
print('CURRENT  rows', len(rows), 'requests', len(src), 'coverage', cov.status, '|', {w['ts']: c[w['ts']] for w in walks})
fixed_scan.install()
http2 = HttpClient(cache_dir=__import__('pathlib').Path(W) / 'cache', offline=True)
rows2, src2, cov2 = PolymarketData(http2).market_trades(cid, start=start, end=end, taker_only=False)
c2 = Counter(r['timestamp'] for r in rows2)
print('FIXED    rows', len(rows2), 'requests', len(src2), 'coverage', cov2.status, '|', {w['ts']: c2[w['ts']] for w in walks})
print('urls of walk pages in current run:', [s.url[-90:] for s in src if 'start=17927639' in s.url and 'end=17927639' in s.url and 'offset' in s.url][:4])
