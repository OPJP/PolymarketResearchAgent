"""Are data-api tape timestamps the Polygon block timestamps of the settlement tx?
(If so, a print stamped ts was matched off-chain at or before ts, so 'latency 0' decisions
and maker fills in (t0, t0+R] can involve trades matched before the decision.) 6 txs, 12 RPC calls."""
import pickle
from pathlib import Path
from polyrea.adapters.chain import PolygonChain
from polyrea.adapters.http import shared_client

D = pickle.load(open(Path(__file__).parent / "data" / "btc5m.pkl", "rb"))
tapes = D["test"]["tapes"]
rows = []
for cid in list(tapes)[100:106]:
    r = tapes[cid][len(tapes[cid]) // 2]
    rows.append((r["transactionHash"], int(r["timestamp"])))
ch = PolygonChain(); http = shared_client()
recs, _ = ch.receipts([h for h, _ in rows])
for h, ts in rows:
    rc = recs.get(h)
    if not rc:
        print(h, "no receipt"); continue
    blk, _ = http.post_json("https://polygon.drpc.org", {"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": [rc["blockNumber"], False]}, adapter="polygon.rpc.block", max_age=None, max_retries=2)
    bts = int(blk["result"]["timestamp"], 16)
    print(f"tx {h[:12]}.. data-api ts {ts}  block {int(rc['blockNumber'],16)} block ts {bts}  diff {ts - bts}")
