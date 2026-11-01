"""Iteration 11 (X101): extend the in-block execution-order fetch from the pre-registered sample to every lot BTC 5m
cluster maker BUY fill (same method as code11/inblock_fetch.py; blocks already fetched are skipped). Writes
it11/inblock_all_sample.parquet (every fill, split label) and it11/inblock_blocks_all.parquet.
    python code11/inblock_fetch_all.py
"""
import json
import time
from pathlib import Path
import httpx
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
OUT = C / "it11"
RPCS = ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]
SPLIT_V = 1793059200


def main():
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    F = F[(F.role == "maker") & (F.side == "BUY") & F.cid.isin(set(W.cid))].copy()
    F["txh"] = F.txh.str.lower()
    F["split"] = np.where(F.ts >= SPLIT_V, "validate", "study")
    blk = pd.concat([pd.read_parquet(C / f"b1_cluster_orders_{s}.parquet", columns=["tx", "block"]) for s in ("study", "valid")])
    blk["tx"] = blk.tx.str.lower()
    F["block"] = F.txh.map(dict(zip(blk.tx, blk.block)))
    F.to_parquet(OUT / "inblock_all_sample.parquet")
    have = pd.read_parquet(OUT / "inblock_blocks.parquet")
    done = set(have.block.unique())
    blocks = sorted(set(int(b) for b in F.block.dropna()) - done)
    print("fills", len(F), "with block", int(F.block.notna().sum()), "blocks to fetch", len(blocks), flush=True)
    rows, fails = [], 0
    cl = httpx.Client(timeout=40)
    t0 = time.time()
    for i in range(0, len(blocks), 20):
        part = blocks[i:i + 20]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getBlockByNumber", "params": [hex(b), False]} for j, b in enumerate(part)]
        res = None
        for attempt in range(6):
            try:
                r = cl.post(RPCS[attempt % 2], json=body)
                if r.status_code == 429:
                    time.sleep(2 + 2 * attempt)
                    continue
                r.raise_for_status()
                res = r.json()
                if isinstance(res, list) and all(isinstance(x, dict) and x.get("result") for x in res):
                    break
                res = None
                time.sleep(1 + attempt)
            except Exception:  # noqa
                time.sleep(1 + attempt)
        if res is None:
            fails += len(part)
            continue
        for x in res:
            b = part[x["id"]]
            ts = int(x["result"]["timestamp"], 16)
            for k, h in enumerate(x["result"].get("transactions", [])):
                rows.append((b, ts, h.lower(), k))
        if (i // 20) % 100 == 0:
            print(i + len(part), "blocks", fails, "fails", round(time.time() - t0), "s", flush=True)
        time.sleep(0.25)
    D = pd.concat([have, pd.DataFrame(rows, columns=["block", "bts", "h", "pos"])], ignore_index=True)
    D.to_parquet(OUT / "inblock_blocks_all.parquet")
    json.dump({"blocks_fetched": len(blocks), "rows": len(D), "fails": fails, "secs": round(time.time() - t0)}, open(OUT / "inblock_all_status.json", "w"))
    print("saved", len(D), "fails", fails, flush=True)


if __name__ == "__main__":
    main()
