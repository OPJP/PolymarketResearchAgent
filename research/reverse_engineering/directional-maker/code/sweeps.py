"""Where in the book is the cluster's resting bid when a taker hits it?

For a sample of BUILD transactions that filled a cluster maker order on a BTC 5m
window, fetch the receipt (all OrderFilled of the match) and express every
maker fill as an implied bid on the cluster order's token: a maker BUY of the
same token at p is a bid at p; a maker SELL of the complement token at q is a
bid at 1-q (merge match); a maker BUY of the complement is not in the same
queue (skip). Compares the cluster's price with the best price in the sweep.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.chain import decode_fills  # noqa: E402
from polyrea.adapters.http import HttpError, shared_client  # noqa: E402

OUT = ROOT / ".cache/re/directional-maker"
RPC = "https://polygon-bor-rpc.publicnode.com"
EX = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"}
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
http = shared_client()


def receipts(txs, batch=8):
    out = {}
    for i in range(0, len(txs), batch):
        part = txs[i:i + batch]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionReceipt", "params": [h]} for j, h in enumerate(part)]
        for attempt in range(4):
            try:
                res, _ = http.post_json(RPC, body, adapter="polygon.rpc.receipts", max_age=None, max_retries=2)
                break
            except HttpError:
                time.sleep(2 + 2 * attempt)
                res = None
        for r in res or []:
            if isinstance(r, dict) and r.get("result"):
                out[part[r["id"]]] = r["result"]
    return out


def main(lo, hi, n=800, seed=1):
    mk = pd.read_parquet(OUT / f"mk5_{lo}_{hi}.parquet")
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    comp = dict(zip(w["up_token"], w["down_token"])) | dict(zip(w["down_token"], w["up_token"]))
    txs = mk["tx"].drop_duplicates().sample(n=min(n, mk["tx"].nunique()), random_state=seed).tolist()
    rc = receipts(txs)
    rows = []
    for tx in txs:
        r = rc.get(tx)
        if not r:
            continue
        fills = decode_fills(r)
        mine = [f for f in fills if f.maker in CLUSTER and f.taker not in EX]
        if not mine:
            continue
        tok = mine[0].token_id
        ctok = comp.get(tok)
        bids = []
        for f in fills:
            if f.taker in EX:  # the taker's own order
                continue
            if f.token_id == tok and f.side == "BUY":
                bids.append((f.price, f.shares, f.maker in CLUSTER, f.maker))
            elif f.token_id == ctok and f.side == "SELL":
                bids.append((1 - f.price, f.shares, f.maker in CLUSTER, f.maker))
        if not bids:
            continue
        best = max(b[0] for b in bids)
        worst = min(b[0] for b in bids)
        myp = mine[0].price
        taker = [f for f in fills if f.taker in EX]
        rows.append({"tx": tx, "my_price": round(myp, 4), "best": round(best, 4), "worst": round(worst, 4),
                     "n_makers": len({b[3] for b in bids}), "n_levels": len({round(b[0], 4) for b in bids}),
                     "my_at_best": abs(myp - best) < 1e-6, "my_at_worst": abs(myp - worst) < 1e-6,
                     "share_cluster": sum(b[1] for b in bids if b[2]) / sum(b[1] for b in bids),
                     "taker_side": taker[0].side if taker else None, "taker_same_token": (taker[0].token_id == tok) if taker else None})
    d = pd.DataFrame(rows)
    print("sampled txs", len(txs), "decoded", len(d))
    print("cluster at best price of the sweep", round(d["my_at_best"].mean(), 3), "at worst", round(d["my_at_worst"].mean(), 3))
    print("levels in sweep q", np.quantile(d["n_levels"], [0.5, 0.75, 0.9]), "makers in sweep q", np.quantile(d["n_makers"], [0.5, 0.75, 0.9]))
    print("best - my price (cents) q", np.round(np.quantile((d["best"] - d["my_price"]) * 100, [0.5, 0.75, 0.9, 0.95]), 2))
    print("cluster share of the hit volume q", np.round(np.quantile(d["share_cluster"], [0.1, 0.5, 0.9]), 3))
    print("taker order: same token SELL", round(((d["taker_side"] == "SELL") & d["taker_same_token"]).mean(), 3),
          "complement BUY", round(((d["taker_side"] == "BUY") & ~d["taker_same_token"].astype(bool)).mean(), 3))
    d.to_parquet(OUT / f"sweeps_{lo}_{hi}.parquet", index=False)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 800)
