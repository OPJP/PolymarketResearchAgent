"""Iteration 12, X118 (information I11-5): the operator's other accounts. Safe getOwners() (selector 0xa0e67e2b) on each
cluster proxy via eth_call (Polygon, drpc), then for every owner EOA: Polygon nonce (transaction count), and the
public Hyperliquid info API (userRole, userFillsByTime and userNonFundingLedgerUpdates with every window ending before
2026-10-31 00:00 UTC). Development data only (nothing after T0). Writes results/iter12_owners.json.
    python code12/owners.py
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
PROXIES = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def rpc(h, method, params):
    d, _ = h.post_json(RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, adapter="polygon.rpc")
    return d.get("result") if isinstance(d, dict) else None


def main():
    h = HttpClient()
    out = {}
    for name, p in PROXIES.items():
        rec = {"proxy": p}
        code = rpc(h, "eth_getCode", [p, "latest"])
        rec["code_len"] = len(code or "")
        r = rpc(h, "eth_call", [{"to": p, "data": "0xa0e67e2b"}, "latest"])
        owners = []
        if r and len(r) > 130:
            b = r[2:]
            n = int(b[64:128], 16)
            for i in range(n):
                owners.append("0x" + b[128 + 64 * i + 24:128 + 64 * (i + 1)])
        rec["owners"] = owners
        th = rpc(h, "eth_call", [{"to": p, "data": "0xe75235b8"}, "latest"])  # getThreshold()
        rec["threshold"] = int(th, 16) if th and th != "0x" else None
        rec["owner_info"] = {}
        for o in owners:
            oi = {"polygon_nonce": int(rpc(h, "eth_getTransactionCount", [o, "latest"]) or "0x0", 16)}
            try:
                role, _ = h.post_json(HL, {"type": "userRole", "user": o}, adapter="hyperliquid.info")
                oi["hl_role"] = role
                fills, _ = h.post_json(HL, {"type": "userFillsByTime", "user": o, "startTime": T0_MS - 120 * 86400 * 1000,
                                            "endTime": T0_MS - 1}, adapter="hyperliquid.info")
                fills = fills if isinstance(fills, list) else []
                oi["hl_fills_120d_before_T0"] = len(fills)
                if fills:
                    oi["hl_first_last"] = [min(f["time"] for f in fills), max(f["time"] for f in fills)]
                    coins = {}
                    for f in fills:
                        coins[f.get("coin")] = coins.get(f.get("coin"), 0) + 1
                    oi["hl_coins"] = coins
                led, _ = h.post_json(HL, {"type": "userNonFundingLedgerUpdates", "user": o, "startTime": T0_MS - 365 * 86400 * 1000,
                                          "endTime": T0_MS - 1}, adapter="hyperliquid.info")
                led = led if isinstance(led, list) else []
                oi["hl_ledger_n"] = len(led)
                oi["hl_ledger_last"] = [(x.get("time"), (x.get("delta") or {}).get("type")) for x in led[-5:]]
            except Exception as e:  # noqa: BLE001
                oi["hl_error"] = str(e)[:200]
            rec["owner_info"][o] = oi
        out[name] = rec
        print(name, json.dumps(rec)[:600], flush=True)
    (Path(__file__).resolve().parent.parent / "results" / "iter12_owners.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
