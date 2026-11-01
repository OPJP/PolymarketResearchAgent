"""Iteration 8 (Q2, the Dota input): does any public taker co-sign the wallet's Dota 2 takes at a fixed lag, as the six
subscribers do in CS2? The wallet's Dota markets of 10-22 (development): every public taker transaction of the in-play
window decoded (eth_getTransactionByHash, decoded fields only, .cache/re/tommy-cs2-maker/dota_pub/), then same-token BUY
taker orders of other wallets within +-1,000 ms of each of the wallet's Dota takes, per wallet, against a 30-s shift
null. Output: results/dota_cosign.json
"""
from __future__ import annotations

import json
import sys
import time
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
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
H = 1792713600


def main():
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    ca = pd.read_parquet(OUT / "calldata_all.parquet")
    ca["maker"] = ca.maker.str.lower()
    dc = set(ud.cid)
    wt = ca[(ca.maker == W) & (ca.idx == -1) & ca.cid.isin(dc)].drop_duplicates("tx")
    mk = ud[ud.cid.isin(set(wt.cid))]
    pm = PolymarketData()
    txs = set()
    for r in mk.itertuples():
        x, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 600, end=int(min(r.gs_ts + 5 * 3600, H - 1)), taker_only=True)
        txs |= {t["transactionHash"] for t in x}
    txs -= set(ca.tx)
    od = OUT / "dota_pub"
    od.mkdir(exist_ok=True)
    done = set()
    for p in od.glob("part_*.parquet"):
        done |= set(pd.read_parquet(p, columns=["tx"]).tx)
    todo = sorted(txs - done)
    print("wallet dota takes", len(wt), "markets", len(mk), "public txs", len(txs), "todo", len(todo), flush=True)
    cli = httpx.Client(timeout=40, headers={"User-Agent": "polyrea-research"})
    buf = []
    k = len(list(od.glob("part_*.parquet")))
    for i in range(0, len(todo), 40):
        part = todo[i:i + 40]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)]
        res = None
        for attempt in range(8):
            try:
                rr = cli.post("https://polygon-bor-rpc.publicnode.com", json=body)
                if rr.status_code == 429:
                    time.sleep(3 + 3 * attempt)
                    continue
                res = rr.json()
                if isinstance(res, list):
                    break
            except Exception:  # noqa: BLE001
                time.sleep(3 + 3 * attempt)
        for x in res or []:
            t = x.get("result") if isinstance(x, dict) else None
            if t:
                buf += rows_of(t)
        time.sleep(0.25)
    if buf:
        pd.DataFrame(buf).astype({"salt": str, "token_id": str}).to_parquet(od / f"part_{k}.parquet", index=False)
    D = pd.concat([pd.read_parquet(p) for p in od.glob("part_*.parquet")]) if list(od.glob("part_*.parquet")) else pd.DataFrame()
    D["maker"] = D.maker.str.lower()
    T = D[(D.idx == -1) & (D.side == 0) & (D.sign_ms > 1.79e12) & (D.sign_ms < H * 1000) & (D.maker != W)]
    g = {kk: v for kk, v in T.groupby("token_id")}
    rng = np.random.default_rng(6)
    lags, who = [], []
    nul = {}
    for r in wt.itertuples():
        x = g.get(str(r.token_id))
        if x is None:
            continue
        d = x.sign_ms.to_numpy(float) - r.sign_ms
        m = np.abs(d) <= 1000
        lags += list(d[m])
        who += list(x.maker.to_numpy()[m])
    for _ in range(50):
        for r in wt.itertuples():
            x = g.get(str(r.token_id))
            if x is None:
                continue
            d = x.sign_ms.to_numpy(float) - (r.sign_ms + rng.choice([-1, 1]) * 30000)
            m = np.abs(d) <= 1000
            for w_ in x.maker.to_numpy()[m]:
                nul[w_] = nul.get(w_, 0) + 1 / 50
    L = pd.DataFrame({"lag": lags, "who": who})
    res = {"wallet_dota_takes": int(len(wt)), "public_taker_buys": int(len(T)), "cosigns_within_1s": int(len(L)),
           "null_cosigns_within_1s": round(float(sum(nul.values())), 2),
           "hist_200ms": np.histogram(L.lag, bins=np.arange(-1000, 1001, 200))[0].tolist() if len(L) else None}
    if len(L):
        top = L.who.value_counts().head(8)
        res["top_cosigners"] = {w_: {"n": int(n), "null": round(float(nul.get(w_, 0)), 2), "median_lag_ms": round(float(L[L.who == w_].lag.median()), 1),
                                     "iqr_ms": round(float(np.subtract(*np.percentile(L[L.who == w_].lag, [75, 25]))), 1)} for w_, n in top.items()}
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "dota_cosign.json", "w"), indent=1)


if __name__ == "__main__":
    main()
