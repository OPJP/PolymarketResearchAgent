"""Iteration 11 (information panel I10-1 = X101, price part): the in-block transaction order as a recording-free match
clock for the price anchor.

Pre-registered sample (written before any in-block number is read): seed 1101; 3,000 VALIDATE (10-27..30) and 1,500
STUDY (10-23..26) cluster maker BUY fills in BTC 5m windows, drawn uniformly from fills_holdout. For each sampled fill
the block of its transaction (b1_cluster_orders_* 'block') is fetched with eth_getBlockByNumber(block, false), which
lists the block's transaction hashes in execution order. Writes it11/inblock_blocks.parquet (block, tx hash, index).
    python code11/inblock_fetch.py
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
SEED = 1101
N_VAL, N_STUDY = 3000, 1500
BATCH, PAUSE = 20, 0.3


def main():
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    F = F[(F.role == "maker") & (F.side == "BUY") & F.cid.isin(set(W.cid))].copy()
    F["txh"] = F.txh.str.lower()
    rng = np.random.default_rng(SEED)
    sv = F[F.ts >= SPLIT_V]
    ss = F[F.ts < SPLIT_V]
    samp = pd.concat([sv.iloc[np.sort(rng.choice(len(sv), N_VAL, replace=False))].assign(split="validate"),
                      ss.iloc[np.sort(rng.choice(len(ss), N_STUDY, replace=False))].assign(split="study")])
    blk = pd.concat([pd.read_parquet(C / f"b1_cluster_orders_{s}.parquet", columns=["tx", "block"]) for s in ("study", "valid")])
    blk["tx"] = blk.tx.str.lower()
    b_of = dict(zip(blk.tx, blk.block))
    samp["block"] = samp.txh.map(b_of)
    samp.to_parquet(OUT / "inblock_sample.parquet")
    blocks = sorted(set(int(b) for b in samp.block.dropna()))
    print("sample", len(samp), "with block", int(samp.block.notna().sum()), "blocks", len(blocks), flush=True)
    rows, fails = [], 0
    cl = httpx.Client(timeout=40)
    t0 = time.time()
    for i in range(0, len(blocks), BATCH):
        part = blocks[i:i + BATCH]
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
            txs = x["result"].get("transactions", [])
            ts = int(x["result"]["timestamp"], 16)
            for k, h in enumerate(txs):
                rows.append((b, ts, h.lower(), k))
        if (i // BATCH) % 25 == 0:
            print(i + len(part), "blocks", len(rows), "rows", fails, "fails", round(time.time() - t0), "s", flush=True)
        time.sleep(PAUSE)
    D = pd.DataFrame(rows, columns=["block", "bts", "h", "pos"])
    D.to_parquet(OUT / "inblock_blocks.parquet")
    json.dump({"blocks": len(blocks), "rows": len(D), "fails": fails, "secs": round(time.time() - t0)}, open(OUT / "inblock_fetch_status.json", "w"))
    print("saved", len(D), "fails", fails, flush=True)


if __name__ == "__main__":
    main()
