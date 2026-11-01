"""directional-maker iteration 14, X156 step 1 probe (panel iter13 information I13-3): does GMX v2 on Arbitrum publish
Chainlink Data Streams BTC prices on chain densely enough to stand in for the settlement stream before the 30-day horizon?

Probe on the development block 10-31 15:00-15:02 UTC (where dm_rtds holds every Chainlink second): EventEmitter
(0xC8ee91A54287DB53897056e12D9819156D3822Fb) logs whose non-indexed eventName is "OraclePriceUpdate"; extract the uint
words that look like a BTC price (x 1e22, the GMX 30-decimal convention for an 8-decimal token) and like a unix time;
compare (min+max)/2 with the Chainlink value of the same stamp. Through polyrea's HttpClient (cached).
    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/gmx_probe.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research/reverse_engineering/directional-maker/code"))
from polyrea.adapters.http import HttpClient  # noqa: E402

RPC = "https://arbitrum-one-rpc.publicnode.com"
EMITTER = "0xc8ee91a54287db53897056e12d9819156d3822fb"
NAME_HEX = "OraclePriceUpdate".encode().hex()
http = HttpClient(rates={"arbitrum-one-rpc.publicnode.com": 3.0})


def rpc(method, params, cache=True):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r, _ = http.post_json(RPC, body, adapter="arbitrum_rpc", max_age=None if cache else 0.0)
    if "error" in r:
        raise RuntimeError(r["error"])
    return r["result"]


def block_ts(n):
    return int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)


def find_block(ts):
    hi = int(rpc("eth_blockNumber", [], cache=False), 16)
    hts = block_ts(hi)
    lo = hi - int((hts - ts) * 4.5) - 20000
    for _ in range(40):
        if hi - lo <= 1:
            break
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid
        else:
            hi = mid
    return hi


def main():
    t0 = 1793458800
    b0 = find_block(t0)
    print("block at", t0, b0, block_ts(b0))
    logs = []
    for a in range(b0, b0 + 480, 120):
        logs += rpc("eth_getLogs", [{"address": EMITTER, "fromBlock": hex(a), "toBlock": hex(a + 119)}])
    print("emitter logs", len(logs))
    hits = [lg for lg in logs if NAME_HEX in lg["data"]]
    print("OraclePriceUpdate logs", len(hits))
    out = []
    for lg in hits:
        d = lg["data"][2:]
        words = [int(d[i:i + 64], 16) for i in range(0, len(d), 64)]
        prices = [w / 1e22 for w in words if 3e26 < w < 2e27]
        times = [w for w in words if 1.78e9 < w < 1.81e9]
        addrs = ["0x" + d[i + 24:i + 64] for i in range(0, len(d), 64) if d[i:i + 24] == "0" * 24 and int(d[i + 24:i + 64], 16) > 2 ** 100]
        out.append({"block": int(lg["blockNumber"], 16), "prices": prices[:4], "times": times[:3], "addrs": addrs[:4], "topics": lg["topics"][:3]})
    btc = [o for o in out if o["prices"]]
    print("with BTC-like price words", len(btc))
    for o in btc[:6]:
        print(json.dumps(o)[:400])
    import cl_source
    st = sorted({t for o in btc for t in o["times"]})
    clv = cl_source.cl_values(st, allow_sealed=False, fetch=False) if st else None
    diffs = []
    for o in btc:
        if o["times"] and len(o["prices"]) >= 2 and clv is not None:
            v = clv.get(o["times"][0])
            if v == v and v is not None:
                diffs.append(round((o["prices"][0] + o["prices"][1]) / 2 - float(v), 2))
    res = {"block0": b0, "logs": len(logs), "oracle_updates": len(hits), "btc_like": len(btc), "diff_mid_minus_chainlink": diffs[:40],
           "n_compared": len(diffs), "distinct_times": len(st)}
    print(json.dumps(res)[:1500])
    (ROOT / "research/reverse_engineering/directional-maker/results/iter14_gmx_probe.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
