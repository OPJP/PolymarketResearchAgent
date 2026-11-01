"""R7-price (iteration 11; information panel I10-1 = X101, price part): a recording-free match clock for the price rule.

The R4 rule says the cluster's maker BUY limit = the last trade of the market before its fill (no cluster transaction)
minus 0.01. Live, "before" is the shared recorder's server match ms; historically and in blocks without recordings it is
the on-chain execution order: the last clean transaction of the same market earlier in the fill's own block
(eth_getBlockByNumber(block, false) lists the hashes in execution order), else the last clean print stamped before the
block second (R3's block-clock anchor). A clean transaction with several rows is priced at the taker's worst price
(max of the Up-mapped price when the taker pushes Up up, min otherwise). Point-in-time note: the earlier transaction was
matched, and broadcast on the CLOB market channel, before the fill's match; under the brief's block-stamp convention for
tape prints it would count as published at the block time, so evaluate() reports the block clock beside it.

Pre-registered and adopted on the historical VALIDATE (iteration 11, code11/inblock_score.py): BTC 5m 0.807 vs block clock
0.709 on a 3,000-fill sample (gain +0.098, 2-h block bootstrap [+0.078, +0.119]); BTC 15m 0.766 vs 0.666 (all 2,996 fills).
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

RPCS = ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]
OFFSET = 0.01
MAX_TXS = 60000


def _txint1(h: str) -> int:
    try:
        return int(str(h)[2:17], 16)
    except (TypeError, ValueError):
        return 0


def _rpc(cl, body):
    for attempt in range(6):
        try:
            r = cl.post(RPCS[attempt % len(RPCS)], json=body)
            if r.status_code == 429:
                time.sleep(2 + 2 * attempt)
                continue
            r.raise_for_status()
            res = r.json()
            if isinstance(res, list) and all(isinstance(x, dict) and x.get("result") for x in res):
                return res
            time.sleep(1 + attempt)
        except Exception:  # noqa: BLE001
            time.sleep(1 + attempt)
    return None


def fetch_positions(full_hashes: list[str]) -> tuple[dict, dict]:
    """full hash -> block number; (block, compact tx key) -> position in the block."""
    import httpx
    blk, pos = {}, {}
    hs = sorted(set(h for h in full_hashes if isinstance(h, str) and h.startswith("0x")))[:MAX_TXS]
    with httpx.Client(timeout=40) as cl:
        for i in range(0, len(hs), 25):
            part = hs[i:i + 25]
            res = _rpc(cl, [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)])
            if res:
                for x in res:
                    blk[part[x["id"]]] = int(x["result"]["blockNumber"], 16)
            time.sleep(0.25)
        blocks = sorted(set(blk.values()))
        for i in range(0, len(blocks), 20):
            part = blocks[i:i + 20]
            res = _rpc(cl, [{"jsonrpc": "2.0", "id": j, "method": "eth_getBlockByNumber", "params": [hex(b), False]} for j, b in enumerate(part)])
            if res:
                for x in res:
                    b = part[x["id"]]
                    for k, h in enumerate(x["result"].get("transactions", [])):
                        pos[(b, _txint1(h))] = k
            time.sleep(0.25)
    return blk, pos


def price_inblock(mk: pd.DataFrame, w: pd.DataFrame, clean: pd.DataFrame, txh_full: dict, names: dict, return_preds: bool = False):
    """mk: cluster maker BUY fills (wallet, tx = compact key, token_id, ts, price); clean: clean taker tape (compact tx);
    txh_full: compact key -> full hash. Returns within-a-tick shares on the in-block and block clocks, pooled and per
    wallet, plus the trivial anchor 'last print' (no offset) on the in-block clock."""
    empty = pd.DataFrame(columns=["tx", "token_id", "pred_block"])
    if mk is None or not len(mk) or clean is None or not len(clean):
        return ({"n_fills": 0}, empty) if return_preds else {"n_fills": 0}
    upset = set(w["up_token"].astype(str))
    tok2cid = {**dict(zip(w["up_token"].astype(str), w["cid"])), **dict(zip(w["down_token"].astype(str), w["cid"]))}
    f = mk.assign(c_=[tok2cid.get(str(t)) for t in mk["token_id"]])
    f = f[f["c_"].notna()]
    full = [txh_full.get(int(t)) for t in f["tx"]]
    blk, pos = fetch_positions([h for h in full if h])
    f = f.assign(fh=full)
    c2 = clean[clean["cid"].astype(str).isin(set(f["c_"].astype(str)))].copy()
    c2["up_token"] = c2["cid"].astype(str).map(dict(zip(w["cid"].astype(str), w["up_token"].astype(str))))
    c2["isu"] = c2["asset"].astype(str).to_numpy() == c2["up_token"].astype(str).to_numpy()
    c2["up_px"] = np.where(c2["isu"], c2["price"].astype(float), 1 - c2["price"].astype(float))
    c2["push_up"] = (c2["side"].astype(str).to_numpy() == "BUY") == c2["isu"].to_numpy()
    groups = {c: g.sort_values("ts", kind="stable") for c, g in c2.groupby(c2["cid"].astype(str))}
    rows = []
    for r in f.itertuples(index=False):
        g = groups.get(str(r.c_))
        if g is None:
            continue
        ts_ = g["ts"].to_numpy()
        pu = g["up_px"].to_numpy()
        b = int(r.ts)
        isup = str(r.token_id) in upset
        i = np.searchsorted(ts_, b, side="left") - 1
        if i < 0:
            continue
        a_block = pu[i] if isup else 1 - pu[i]
        a_in, src = a_block, "block"
        fb = blk.get(r.fh) if r.fh else None
        cpos = pos.get((fb, int(r.tx))) if fb is not None else None
        if cpos is not None:
            j0, j1 = np.searchsorted(ts_, b, side="left"), np.searchsorted(ts_, b, side="right")
            if j1 > j0:
                same = g.iloc[j0:j1]
                p = np.array([pos.get((fb, int(t)), -1) for t in same["tx"]])
                okp = (p >= 0) & (p < cpos)
                if okp.any():
                    last_tx = same["tx"].to_numpy()[okp][np.argmax(p[okp])]
                    tr = same[same["tx"].to_numpy() == last_tx]
                    worst = tr["up_px"].max() if bool(tr["push_up"].iloc[0]) else tr["up_px"].min()
                    a_in, src = (worst if isup else 1 - worst), "inblock"
        rows.append((r.wallet, float(r.price), a_block, a_in, src, cpos is not None, r.fh, str(r.token_id)))
    if not rows:
        return ({"n_fills": 0}, empty) if return_preds else {"n_fills": 0}
    D = pd.DataFrame(rows, columns=["wallet", "price", "a_block", "a_in", "src", "found", "fh", "token_id"])
    wi = np.abs(D["price"] - np.round(D["a_in"] - OFFSET, 2)) <= 0.0105
    wb = np.abs(D["price"] - np.round(D["a_block"] - OFFSET, 2)) <= 0.0105
    wl = np.abs(D["price"] - np.round(D["a_in"], 2)) <= 0.0105
    out = {"n_fills": int(len(D)), "within_0.01_inblock": float(wi.mean()), "within_0.01_block_clock": float(wb.mean()),
           "trivial_last_print_no_offset_inblock": float(wl.mean()), "inblock_anchor_share": float((D["src"] == "inblock").mean()),
           "fill_tx_position_found": float(D["found"].mean()), "per_wallet": {}}
    for addr, name in names.items():
        k = (D["wallet"] == addr).to_numpy()
        if k.any():
            out["per_wallet"][name] = {"within_0.01_inblock": float(wi[k].mean()), "within_0.01_block_clock": float(wb[k].mean()),
                                       "n": int(k.sum())}
    if return_preds:
        preds = pd.DataFrame({"tx": D["fh"].fillna("").astype(str), "token_id": D["token_id"], "pred_block": np.round(D["a_in"] - OFFSET, 2)})
        return out, preds
    return out
