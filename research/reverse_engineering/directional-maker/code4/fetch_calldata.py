"""Fetch + decode V2 calldata for every cluster fill tx of the released lot (10-23..10-31).
Writes chunked parquet to .cache/re/directional-maker/calldata/ (decoded fields only)."""
from __future__ import annotations
import sys, time
from pathlib import Path
import pandas as pd
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent))
import calldata as C

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker/calldata"
OUT.mkdir(parents=True, exist_ok=True)


def main(fills_path: str, tag: str, t0: int, t1: int, chunk: int = 2000):
    f = pd.read_parquet(fills_path, columns=["txh", "ts"])
    f = f[(f.ts >= t0) & (f.ts < t1)]
    hashes = f.sort_values("ts").txh.drop_duplicates().tolist()
    done = set()
    for p in OUT.glob(f"{tag}_*.parquet"):
        done |= set(pd.read_parquet(p, columns=["tx"]).tx.unique())
    hashes = [h for h in hashes if h not in done]
    print(tag, "to fetch", len(hashes), flush=True)
    cl = httpx.Client(timeout=30)
    rows, k, nbad = [], len(list(OUT.glob(f"{tag}_*.parquet"))), 0
    t_start = time.time()
    for n, (h, tx) in enumerate(C.fetch_txs(hashes, batch=25, pause=0.2, client=cl)):
        if tx is None:
            nbad += 1
            continue
        d = C.decode(tx.get("input", ""))
        blk = int(tx["blockNumber"], 16)
        if d is None:
            rows.append({"tx": h, "block": blk, "role": "undecoded", "sel": tx.get("input", "")[:10]})
        else:
            for i, o in enumerate([d["taker"]] + d["makers"]):
                r = dict(o)
                r.update(tx=h, block=blk, cond=d["condition_id"], role="taker" if i == 0 else "maker", idx=i,
                         taker_fill=d["taker_fill"] if i == 0 else None, frm=tx.get("from"))
                rows.append(r)
        if len(rows) >= chunk * 3 or n == len(hashes) - 1:
            df = pd.DataFrame(rows)
            for c in ("maker_amount", "taker_amount", "fill_amount", "fee_amount", "taker_fill", "sign_ms"):
                if c in df:
                    df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
            df.to_parquet(OUT / f"{tag}_{k:04d}.parquet")
            k += 1
            rows = []
            print(tag, n + 1, "txs", round(time.time() - t_start), "s bad", nbad, flush=True)
    if rows:
        df = pd.DataFrame(rows)
        for c in ("maker_amount", "taker_amount", "fill_amount", "fee_amount", "taker_fill", "sign_ms"):
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
        df.to_parquet(OUT / f"{tag}_{k:04d}.parquet")
    print(tag, "done bad", nbad, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
