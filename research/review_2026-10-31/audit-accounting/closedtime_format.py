import _env, sqlite3, zlib, json, collections, re
from polyrea.analysis.profile import resolution_info
db = sqlite3.connect('file:' + _env.SCR + '/cache/http.sqlite?mode=ro', uri=True)
fmts = collections.Counter(); unparsed = collections.Counter(); resolved_stat = collections.Counter()
ex = {}
for url, body in db.execute("select url, body from responses where url like 'https://gamma-api.polymarket.com/markets%'"):
    data = json.loads(zlib.decompress(body))
    if not isinstance(data, list): continue
    for m in data:
        ct = m.get('closedTime')
        f = re.sub(r'\d', '9', ct) if ct else None
        fmts[f] += 1
        ex.setdefault(f, ct)
        r = resolution_info(m)
        resolved_stat[(bool(m.get('closed')), m.get('umaResolutionStatus'), r['resolved'], r['closed_ts'] is not None)] += 1
        if r['resolved'] and r['closed_ts'] is None:
            unparsed[f] += 1
print('closedTime formats:'); [print(' ', v, k, ex[k]) for k, v in fmts.most_common()]
print('resolved but closed_ts None by format:', dict(unparsed))
print('(closed, umaStatus, resolved, has_closed_ts):'); [print(' ', k, v) for k, v in resolved_stat.most_common()]
