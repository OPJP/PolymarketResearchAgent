"""Iteration 6, X79 step 4 follow-up (C1 / C8): who runs the 100-share ladders with the 1.5-s re-post timer in markets the
wallet never trades? Development-start units only (10-31 12-18 block; cooldown_pairs_dev.parquet lists them).

For the four untraded markets with the most 100-share timer pairs: their public trades (data-api, takerOnly=false) up to
the end of the block, the matched-order calldata of every transaction (publicnode, batches of 40), and the makers whose
orders are exactly 100 shares at whole cents: maker, signature type, share of BUY orders, number of orders, and whether
the maker is the wallet. Output: results/timer_owner.json (aggregates only).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from fetch_calldata import rows_of  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
BLOCK_END = 1793469600  # 10-31 18:00 UTC


def main():
    R = pd.read_parquet(OUT / "cooldown_pairs_dev.parquet")
    x = R[(~R.traded) & (R["size"] == 100.0)]
    top = x.groupby(["cid", "slug"]).spike.sum().sort_values(ascending=False).head(4)
    pm = PolymarketData()
    cli = httpx.Client(timeout=60)
    res = {"markets": {}}
    allm = []
    for (cid, slug), n in top.items():
        rows, _, _ = pm.market_trades(cid, start=BLOCK_END - 6 * 3600, end=BLOCK_END - 1, taker_only=False)
        txs = sorted({r["transactionHash"] for r in rows if r.get("transactionHash")})
        recs = []
        for i in range(0, len(txs), 40):
            body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(txs[i:i + 40])]
            try:
                for t in cli.post("https://polygon-bor-rpc.publicnode.com", json=body).json():
                    if t.get("result"):
                        recs += rows_of(t["result"])
            except Exception as e:  # noqa: BLE001
                print("rpc", type(e).__name__, flush=True)
        D = pd.DataFrame(recs)
        if D.empty:
            continue
        D = D[D.idx >= 0]
        whole = (np.abs(D.price * 100 - np.round(D.price * 100)) < 1e-6)
        d100 = D[(D.shares.round(2) == 100.0) & whole].drop_duplicates(["maker", "salt"])
        g = d100.groupby("maker").agg(orders=("salt", "size"), buy_share=("side", lambda s: float((s == 0).mean())),
                                       sig=("sig_type", lambda s: int(s.mode().iloc[0]))).sort_values("orders", ascending=False).head(5)
        res["markets"][slug] = {"timer_pairs_100": int(n), "txs": len(txs), "maker_orders_100_whole": int(len(d100)),
                                "top_makers": {m: {"orders": int(r.orders), "buy_share": round(r.buy_share, 2), "sig_type": int(r.sig),
                                                   "is_wallet": m.lower() == WALLET} for m, r in g.iterrows()}}
        allm.append(d100.assign(slug=slug))
        print(slug, len(txs), len(d100), flush=True)
    if allm:
        A = pd.concat(allm)
        tot = A.groupby("maker").agg(orders=("salt", "size"), markets=("slug", "nunique")).sort_values("orders", ascending=False).head(8)
        res["across_markets"] = {m: {"orders": int(r.orders), "markets": int(r.markets)} for m, r in tot.iterrows()}
    (RES / "timer_owner.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
