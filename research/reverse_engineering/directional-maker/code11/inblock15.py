"""Iteration 11 (X101, price part, BTC 15m): the R7-price in-block anchor on every lot BTC 15m cluster maker BUY fill
(same pre-registered criterion as BTC 5m). Step 1 eth_getTransactionByHash for each fill tx (blockNumber), step 2
eth_getBlockByNumber(block, false) for the execution order, step 3 score (STUDY per fill allowed, VALIDATE aggregate).
    python code11/inblock15.py
"""
import json
import time
from pathlib import Path
import httpx
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
RPCS = ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]
LOT = (1792713600, 1793404800)
SPLIT_V = 1793059200


def rpc_batch(cl, body):
    for attempt in range(6):
        try:
            r = cl.post(RPCS[attempt % 2], json=body)
            if r.status_code == 429:
                time.sleep(2 + 2 * attempt)
                continue
            r.raise_for_status()
            res = r.json()
            if isinstance(res, list) and all(isinstance(x, dict) and x.get("result") for x in res):
                return res
            time.sleep(1 + attempt)
        except Exception:  # noqa
            time.sleep(1 + attempt)
    return None


def main():
    F = pd.read_parquet(C / "p15" / "cluster_btc15m_fills.parquet")
    F = F[(F.ts >= LOT[0]) & (F.ts < LOT[1]) & (F.role == "maker") & (F.side == "BUY")].copy()
    F["txh"] = F.tx.astype(str).str.lower()
    cl = httpx.Client(timeout=40)
    hs = sorted(set(F.txh))
    blk = {}
    for i in range(0, len(hs), 25):
        part = hs[i:i + 25]
        res = rpc_batch(cl, [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)])
        if res:
            for x in res:
                blk[part[x["id"]]] = int(x["result"]["blockNumber"], 16)
        time.sleep(0.25)
    F["block"] = F.txh.map(blk)
    blocks = sorted(set(int(b) for b in F.block.dropna()))
    print("txs", len(hs), "with block", len(blk), "blocks", len(blocks), flush=True)
    rows = []
    for i in range(0, len(blocks), 20):
        part = blocks[i:i + 20]
        res = rpc_batch(cl, [{"jsonrpc": "2.0", "id": j, "method": "eth_getBlockByNumber", "params": [hex(b), False]} for j, b in enumerate(part)])
        if res:
            for x in res:
                for k, h in enumerate(x["result"].get("transactions", [])):
                    rows.append((part[x["id"]], h.lower(), k))
        time.sleep(0.3)
    BL = pd.DataFrame(rows, columns=["block", "h", "pos"])
    BL.to_parquet(C / "it11" / "inblock15_blocks.parquet")
    F.to_parquet(C / "it11" / "inblock15_sample.parquet")
    pos, blk_of = dict(zip(BL.h, BL.pos)), dict(zip(BL.h, BL.block))
    W = pd.read_parquet(C / "t15" / "windows_15m.parquet").set_index("cid")
    cl_tx = set(F.txh)
    for n in ("bosona", "almach", "momoney"):
        cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
    out_rows = []
    F["day"] = (F.ts // 86400 * 86400).astype(int)
    for day, sd in F.groupby("day"):
        T = pd.read_parquet(C / "t15" / f"taker15m_day_{day}.parquet", columns=["cid", "ts", "side", "asset", "price", "tx"])
        T["tx"] = T.tx.str.lower()
        T = T[T.cid.isin(set(sd.cid)) & ~T.tx.isin(cl_tx)]
        tg = {k: g for k, g in T.groupby("cid")}
        for r in sd.itertuples(index=False):
            if r.cid not in tg or r.cid not in W.index:
                continue
            up = str(W.at[r.cid, "up_token"])
            g = tg[r.cid]
            gts = g.ts.to_numpy()
            o = np.argsort(gts, kind="stable")
            gs = g.iloc[o]
            gts = gts[o]
            pu = np.where(gs.asset.astype(str).to_numpy() == up, gs.price.to_numpy(float), 1 - gs.price.to_numpy(float))
            isup = str(r.token_id) == up
            b = int(r.ts)
            i = np.searchsorted(gts, b, side="left") - 1
            if i < 0:
                continue
            a_block = pu[i] if isup else 1 - pu[i]
            a_in, src = a_block, "block"
            same = gs[gts == b]
            cpos = pos.get(r.txh)
            if cpos is not None and len(same):
                same = same.assign(p=[pos.get(h) for h in same.tx], bk=[blk_of.get(h) for h in same.tx])
                prev = same[same.p.notna() & (same.bk == blk_of.get(r.txh)) & (same.p < cpos)]
                if len(prev):
                    tr = prev[prev.tx == prev.loc[prev.p.idxmax(), "tx"]]
                    isu = tr.asset.astype(str).to_numpy() == up
                    tu = np.where(isu, tr.price.to_numpy(float), 1 - tr.price.to_numpy(float))
                    worst = tu.max() if ((tr.side.to_numpy()[0] == "BUY") == isu[0]) else tu.min()
                    a_in, src = (worst if isup else 1 - worst), "inblock"
            out_rows.append(dict(split="study" if b < SPLIT_V else "validate", b=b, price=float(r.price), a_block=a_block, a_in=a_in, src=src))
    D = pd.DataFrame(out_rows)
    D["w_block"] = np.abs(D.price - np.round(D.a_block - 0.01, 2)) <= 0.0105
    D["w_in"] = np.abs(D.price - np.round(D.a_in - 0.01, 2)) <= 0.0105
    out = {sp: {"fills": int(len(d)), "inblock_share": round(float((d.src == "inblock").mean()), 4),
                "block_clock_within_tick": round(float(d.w_block.mean()), 4), "inblock_within_tick": round(float(d.w_in.mean()), 4)}
           for sp, d in D.groupby("split")}
    (HERE.parent / "results" / "iter11_inblock_price_15m.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
