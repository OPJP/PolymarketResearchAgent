"""Across all cached Polygon receipts: is role_of's rule (taker topic == emitting contract) consistent?
Checks every OrderFilled log: emitting address vs taker topic, and per-tx structure (one taker-order event per match)."""
import _env, sqlite3, zlib, json, collections
from polyrea.adapters.chain import decode_fills, ORDER_FILLED_V1, ORDER_FILLED_V2
db = sqlite3.connect('file:' + _env.SCR + '/cache/http.sqlite?mode=ro', uri=True)
addr_c = collections.Counter(); taker_eq = collections.Counter(); per_tx = collections.Counter()
taker_is_other_exchange = collections.Counter(); n_rec = 0
fee_side = collections.Counter(); v1v2 = collections.Counter()
exch = set()
receipts = []
for url, body in db.execute("select url, body from responses where url like 'https://polygon%'"):
    data = json.loads(zlib.decompress(body))
    items = data if isinstance(data, list) else [data]
    for it in items:
        r = it.get('result') if isinstance(it, dict) else None
        if r: receipts.append(r)
for r in receipts:
    n_rec += 1
    fills = decode_fills(r)
    for f in fills:
        exch.add(f.exchange)
for r in receipts:
    fills = decode_fills(r)
    n_self = 0
    for f in fills:
        addr_c[(f.version, f.exchange[:10])] += 1
        if f.taker == f.exchange:
            n_self += 1
        elif f.taker in exch:
            taker_is_other_exchange[(f.exchange[:10], f.taker[:10])] += 1
        if f.fee > 0:
            fee_side[(f.version, f.side, 'taker-order' if f.taker == f.exchange else 'maker-order')] += 1
    per_tx[n_self] += 1
print('receipts', n_rec)
print('OrderFilled by (version, emitting contract):', dict(addr_c))
print('taker-topic is a DIFFERENT exchange contract than emitter:', dict(taker_is_other_exchange))
print('number of events per tx whose taker topic == emitter:', dict(sorted(per_tx.items())))
print('events with fee>0 by (version, side, order kind):', dict(fee_side))
