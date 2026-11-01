"""X166 (mechanics panel iter-11 P4): lineage of the deposit wallet (creation, first funding, possible predecessor).

Polygon JSON-RPC (publicnode, as code/iter6/funding_graph.py), read-only calls only:
  1. eth_getTransactionCount / eth_getCode of the owner EOA 0x8af810f0... and of the deposit wallet;
  2. the deployment block of the deposit wallet by binary search on eth_getCode (archive state);
  3. the deployment transaction's creator (the block's transactions that touch the factory) and the first incoming
     USDC.e / USDC Transfer logs to the wallet in the first days after deployment;
  4. Polymarket's own Safe factory computeProxyAddress(owner) (eth_call) and data-api activity of that address and of the
     owner EOA, development periods only (everything before H).
Output: results/lineage.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter8"))
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
RPC = "https://polygon-bor-rpc.publicnode.com"
ARCHIVE = "https://polygon.drpc.org"  # publicnode refuses archive state without a token (verified 2026-11-01)
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OWNER = "0x8af810f0e236cae55588ea6a084013c24122fd4f"
SAFE_FACTORY = "0xaacfeea03eb1561c4e67d661e40682bd20e3541b"
USDCE = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"
USDC = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
H = 1792713600


def rpc(c, method, params, url=None):
    url = url or (ARCHIVE if method in ("eth_getCode", "eth_getLogs", "eth_getBlockByNumber", "eth_getTransactionReceipt") else RPC)
    last = None
    for k in range(5):
        try:
            r = c.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=30)
            j = r.json()
            if "error" in j:
                return {"error": j["error"]}
            return j.get("result")
        except Exception as e:  # noqa: BLE001
            time.sleep(1 + k)
            last = e
    return {"error": str(last)}


def main():
    from sigrecover import keccak  # pure-Python keccak of iteration 8
    out = {}
    with httpx.Client(headers={"content-type": "application/json"}) as c:
        latest = int(rpc(c, "eth_blockNumber", []), 16)
        out["latest_block"] = latest
        out["owner_nonce"] = int(rpc(c, "eth_getTransactionCount", [OWNER, "latest"]), 16)
        out["owner_code_len"] = (len(rpc(c, "eth_getCode", [OWNER, "latest"])) - 2) // 2
        code = rpc(c, "eth_getCode", [WALLET, "latest"])
        out["wallet_code_len"] = (len(code) - 2) // 2 if isinstance(code, str) else code
        # deployment block by binary search
        lo, hi = 80_000_000, latest
        probe = rpc(c, "eth_getCode", [WALLET, hex(lo)])
        out["archive_probe"] = "ok" if isinstance(probe, str) else probe
        dep = None
        if isinstance(probe, str):
            while hi - lo > 1:
                mid = (lo + hi) // 2
                cc = rpc(c, "eth_getCode", [WALLET, hex(mid)])
                if not isinstance(cc, str):
                    out["bsearch_error"] = cc; break
                if len(cc) > 2:
                    hi = mid
                else:
                    lo = mid
            dep = hi
        out["deploy_block"] = dep
        if dep:
            b = rpc(c, "eth_getBlockByNumber", [hex(dep), True])
            out["deploy_ts"] = int(b["timestamp"], 16)
            txs = [t for t in b["transactions"] if WALLET[2:] in (t.get("input") or "").lower() or (t.get("to") or "").lower() == WALLET]
            # the creating tx: receipt that lists the wallet as a log address or contractAddress
            cand = []
            for t in b["transactions"]:
                rc = rpc(c, "eth_getTransactionReceipt", [t["hash"]])
                if isinstance(rc, dict) and any((lg.get("address") or "").lower() == WALLET for lg in rc.get("logs", [])) or (isinstance(rc, dict) and (rc.get("contractAddress") or "").lower() == WALLET):
                    cand.append({"hash": t["hash"], "from": t["from"], "to": t.get("to"), "selector": (t.get("input") or "")[:10]})
                if len(cand) >= 3:
                    break
            out["deploy_txs"] = cand
            out["txs_mentioning_wallet_in_input"] = [{"hash": t["hash"], "from": t["from"], "to": t.get("to")} for t in txs[:5]]
            # first incoming transfers (USDC.e and USDC) over ~10 days after deployment
            pad = "0x" + "0" * 24 + WALLET[2:]
            first = []
            for tok in (USDCE, USDC):
                start = dep
                for _ in range(150):
                    end = start + 2999
                    lg = rpc(c, "eth_getLogs", [{"address": tok, "fromBlock": hex(start), "toBlock": hex(end), "topics": [TRANSFER, None, pad]}])
                    if isinstance(lg, list) and lg:
                        for x in lg[:5]:
                            first.append({"token": tok, "block": int(x["blockNumber"], 16), "from": "0x" + x["topics"][1][-40:],
                                          "amount": int(x["data"], 16) / 1e6, "tx": x["transactionHash"]})
                        break
                    start = end + 1
                    time.sleep(0.2)
            out["first_incoming"] = sorted(first, key=lambda z: z["block"])[:8]
            srcs = {}
            for f in out["first_incoming"]:
                a = f["from"]
                if a in srcs:
                    continue
                cc = rpc(c, "eth_getCode", [a, "latest"])
                nn = rpc(c, "eth_getTransactionCount", [a, "latest"])
                srcs[a] = {"code_len": (len(cc) - 2) // 2 if isinstance(cc, str) else None, "nonce": int(nn, 16) if isinstance(nn, str) else None}
            out["sources"] = srcs
        # Polymarket Safe factory: computeProxyAddress(owner)
        sel = keccak(b"computeProxyAddress(address)")[:4].hex()
        r = rpc(c, "eth_call", [{"to": SAFE_FACTORY, "data": "0x" + sel + "0" * 24 + OWNER[2:]}, "latest"])
        out["safe_factory_code_len"] = (len(rpc(c, "eth_getCode", [SAFE_FACTORY, "latest"])) - 2) // 2
        if isinstance(r, str) and len(r) >= 66:
            safe = "0x" + r[-40:]
            out["owner_safe"] = safe
            cc = rpc(c, "eth_getCode", [safe, "latest"])
            out["owner_safe_code_len"] = (len(cc) - 2) // 2 if isinstance(cc, str) else cc
        else:
            out["owner_safe"] = r
    # data-api activity (cached client; only rows before H are counted)
    from polyrea.adapters.http import shared_client
    h = shared_client()
    acts = {}
    for name, addr in (("owner_eoa", OWNER), ("owner_safe", out.get("owner_safe"))):
        if not isinstance(addr, str) or not addr.startswith("0x"):
            continue
        try:
            d, _ = h.get_json("https://data-api.polymarket.com/activity", {"user": addr, "limit": 100, "end": H - 1}, adapter="polymarket.data", max_age=None)
            rows = d if isinstance(d, list) else []
            rows = [x for x in rows if int(x.get("timestamp", 0)) < H]
            acts[name] = {"rows_before_H_first_page": len(rows), "types": sorted({x.get("type") for x in rows}),
                          "first_ts": min((int(x["timestamp"]) for x in rows), default=None)}
        except Exception as e:  # noqa: BLE001
            acts[name] = {"error": str(e)[:200]}
    out["activity"] = acts
    (RES / "lineage.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
