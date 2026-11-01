"""Iteration 12, X118 (information I11-5) step 1 + 3: follow the 10-12 Monday sweep (development; blocks ~95,374,362-364,
iteration-9 assumptions panel) from each cluster proxy through its intermediate address to the final EOA with ERC-20
Transfer logs (any token), then query each final EOA's Polygon nonce / code and the public Hyperliquid info API (every
window ending before T0). Timestamps, addresses and counts only; amounts are not used.
    python code12/sweep_trace.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import HttpClient  # noqa: E402

RPC = "https://polygon.drpc.org"
HL = "https://api.hyperliquid.xyz/info"
T0_MS = 1793404800 * 1000
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
PROXIES = {"momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed"}
B0, B1 = 95374350, 95374420


def pad(a):
    return "0x" + "0" * 24 + a[2:].lower()


def main():
    h = HttpClient()

    def rpc(m, p):
        d, _ = h.post_json(RPC, {"jsonrpc": "2.0", "id": 1, "method": m, "params": p}, adapter="polygon.rpc")
        return d.get("result") if isinstance(d, dict) else None

    out = {}
    for name, p in PROXIES.items():
        hops = []
        cur = p
        seen = {p}
        for _ in range(4):
            logs = rpc("eth_getLogs", [{"fromBlock": hex(B0), "toBlock": hex(B1), "topics": [TRANSFER, pad(cur)]}]) or []
            tos = [("0x" + lg["topics"][2][-40:]) for lg in logs if len(lg.get("topics", [])) >= 3]
            tos = [t for t in dict.fromkeys(tos) if t not in seen and t != "0x" + "0" * 40]
            hops.append({"from": cur, "n_logs": len(logs), "to": tos[:5], "blocks": sorted({int(lg["blockNumber"], 16) for lg in logs})[:5],
                         "tokens": sorted({lg["address"] for lg in logs})[:5]})
            if not tos:
                break
            cur = tos[-1]
            seen.add(cur)
        final = cur
        info = {"polygon_nonce": int(rpc("eth_getTransactionCount", [final, "latest"]) or "0x0", 16),
                "code_len": len(rpc("eth_getCode", [final, "latest"]) or "")}
        try:
            role, _ = h.post_json(HL, {"type": "userRole", "user": final}, adapter="hyperliquid.info")
            fills, _ = h.post_json(HL, {"type": "userFillsByTime", "user": final, "startTime": T0_MS - 120 * 86400 * 1000, "endTime": T0_MS - 1},
                                   adapter="hyperliquid.info")
            led, _ = h.post_json(HL, {"type": "userNonFundingLedgerUpdates", "user": final, "startTime": T0_MS - 365 * 86400 * 1000, "endTime": T0_MS - 1},
                                 adapter="hyperliquid.info")
            info.update({"hl_role": role, "hl_fills_120d": len(fills) if isinstance(fills, list) else str(fills)[:80],
                         "hl_ledger_365d": len(led) if isinstance(led, list) else str(led)[:80]})
        except Exception as ex:  # noqa: BLE001
            info["hl_error"] = repr(ex)[:200]
        out[name] = {"hops": hops, "final": final, "final_info": info}
        print(name, final, info, [x["to"] for x in hops], flush=True)
    (Path(__file__).resolve().parent.parent / "results" / "iter12_sweep_trace.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
