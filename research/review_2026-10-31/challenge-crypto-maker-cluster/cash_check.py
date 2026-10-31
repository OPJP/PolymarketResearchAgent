# Find the collateral ERC20 from a cached fill receipt, then read current collateral balances (upper bound on resting-order collateral).
import sys, json, collections; sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.workflows.investigate import load_window
from polyrea.adapters.chain import PolygonChain
from polyrea.adapters.http import shared_client
AS_OF = 1793318400
W = {'bosona': '0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed', 'almach': '0x3725d52f3c252e8374999cc8617292ea2608ad88'}
tr = load_window(W['bosona'], 30, as_of=AS_OF)['trades']
ch = PolygonChain(); rec, _ = ch.receipts(tr.tx.tolist()[-3:])
TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
cnt = collections.Counter()
for r in rec.values():
    for lg in (r or {}).get('logs', []):
        if lg['topics'] and lg['topics'][0] == TRANSFER and len(lg['topics']) == 3:
            cnt[lg['address'].lower()] += 1
print('ERC20 transfer emitters in recent fill receipts:', dict(cnt))
http = shared_client(); out = {}
for tok in cnt:
    for nm, w in W.items():
        data = '0x70a08231' + '0' * 24 + w[2:]
        res, _ = http.post_json('https://polygon.drpc.org', {'jsonrpc': '2.0', 'id': 1, 'method': 'eth_call', 'params': [{'to': tok, 'data': data}, 'latest']}, adapter='polygon.rpc.balance', max_age=0, max_retries=2)
        bal = int(res['result'], 16) / 1e6 if res and res.get('result') not in (None, '0x') else None
        out[f'{nm}@{tok}'] = bal
print(json.dumps(out, indent=1))
json.dump({'emitters': dict(cnt), 'balances_usd_6dp': out}, open('/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster/cash_check.json', 'w'), indent=1)
