"""Exercise decode_fills / role_of on real CTF Exchange V1 receipts (none are in the research cache)."""
import _env
from polyrea.adapters.http import HttpClient
from polyrea.adapters.chain import PolygonChain, decode_fills, ORDER_FILLED_V1
http = HttpClient()
w = _env.WALLETS['RN1']
rows, _ = http.get_json('https://data-api.polymarket.com/activity', {'user': w, 'limit': 20, 'start': 1756684800, 'end': 1756771200, 'type': 'TRADE', 'sortBy': 'TIMESTAMP', 'sortDirection': 'ASC'}, adapter='audit', max_age=None)
print('old activity rows', len(rows))
txs = list(dict.fromkeys(r['transactionHash'] for r in rows))[:6]
rec, _ = PolygonChain().receipts(txs)
for tx in txs:
    api = [r for r in rows if r['transactionHash'] == tx]
    fills = decode_fills(rec[tx]) if rec.get(tx) else []
    mine = [f for f in fills if f.maker == w]
    kinds = {(f.version, f.exchange[:10]) for f in fills}
    n_self = sum(1 for f in fills if f.taker == f.exchange)
    print(tx[:12], 'API', [(r['side'], r['asset'][:8], r['size'], r['usdcSize'], r['price']) for r in api])
    print('    chain', kinds, 'taker-order events', n_self, 'wallet events', [(f.side, f.token_id[:8], f.shares, round(f.usdc, 4), round(f.price, 4), f.fee, f.role_of(w)) for f in mine])
