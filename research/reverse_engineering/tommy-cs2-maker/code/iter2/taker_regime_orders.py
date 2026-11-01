"""Taker regime (10-01..10-15) at order level from V2 calldata (assumptions panel X16): roles, sides, sizes, limit vs
fill, in-play share, sign-to-block latency, compared with the maker regime's taker orders (16-22 Oct)."""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import OUT, RES, WALLET  # noqa: E402


def gs_map(mfile):
    m = json.load(open(OUT / mfile))
    out, tok = {}, {}
    for cid, x in m.items():
        g = str(x.get("gameStartTime") or "")
        if g.endswith("+00"):
            g += ":00"
        try:
            out[cid] = pd.Timestamp(g).timestamp()
        except Exception:  # noqa: BLE001
            out[cid] = np.nan
        t = x.get("clobTokenIds")
        t = json.loads(t) if isinstance(t, str) else (t or [])
        for i, z in enumerate(t):
            tok[str(z)] = (cid, i)
    return out, tok


def main():
    parts = sorted(glob.glob(str(OUT / "calldata_taker/*.parquet")))
    d = pd.concat([pd.read_parquet(p) for p in parts])
    gs, tok = gs_map("markets_taker.json")
    a = pd.read_parquet(OUT / "activity_taker.parquet", columns=["transactionHash", "timestamp"]).drop_duplicates("transactionHash")
    bts = dict(zip(a.transactionHash, a.timestamp.astype(int)))
    w = d[d.maker == WALLET].copy()
    w["cid"] = w.token_id.astype(str).map(lambda t: tok.get(t, (None, -1))[0])
    w["gs"] = w.cid.map(gs)
    w["bts"] = w.tx.map(bts)
    w["role"] = np.where(w.idx == -1, "taker", "maker")
    w = w[(w.sign_ms > 1.7e12) & (w.sign_ms < 1.8e12)]
    key = ["salt", "sign_ms", "token_id", "price", "shares", "side"]
    o = w.groupby(key, as_index=False).agg(role=("role", "first"), n_tx=("tx", "nunique"), filled=("fill", "sum"), gs=("gs", "first"), bts=("bts", "min"))
    res = {"txs": int(d.tx.nunique()), "wallet_rows": len(w), "orders": len(o), "role_share": o.role.value_counts(normalize=True).round(3).to_dict(),
           "side_share_taker": o[o.role == "taker"].side.value_counts(normalize=True).round(3).to_dict()}
    t = o[o.role == "taker"].copy()
    t["inplay"] = t.sign_ms / 1000 >= t.gs
    t["fill_frac"] = t.filled / t.shares
    t["lat"] = t.bts - t.sign_ms / 1000
    res["taker"] = {"n": len(t), "inplay_share": round(float(t.inplay.mean()), 3), "one_tx_share": round(float((t.n_tx == 1).mean()), 3),
                    "fill_frac_q": t.fill_frac.quantile([.25, .5, .75]).round(3).tolist(), "shares_q": t.shares.quantile([.25, .5, .75, .9]).round(0).tolist(),
                    "round_100_share": round(float((t.shares % 100 == 0).mean()), 3), "sign_to_block_q": t.lat.quantile([.05, .5, .95]).round(2).tolist(),
                    "price_whole_cent": round(float((np.abs(t.price * 100 - np.round(t.price * 100)) < 1e-6).mean()), 3)}
    m = o[o.role == "maker"]
    if len(m):
        res["maker"] = {"n": len(m), "shares_q": m.shares.quantile([.25, .5, .75]).round(0).tolist()}
    json.dump(res, open(RES / "results/taker_regime_orders.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
