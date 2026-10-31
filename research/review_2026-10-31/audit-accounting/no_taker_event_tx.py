"""Receipts whose OrderFilled events have no 'taker-order' event (taker topic == emitter): what are they?"""
import _env, sqlite3, zlib, json
from polyrea.adapters.chain import decode_fills
db = sqlite3.connect('file:' + _env.SCR + '/cache/http.sqlite?mode=ro', uri=True)
studied = set(_env.WALLETS.values()) | {'0x3048d65321be3497164cdfc2996f94f98a2e7537', '0xc53375ff94e96100f2b30a4b5775db35218d69a9'}
for url, body in db.execute("select url, body from responses where url like 'https://polygon%'"):
    data = json.loads(zlib.decompress(body))
    for it in (data if isinstance(data, list) else [data]):
        r = it.get('result') if isinstance(it, dict) else None
        if not r: continue
        f = decode_fills(r)
        if f and not any(x.taker == x.exchange for x in f):
            makers = {x.maker for x in f}; takers = {x.taker for x in f}
            print(r['transactionHash'][:14], 'events', len(f), 'distinct makers', len(makers), 'distinct taker topics', [t[:10] for t in takers], 'studied wallet as maker:', [w[:10] for w in makers & studied], 'as taker topic:', [w[:10] for w in takers & studied], 'logs total', len(r.get('logs') or []))
