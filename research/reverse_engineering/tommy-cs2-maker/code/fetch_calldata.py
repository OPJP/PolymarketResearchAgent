"""B1: fetch eth_getTransactionByHash for every transaction with a wallet fill and keep only decoded fields.

Input: the on-chain OrderFilled table (topic2 = wallet), development blocks only (all before H).
Outputs (.cache/re/tommy-cs2-maker/calldata/):
  part_<k>.parquet   one row per order in each transaction (idx -1 = the taker order):
                     tx, block, idx, maker, side, token_id, price, shares (full original size), sign_ms,
                     sig_type, builder, metadata, salt, fill (in shares), fee, n_makers, condition_id
Raw inputs are never stored (no HTTP cache: plain httpx, ~2.7 KB per tx).
Usage: fetch_calldata.py FILLS_PARQUET [BATCH] [OUTDIR]  (FILLS_PARQUET needs columns tx, bts)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calldata import decode_match_orders  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
H = 1792713600
OUT = ROOT / ".cache/re/tommy-cs2-maker/calldata"
RPCS = ["https://polygon-bor-rpc.publicnode.com"]  # drpc free plan rejects batches > 3


def rows_of(t: dict) -> list[dict]:
    d = decode_match_orders(t.get("input", ""))
    blk = int(t["blockNumber"], 16)
    if d is None:
        return [{"tx": t["hash"], "block": blk, "idx": -9, "maker": t.get("to", ""), "side": -1}]
    out = []
    tk = d["taker"]
    allo = [(-1, tk, d["taker_fill"], d["taker_fee"])] + [
        (k, o, d["maker_fills"][k] if k < len(d["maker_fills"]) else float("nan"),
         d["maker_fees"][k] if k < len(d["maker_fees"]) else float("nan")) for k, o in enumerate(d["makers"])]
    for k, o, fill, fee in allo:
        # fill amounts are in the order's makerAmount units: USDC for a BUY, shares for a SELL
        fill_sh = fill / o["price"] if (o["side"] == 0 and o["price"] and o["price"] == o["price"]) else fill
        out.append({"tx": t["hash"], "block": blk, "idx": k, "maker": o["maker"], "side": o["side"],
                    "token_id": o["token_id"], "price": o["price"], "shares": o["shares"], "sign_ms": o["sign_ms"],
                    "sig_type": o["sig_type"], "builder": o["builder"], "metadata": o["metadata"], "salt": o["salt"],
                    "fill": fill_sh, "fee": fee, "n_makers": len(d["makers"]), "condition_id": d["condition_id"]})
    return out


def main(fills_path: str, batch: int = 40, outdir: str | None = None) -> None:
    global OUT
    if outdir:
        OUT = ROOT / ".cache/re/tommy-cs2-maker" / outdir
    OUT.mkdir(parents=True, exist_ok=True)
    f = pd.read_parquet(fills_path, columns=["tx", "bts"])
    f = f[f["bts"] < H]
    txs = list(dict.fromkeys(f.sort_values("bts")["tx"]))
    done = set()
    for p in OUT.glob("part_*.parquet"):
        done |= set(pd.read_parquet(p, columns=["tx"])["tx"])
    todo = [t for t in txs if t not in done]
    print("tx", len(txs), "done", len(done), "todo", len(todo), flush=True)
    k0 = len(list(OUT.glob("part_*.parquet")))
    buf, t0, nreq = [], time.time(), 0
    cli = httpx.Client(timeout=40, headers={"User-Agent": "polyrea-research"})
    i = 0
    while i < len(todo):
        part = todo[i: i + batch]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)]
        ok = False
        for attempt in range(10):
            rpc = RPCS[(nreq + attempt) % len(RPCS)]
            try:
                r = cli.post(rpc, json=body)
                nreq += 1
                if r.status_code == 429:
                    time.sleep(3 + 3 * attempt)
                    continue
                res = r.json()
                if isinstance(res, list) and len(res) == len(part) and all(isinstance(x, dict) and x.get("result") for x in res):
                    ok = True
                    break
                time.sleep(1 + attempt)
            except Exception as e:  # noqa: BLE001
                print("err", rpc, str(e)[:100], flush=True)
                time.sleep(2 + 2 * attempt)
        if not ok:
            print("batch failed at", i, flush=True)
            i += batch
            continue
        for x in res:
            buf.extend(rows_of(x["result"]))
        i += batch
        if len(buf) and (i // batch) % 50 == 0:
            pd.DataFrame(buf).to_parquet(OUT / f"part_{k0:04d}.parquet", index=False)
            k0 += 1
            buf = []
            print(i, f"{time.time()-t0:.0f}s", flush=True)
        time.sleep(0.15)
    if buf:
        pd.DataFrame(buf).to_parquet(OUT / f"part_{k0:04d}.parquet", index=False)
    print("done", f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], *(int(x) for x in a[1:2]), *(a[2:3]))
