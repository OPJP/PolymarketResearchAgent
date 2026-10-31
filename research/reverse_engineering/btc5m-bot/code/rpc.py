"""Cached Polygon RPC helpers (drpc via polyrea HttpClient; every call cached)."""
import sys
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.adapters.http import shared_client, HttpError

RPC = "https://polygon.drpc.org"
RPC2 = "https://polygon-bor-rpc.publicnode.com"
V2_EXCHANGES = ["0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"]
TOPIC_V2 = "0xd543adfd945773f1a62f74f0ee55a5e3b9b1a28262980ba90b1a89f2ea84d8ee"
_http = shared_client()


def call(method, params, max_age=None, rpc=RPC):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    last = None
    for url in (rpc, RPC2):
        try:
            res, _ = _http.post_json(url, body, adapter="polygon.rpc." + method, max_age=max_age, max_retries=3)
        except HttpError as e:
            last = e
            continue
        if isinstance(res, dict) and "result" in res and res["result"] is not None:
            return res["result"]
        last = res
    raise RuntimeError(f"rpc failed {method} {params}: {str(last)[:300]}")


def block_ts(n):
    b = call("eth_getBlockByNumber", [hex(n), False])
    return int(b["timestamp"], 16)


def pad(addr):
    return "0x" + addr.lower().replace("0x", "").rjust(64, "0")


def get_logs(address, from_block, to_block, topics):
    return call("eth_getLogs", [{"address": address, "fromBlock": hex(from_block), "toBlock": hex(to_block), "topics": topics}])
