"""Are elmcap2's two exact-duplicate TRADE rows real double fills? Decode the receipts."""
import _env, os, pickle, json, collections, sqlite3, zlib
from polyrea.adapters.chain import PolygonChain, decode_fills
win = pickle.load(open(os.path.join(_env.SCR, 'win_elmcap2.pkl'), 'rb'))
w = win['wallet']
txs = ['0x1f248295cf4251f12009560ec30148a089e2c35906ad97c54a5783474eec5b0e', '0x927f22ba0400d3405dc21cf3253673f807c5c8922bb1bd50575d32a0f3fad5e0']
rec, _ = PolygonChain().receipts(txs)
for tx in txs:
    api = [r for r in win['activity'] if r.get('transactionHash') == tx]
    print('== tx', tx[:14], 'API rows for wallet:', [(r['type'], r.get('side'), r.get('asset')[:10], r.get('size'), r.get('usdcSize')) for r in api])
    fills = decode_fills(rec[tx])
    for f in fills:
        tag = 'WALLET-ORDER' if f.maker == w else ('wallet=taker-topic' if f.taker == w else '')
        print(f'   log {f.log_index} {f.version} side={f.side} maker={f.maker[:10]} taker={f.taker[:10]} token={f.token_id[:10]} shares={f.shares} usdc={f.usdc} fee={f.fee} {tag}')
    mine = [f for f in fills if f.maker == w]
    print('   wallet own-order shares on chain:', sum(f.shares for f in mine), ' API sum:', sum(float(r['size']) for r in api if r['type'] == 'TRADE'))
# which cached activity pages contain the duplicated row?
db = sqlite3.connect('file:' + _env.SCR + '/cache/http.sqlite?mode=ro', uri=True)
for url, body in db.execute("select url, body from responses where url like ?", (f'https://data-api.polymarket.com/activity?user={w}%end=1793318400%',)):
    rows = json.loads(zlib.decompress(body))
    for tx in txs:
        n = sum(1 for r in rows if r.get('transactionHash') == tx)
        if n:
            print('page', url.split('start=')[1][:22], 'rows', len(rows), 'first_ts', rows[0]['timestamp'], 'last_ts', rows[-1]['timestamp'], 'count of tx', tx[:10], n)
