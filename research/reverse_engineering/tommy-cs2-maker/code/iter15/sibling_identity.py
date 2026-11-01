"""X205 step 5 / mechanics critique 4: harden or refute the attribution of 0xd2bb9459 and 0x10d79cc7 to the operator.
For 16-22 Oct (development, before H): data-api activity of each account (TRADE rows), a sample of their trade txs
decoded (publicnode, signing ms), and 0-5 ms co-signing with the studied wallet's orders (orders.parquet, all its
filled orders of 16-22 Oct) on OTHER tokens: per-ms rate in 0-5 ms against 5-50 ms. Bar (X176): the operator's
known siblings 7.8-28.9x, every other account <= 4.5x. Also the design of their 16-22 Oct filled orders.
Output: results/sibling_identity.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grid_socket_clock as g1  # noqa: E402
import same_process_gate as S  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

RES = g1.RES
B0, H = 1792108800, 1792713600
ACCTS = {"0xd2bb9459": "0xd2bb94594762beda042e596598800d83f781bd8e", "0x10d79cc7": "0x10d79cc72df76ea3d6bdc2d54f41dbcbbb18bbf6",
         "0x7d67f01d": "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"}
NSAMP = 700


def main():
    pm = PolymarketData()
    o = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/orders.parquet", columns=["sign_ms", "token_id"])
    o = o[(o.sign_ms > 1.7e12) & (o.sign_ms / 1000 < H)]
    wms = np.sort(o.sign_ms.to_numpy(float))
    out = {"wallet_orders": int(len(wms))}
    rng = np.random.default_rng(0)
    for name, a in ACCTS.items():
        rows, _, _ = pm.activity(a, start=B0, end=H - 1)
        act = pd.DataFrame(rows)
        if act.empty:
            out[name] = {"activity": 0}
            continue
        tr = act[act["type"] == "TRADE"]
        txs = tr.transactionHash.dropna().unique()
        samp = rng.choice(txs, min(NSAMP, len(txs)), replace=False)
        cd = g1.decode(list(samp))
        c = cd[(cd.maker.str.lower() == a) & (cd.sign_ms > 1.7e12) & (cd.sign_ms / 1000 < H)].drop_duplicates(["salt", "sign_ms"])
        # restrict the wallet's orders to the sampled account's active hours (+-1 h) for a fair rate
        cs = S.cosign(c.sign_ms.to_numpy(float), None, wms, None)
        out[name] = {"activity_trades": int(len(tr)), "txs": int(len(txs)), "sampled_txs": int(len(samp)), "orders_decoded": int(len(c)),
                     "cosign_with_wallet": cs, "design": S.design(c) if len(c) else None,
                     "maker_share": round(float((c.idx >= 0).mean()), 3) if "idx" in c and len(c) else None}
        print(name, json.dumps(out[name]["cosign_with_wallet"]), out[name]["orders_decoded"], flush=True)
    (RES / "sibling_identity.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
