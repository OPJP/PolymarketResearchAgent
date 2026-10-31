import sqlite3, zlib, json, sys
db = sqlite3.connect('/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/audit-statistics/cache/http.sqlite')
w = sys.argv[1]
rows = db.execute("SELECT url, fetched_at, body FROM responses WHERE url LIKE ?", (f"%user-pnl%{w}%",)).fetchall()
for url, fa, b in rows:
    d = json.loads(zlib.decompress(b))
    pts = d['data']['points']
    print(url, fa, len(pts))
    for p in pts[:3] + pts[-4:]:
        print(p)
    ts = [p['timestamp'] for p in pts]
    import collections
    print('non-midnight:', [t for t in ts if t % 86400], 'gaps:', collections.Counter((b-a)//86400 for a,b in zip(ts, ts[1:]) if a%86400==0 and b%86400==0))
