"""Drive PolymarketData._cursor_scan (both paths) against an in-memory fake API with known ground truth.

Fake API semantics match what the cache shows for the real one: start/end inclusive, limit 500,
/activity honours sortDirection=ASC, /trades returns newest first, offset beyond `offset_cap` -> HTTP 400.
"""
import _env, random, collections
from polyrea.adapters.polymarket import PolymarketData, activity_key
from polyrea.adapters.http import HttpError
from polyrea.evidence import Source

class FakeHttp:
    def __init__(self, rows, offset_cap=5000):
        self.rows = sorted(rows, key=lambda r: (r['timestamp'], r['_id']))
        self.offset_cap = offset_cap; self.calls = 0
    def get_json(self, url, params, adapter, max_age=None, **kw):
        self.calls += 1
        p = dict(params)
        off = int(p.get('offset', 0))
        if off > self.offset_cap:
            raise HttpError(400, url, 'offset too large')
        s = p.get('start'); e = p.get('end')
        sel = [r for r in self.rows if (s is None or r['timestamp'] >= s) and (e is None or r['timestamp'] <= e)]
        if p.get('sortDirection') != 'ASC':
            sel = sel[::-1]
        page = sel[off: off + int(p.get('limit', 100))]  # real API default limit is 100 (cache shows 19 such pages)
        return [dict(r) for r in page], Source(adapter=adapter, url=url, fetched_at='', body_sha256='', cached=False)

def mk(n_by_ts, dup_every=0):
    rows, i = [], 0
    for ts, n in n_by_ts:
        for k in range(n):
            rows.append({'_id': i, 'timestamp': ts, 'transactionHash': f'0x{ts:x}{k // 2 if dup_every else k}', 'asset': 'a', 'type': 'TRADE', 'side': 'BUY',
                         'size': 10.0, 'price': 0.5, 'conditionId': 'c'})
            i += 1
    return rows

def check(name, rows, path, offset_cap=5000):
    pm = PolymarketData(http=FakeHttp(rows, offset_cap))
    asc = path == 'asc'
    got, src, cov = pm._cursor_scan('https://x/activity' if asc else 'https://x/trades', {}, start=None, end=10**10, adapter='t', max_rows=None, ascending_supported=asc)
    truth = collections.Counter(activity_key(r) for r in rows)
    have = collections.Counter(activity_key(r) for r in got)
    missing = sum((truth - have).values()); extra = sum((have - truth).values())
    print(f'{name:58s} [{path}] truth {len(rows):6d} got {len(got):6d} missing {missing:5d} dup {extra:4d} coverage={cov.status!r} ({pm.http.calls} calls)')

random.seed(1)
base = [(t, random.randint(1, 40)) for t in range(1000, 1600)]
check('ordinary history, ties at every page boundary', mk(base), 'asc')
check('ordinary history, ties at every page boundary', mk(base), 'desc')
check('identical rows (pairs share tx/size/price) across boundaries', mk(base, dup_every=2), 'asc')
check('identical rows (pairs share tx/size/price) across boundaries', mk(base, dup_every=2), 'desc')
check('one second with 1,200 rows', mk(base[:50] + [(2000, 1200)] + base[50:60]), 'asc')
check('one second with 1,200 rows', mk(base[:50] + [(2000, 1200)] + base[50:60]), 'desc')
check('one second with 7,000 rows (> offset walk cap 5,500)', mk(base[:50] + [(2000, 7000)] + base[50:60]), 'asc')
check('one second with 7,000 rows (> offset walk cap 5,500)', mk(base[:50] + [(2000, 7000)] + base[50:60]), 'desc')
check('one second with 2,000 rows, API offset cap 1,000', mk(base[:50] + [(2000, 2000)] + base[50:60]), 'asc', offset_cap=1000)
check('one second with 2,000 rows, API offset cap 1,000', mk(base[:50] + [(2000, 2000)] + base[50:60]), 'desc', offset_cap=1000)
dense = [(3000 + 10 * k, 600) for k in range(12)]
check('12 separate seconds with 600 rows each (stall counter)', mk(base[:30] + dense + [(9000, 30)]), 'asc')
check('12 separate seconds with 600 rows each (stall counter)', mk(base[:30] + dense + [(9000, 30)]), 'desc')
