import sqlite3, zlib, json, sys
db = sqlite3.connect(sys.argv[1])
walks = json.load(open(sys.argv[2]))
cids = {w['market'] for w in walks}
found = {}
for url, blob in db.execute("select url, body from responses where url like 'https://gamma-api.polymarket.com/markets?%slug=btc-updown%'"):
    try: data = json.loads(zlib.decompress(blob))
    except Exception: continue
    for m in data or []:
        if m.get('conditionId') in cids: found[m['conditionId']] = m.get('slug')
for c in sorted(cids): print(c[:12], found.get(c))
