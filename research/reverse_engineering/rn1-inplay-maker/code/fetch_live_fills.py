"""RN1's fills and decoded orders in the post-T0 development blocks, restricted to development units.

1. OrderFilled logs (topic2 = RN1) for the block range of each development 6-h block.
2. Calldata of every transaction (ms signing times, limit prices, sizes, conditionId).
3. Gamma listing projection (gameStartTime, slug, sportsMarketType, secondsDelay, tokens) per conditionId,
   fetched with httpx (no shared cache) and projected at once (no post-hoc field is kept).
4. Only markets whose unit (gameStartTime) starts inside a development block are kept; every row of other
   units is dropped in memory before anything is written or counted.
Output: .cache/re/rn1-inplay-maker/live/fills_<a>.parquet, orders_<a>.parquet, units.parquet
Usage: python fetch_live_fills.py <block_start_ts> [<block_start_ts> ...]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sealed  # noqa: E402
from fetch_calldata import decode_match, fetch_batch  # noqa: E402
from polyrea.adapters.chain import ORDER_FILLED_V2, decode_fills  # noqa: E402

W = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
EXCHANGES = ["0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"]
RPC = "https://polygon-bor-rpc.publicnode.com"
OUT = ROOT / ".cache/re/rn1-inplay-maker/live"
OUT.mkdir(parents=True, exist_ok=True)
KEY = "rn1-inplay-maker"
LISTING = ["conditionId", "slug", "question", "sportsMarketType", "gameStartTime", "clobTokenIds", "secondsDelay",
           "negRisk", "rfqEnabled", "line", "feeSchedule", "rewardsMinSize", "rewardsMaxSpread", "startDate", "endDate"]
cli = httpx.Client(timeout=60)


def rpc(method, params):
    for attempt in range(8):
        try:
            r = cli.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
            js = r.json()
            if js.get("result") is not None:
                return js["result"]
        except Exception as e:  # noqa: BLE001
            print("rpc err", str(e)[:100], flush=True)
        time.sleep(2 + 2 * attempt)
    raise RuntimeError(method)


def block_ts(n):
    return int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)


def block_at(ts, lo, hi):
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid
        else:
            hi = mid
    return lo


def parse_ts(s):
    from datetime import datetime, timezone
    if not s:
        return None
    s = str(s).replace("Z", "+00:00").replace(" ", "T")
    if s.endswith("+00"):
        s += ":00"
    try:
        return int(datetime.fromisoformat(s).astimezone(timezone.utc).timestamp())
    except ValueError:
        return None


def gamma_projection(cids):
    out = {}
    cids = sorted(set(cids))
    for i in range(0, len(cids), 20):
        part = cids[i:i + 20]
        for closed in ("true", "false"):
            miss = [c for c in part if c not in out]
            if not miss:
                break
            params = [("condition_ids", c) for c in miss] + [("limit", 2 * len(miss))] + ([("closed", "true")] if closed == "true" else [])
            try:
                data = cli.get("https://gamma-api.polymarket.com/markets", params=params).json()
            except Exception:  # noqa: BLE001
                data = []
            for m in data or []:
                out[m.get("conditionId")] = {k: (json.dumps(m.get(k)) if isinstance(m.get(k), (list, dict)) else m.get(k)) for k in LISTING}
            time.sleep(0.3)
    return out


def main(blocks):
    latest = int(rpc("eth_blockNumber", []), 16)
    lt = block_ts(latest)
    wtopic = "0x" + W[2:].rjust(64, "0")
    st = sealed.load_state(KEY)
    for a in blocks:
        b = a + 6 * 3600
        if sealed.future_block_sealed(a):
            print("refusing sealed block", a)
            continue
        if (OUT / f"orders_{a}.parquet").exists():
            continue
        t0 = time.time()
        gs = latest - int((lt - a) / 1.5) - 30000
        ge = latest - int((lt - b) / 1.5) + 30000
        b0 = block_at(a, max(gs, 1), min(ge, latest)) + 1
        b1 = block_at(b, b0, min(ge + 30000, latest))
        logs = []
        for fb in range(b0, b1 + 1, 2000):
            tb = min(fb + 1999, b1)
            for lg in rpc("eth_getLogs", [{"fromBlock": hex(fb), "toBlock": hex(tb), "address": EXCHANGES,
                                            "topics": [ORDER_FILLED_V2, None, wtopic]}]):
                for fl in decode_fills({"transactionHash": lg["transactionHash"], "logs": [lg]}):
                    logs.append({"block": int(lg["blockNumber"], 16), "tx": fl.tx_hash, "log_index": fl.log_index,
                                 "order_hash": fl.order_hash, "taker": fl.taker, "side": fl.side, "token_id": fl.token_id,
                                 "shares": fl.shares, "usdc": fl.usdc, "fee": fl.fee,
                                 "role": "taker" if fl.taker in EXCHANGES else "maker"})
        fills = pd.DataFrame(logs)
        txs = sorted(set(fills["tx"])) if len(fills) else []
        orders = []
        for i in range(0, len(txs), 20):
            for r in fetch_batch(cli, txs[i:i + 20]):
                tx = r.get("result")
                if not tx:
                    continue
                d = decode_match(tx.get("input", ""))
                if d is None:
                    continue
                for o in d["orders"]:
                    o.update({"tx": tx["hash"], "block": int(tx["blockNumber"], 16), "cond": d["cond"]})
                    orders.append(o)
            time.sleep(0.4)
        od = pd.DataFrame(orders)
        # unit filter: keep only markets whose game starts in a development block
        proj = gamma_projection(od["cond"].unique()) if len(od) else {}
        units = pd.DataFrame([dict(v, conditionId=k) for k, v in proj.items()])
        units["gst"] = [parse_ts(x) for x in units["gameStartTime"]]
        units["unit_ts"] = [g if g is not None else parse_ts(s) for g, s in zip(units["gst"], units["startDate"])]
        units["dev_unit"] = [bool(u is not None and u >= sealed.T0 and not sealed.future_block_sealed(u)) for u in units["unit_ts"]]
        keep = set(units.loc[units["dev_unit"], "conditionId"])
        od = od[od["cond"].isin(keep)].copy()
        tx_keep = set(od["tx"])
        fills = fills[fills["tx"].isin(tx_keep)].copy()
        anchors = sorted(set(list(range(b0, b1 + 1, 300)) + [b1]))
        ats = [block_ts(x) for x in anchors]
        fills["ts"] = np.interp(fills["block"], anchors, ats)
        od["bts"] = np.interp(od["block"], anchors, ats)
        for c in ("salt",):
            od[c] = od[c].astype(str)
        for c in ("maker_amount", "taker_amount", "sign_ms", "fill", "fee"):
            od[c] = od[c].astype("float64")
        od.to_parquet(OUT / f"orders_{a}.parquet", index=False)
        fills.to_parquet(OUT / f"fills_{a}.parquet", index=False)
        units[units["dev_unit"]].drop(columns=["dev_unit"]).to_parquet(OUT / f"units_{a}.parquet", index=False)
        print(a, "blocks", b0, b1, "dev-unit fills", len(fills), "orders", len(od), "dev units", len(keep), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]])
