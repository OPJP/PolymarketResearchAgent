"""B1 for development-block units after T0: decode matchOrders calldata of (a) every wallet transaction in dev units
(activity_devblocks.parquet) and (b) every public taker transaction in the same markets (data-api taker tape since
gameStart - 1 h), so the wallet's and the pack's signing ms are known. Only units whose gameStartTime is in a development
block are touched (the activity file is already filtered). Output: .cache/re/tommy-cs2-maker/calldata_dev.parquet and
tapes_dev/<cid>_tk.parquet. Raw inputs are not stored."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from fetch_calldata import rows_of  # noqa: E402
import sealed  # noqa: E402

KEY = "tommy-cs2-maker"
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RPC = "https://polygon-bor-rpc.publicnode.com"


def main():
    a = pd.read_parquet(OUT / "activity_devblocks.parquet")
    a = a[a.type == "TRADE"]
    pm = PolymarketData()
    (OUT / "tapes_dev").mkdir(exist_ok=True)
    now = int(time.time())
    pub_tx = []
    for cid, gs in a.groupby("conditionId").gs.min().items():
        gs = int(gs)
        assert not sealed.is_sealed(gs, KEY)
        rows, _, cov = pm.market_trades(cid, start=gs - 3600, end=now, taker_only=True, max_rows=100_000)
        df = pd.DataFrame(rows)
        if len(df):
            df = df[["proxyWallet", "side", "asset", "outcomeIndex", "size", "price", "timestamp", "transactionHash"]]
            df.to_parquet(OUT / "tapes_dev" / f"{cid}_tk.parquet", index=False)
            pub_tx += df.transactionHash.tolist()
    txs = list(dict.fromkeys(a.transactionHash.tolist() + pub_tx))
    old = set()
    p = OUT / "calldata_dev.parquet"
    prev = pd.read_parquet(p) if p.exists() else None
    if prev is not None:
        old = set(prev.tx)
    todo = [t for t in txs if t not in old]
    print("tx", len(txs), "todo", len(todo), flush=True)
    cli = httpx.Client(timeout=40, headers={"User-Agent": "polyrea-research"})
    buf = []
    for i in range(0, len(todo), 40):
        part = todo[i:i + 40]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)]
        for attempt in range(8):
            try:
                r = cli.post(RPC, json=body)
                if r.status_code == 429:
                    time.sleep(3 + 3 * attempt)
                    continue
                res = r.json()
                if isinstance(res, list) and all(isinstance(x, dict) and x.get("result") for x in res):
                    for x in res:
                        buf.extend(rows_of(x["result"]))
                    break
            except Exception as e:  # noqa: BLE001
                print("err", str(e)[:80], flush=True)
            time.sleep(1 + attempt)
        time.sleep(0.15)
    d = pd.DataFrame(buf)
    if prev is not None:
        d = pd.concat([prev, d])
    d.to_parquet(p, index=False)
    print("decoded rows", len(d), "txs", d.tx.nunique() if len(d) else 0, flush=True)


if __name__ == "__main__":
    main()
