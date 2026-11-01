"""B1 refresh for development-block units (iteration 3). Markets: dev_markets.parquet (only units whose
gameStartTime is in a development block >= T0). For each market in MODE ('wallet' = markets with wallet trades,
'all' = every dev-unit market): the public taker tape (data-api, taker_only) from gameStart - 1 h to now, and
the calldata of every taker transaction not decoded yet (publicnode, batches of 40). Appends to
.cache/re/tommy-cs2-maker/calldata_dev.parquet; tapes in tapes_dev/<cid>_tk.parquet. Raw inputs are not stored."""
import sys, time
from pathlib import Path
import httpx
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from polyrea.adapters.polymarket import PolymarketData  # noqa
from fetch_calldata import rows_of  # noqa
import sealed  # noqa
KEY = "tommy-cs2-maker"; OUT = ROOT / ".cache/re/tommy-cs2-maker"; RPC = "https://polygon-bor-rpc.publicnode.com"

def main(mode="wallet", max_tx=60000):
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    if mode == "wallet":
        m = m[m.wallet_trades > 0]
    pm = PolymarketData(); now = int(time.time())
    (OUT / "tapes_dev").mkdir(exist_ok=True)
    txs = []
    for cid, gs in zip(m.cid, m.gs):
        assert not sealed.is_sealed(int(gs), KEY)
        rows, _, cov = pm.market_trades(cid, start=int(gs) - 3600, end=now, taker_only=True, max_rows=100_000)
        df = pd.DataFrame(rows)
        if len(df):
            df = df[["proxyWallet", "side", "asset", "outcomeIndex", "size", "price", "timestamp", "transactionHash"]]
            df.to_parquet(OUT / "tapes_dev" / f"{cid}_tk.parquet", index=False)
            txs += df.transactionHash.tolist()
    w = pd.read_parquet(OUT / "dev_wallet_trades.parquet")
    txs = list(dict.fromkeys(w.transactionHash.tolist() + txs))
    p = OUT / "calldata_dev.parquet"
    prev = pd.read_parquet(p) if p.exists() else None
    old = set(prev.tx) if prev is not None else set()
    todo = [t for t in txs if t not in old][:max_tx]
    print("markets", len(m), "tx", len(txs), "todo", len(todo), flush=True)
    cli = httpx.Client(timeout=40, headers={"User-Agent": "polyrea-research"})
    buf = []
    for i in range(0, len(todo), 40):
        part = todo[i:i + 40]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)]
        for attempt in range(8):
            try:
                r = cli.post(RPC, json=body)
                if r.status_code == 429:
                    time.sleep(3 + 3 * attempt); continue
                res = r.json()
                if isinstance(res, list) and all(isinstance(x, dict) and x.get("result") for x in res):
                    for x in res:
                        buf.extend(rows_of(x["result"]))
                    break
            except Exception as e:  # noqa
                print("err", str(e)[:80], flush=True)
            time.sleep(1 + attempt)
        time.sleep(0.12)
        if (i // 40) % 50 == 0:
            print("batch", i // 40, "rows", len(buf), flush=True)
    d = pd.DataFrame(buf)
    if prev is not None:
        d = pd.concat([prev, d]) if len(d) else prev
    d.to_parquet(p, index=False)
    print("decoded rows", len(d), "txs", d.tx.nunique(), flush=True)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "wallet", int(sys.argv[2]) if len(sys.argv) > 2 else 60000)
