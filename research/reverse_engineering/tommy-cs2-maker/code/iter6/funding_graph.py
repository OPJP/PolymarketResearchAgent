"""Iteration 6, X74 (information panel iter5 P5, C1): funding graph of the wallet and the co-timed maker 0x51dbdd2b.

Polygon eth_getLogs (publicnode) of ERC-20 Transfer events of USDC.e (0x2791...; the collateral that V2 wraps into
0xc011a7e1..., verified on a MERGE receipt) and native USDC (0x3c49...) with the address as sender (topic1) or receiver
(topic2), blocks of 10-12 00:00 .. H (development period; block numbers interpolated from known fills). Transfers to or
from Polymarket contracts (CTF, the V2 collateral wrapper, the exchanges, the adapters seen on its MERGE receipts) are
set aside; the rest are external counterparties. Output: results/funding_graph.json (counterparties with counts and
USD, and the overlap between the two wallets' external counterparties).
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[5]
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
RPC = "https://polygon-bor-rpc.publicnode.com"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TOKENS = {"USDC.e": "0x2791bca1f2de4661ed88a30c99a7a9449aa84174", "USDC": "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"}
ADDR = {"wallet": "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2", "cosub_51dbdd2b": "0x51dbdd2b19427dc8e88bb15a4046a38d8427f9b3",
        "wallet_owner": "0x8af810f0e236cae55588ea6a084013c24122fd4f", "cosub_signer": "0xdecd4b4cb7e41b6824518b704161cb423833e780"}
PM = {"0x4d97dcd97ec945f40cf65f87097ace5ea0476045", "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb",
      "0xc417fd8e9661c0d2120b64a04bb3278c17e99db1", "0xe111180000d2663c0091e4f400237545b87b996b",
      "0xe2222d279d744050d28e00520010520000310f59", "0x0000000000000000000000000000000000000000",
      "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e", "0xc5d563a36ae78145c45a50134d48a1215220f80a",
      "0xd91e80cf2e7be2e162c6513ced06f1dd0da35296"}
# block anchors: (block, unix) from the wallet's fills (chain_fills) and dev-block calldata
B0, T0 = 95635089, 1792157970
B1, T1 = 96497334, 1793451451
RATE = (B1 - B0) / (T1 - T0)
START, END = 1791763200, 1792713600  # 10-12 00:00 .. H


def blk(t):
    return int(B0 + (t - T0) * RATE)


def pad(a):
    return "0x" + "0" * 24 + a[2:].lower()


def get_logs(c, token, topics, lo, hi, step=20000):
    out = []
    b = lo
    fails = 0
    while b <= hi:
        e = min(hi, b + step - 1)
        try:
            r = c.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
                                  "params": [{"address": token, "fromBlock": hex(b), "toBlock": hex(e), "topics": topics}]})
            j = r.json()
        except Exception:  # noqa: BLE001
            j = {"error": "exception"}
        if "error" in j:
            fails += 1
            if fails > 12:
                raise RuntimeError(f"getLogs failing at {b}: {j.get('error')}")
            step = max(1000, step // 2)
            time.sleep(min(5, fails))
            continue
        out.extend(j["result"])
        b = e + 1
        time.sleep(0.15)
    return out


def main():
    lo, hi = blk(START), blk(END)
    res = {"blocks": [lo, hi], "addresses": {}}
    ext = {}
    with httpx.Client(timeout=60) as c:
        for nm, a in ADDR.items():
            cp = defaultdict(lambda: {"in_n": 0, "in_usd": 0.0, "out_n": 0, "out_usd": 0.0})
            pm_tot = {"in_usd": 0.0, "out_usd": 0.0}
            for tn, tok in TOKENS.items():
                for direction, topics in (("out", [TRANSFER, pad(a)]), ("in", [TRANSFER, None, pad(a)])):
                    for l in get_logs(c, tok, topics, lo, hi):
                        frm = "0x" + l["topics"][1][-40:]
                        to = "0x" + l["topics"][2][-40:]
                        v = int(l["data"], 16) / 1e6
                        other = to if direction == "out" else frm
                        if other in PM:
                            pm_tot[f"{direction}_usd"] += v
                            continue
                        cp[other][f"{direction}_n"] += 1
                        cp[other][f"{direction}_usd"] += v
            top = sorted(cp.items(), key=lambda kv: -(kv[1]["in_usd"] + kv[1]["out_usd"]))[:15]
            res["addresses"][nm] = {"external_counterparties": len(cp), "polymarket_contract_flows": {k: round(v, 0) for k, v in pm_tot.items()},
                                    "top": {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in top}}
            ext[nm] = set(cp)
            print(nm, len(cp), flush=True)
    res["overlap_wallet_cosub"] = sorted((ext["wallet"] | ext["wallet_owner"]) & (ext["cosub_51dbdd2b"] | ext["cosub_signer"]))
    res["direct_links"] = {"wallet_side_has_cosub": bool({ADDR["cosub_51dbdd2b"], ADDR["cosub_signer"]} & (ext["wallet"] | ext["wallet_owner"])),
                           "cosub_side_has_wallet": bool({ADDR["wallet"], ADDR["wallet_owner"]} & (ext["cosub_51dbdd2b"] | ext["cosub_signer"]))}
    (RES / "funding_graph.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "addresses"}, indent=1))


if __name__ == "__main__":
    main()
