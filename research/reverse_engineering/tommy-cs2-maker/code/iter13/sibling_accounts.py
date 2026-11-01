"""X176 steps 1, 4 (mechanics panel iter-12 P1): the operator's 5-share accounts found by the same-process census.
(1) Chain state at `latest` (eth_getCode / eth_getTransactionCount on publicnode, read-only, not tied to any market
unit) of the deposit wallets and their recovered owner keys: EIP-7702 designator (0xef0100 + delegate) or proxy layout.
(4) Their data-api activity clamped to before H (titles, markets, dates, sizes, MERGE rows), to see whether any of them
traded outside the wallet's universe (a second window on the same process).
Output: results/sibling_accounts.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
H = 1792713600
RPC = "https://polygon-bor-rpc.publicnode.com"
ACC = {"0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14": "0x80a19b874ed5e7e4e931fea8410e35e9fec1b460",
       "0x52661b8e13158f23d94a9e8302ab0295704c22ac": "0xe6f64514da23906bacb209f81de6e1d13db51955",
       "0x671190333b064b0899b4ac1aec86744b1f82885b": None}
EXTRA = ["0x8af810f0e236cae55588ea6a084013c24122fd4f", "0x116342d6"]


def rpc(c, method, params):
    for _ in range(3):
        try:
            r = c.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=20).json()
            return r.get("result")
        except Exception:  # noqa: BLE001
            time.sleep(1.5)
    return None


def main():
    out = {"chain_state": {}, "activity": {}}
    with httpx.Client() as c:
        addrs = list(ACC) + [o for o in ACC.values() if o] + [EXTRA[0]]
        for a in addrs:
            code = rpc(c, "eth_getCode", [a, "latest"]) or ""
            nonce = rpc(c, "eth_getTransactionCount", [a, "latest"])
            info = {"code_bytes": (len(code) - 2) // 2 if code else 0, "nonce": int(nonce, 16) if nonce else None}
            if code.startswith("0xef0100"):
                info["eip7702_delegate"] = "0x" + code[8:48]
            elif code:
                info["code_head"] = code[:24]
                # immutable-args proxies carry 20-byte addresses in the tail
                info["code_tail_addrs"] = ["0x" + code[i:i + 40] for i in range(len(code) - 40 * 2, len(code), 40) if i > 2][:3]
            out["chain_state"][a] = info
            time.sleep(0.4)
    pm = PolymarketData()
    for a in ACC:
        rows, *_ = pm.activity(a, 1781000000, H - 1)
        df = pd.DataFrame(rows)
        if not len(df):
            out["activity"][a] = {"rows": 0}
            continue
        df["day"] = pd.to_datetime(df.timestamp, unit="s").dt.strftime("%m-%d")
        rec = {"rows": int(len(df)), "types": df["type"].value_counts().to_dict(), "days": df.groupby("day").size().to_dict(),
               "first": int(df.timestamp.min()), "last": int(df.timestamp.max())}
        if "slug" in df:
            ev = df["eventSlug"] if "eventSlug" in df else df["slug"]
            rec["titles"] = ev.astype(str).str.split("-").str[0].value_counts().to_dict()
            rec["events"] = ev.astype(str).value_counts().head(12).to_dict()
        tr = df[df["type"] == "TRADE"]
        if len(tr):
            rec["trade_sides"] = tr["side"].value_counts().to_dict()
            rec["trade_sizes"] = tr["size"].astype(float).round(1).value_counts().head(5).to_dict()
        out["activity"][a] = rec
    (RES / "sibling_accounts.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
