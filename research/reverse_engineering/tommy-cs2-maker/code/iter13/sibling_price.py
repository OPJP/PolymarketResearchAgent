"""X176 step 5 (mechanics panel iter-12 P1, 'decode V where the input mix differs'): the same maker process on its
earlier account. 0x7d67f01d ('BACKTESTEOCARAIO1') made the non-GRID CS2 / Dota markets in 10-01..10-15 with the
wallet's design (BUY-only, MERGE, 100 / 10 shares), before the wallet took the role over on 10-16.
Sample: 3,253 of its 10,230 CS2 / Dota trade transactions of 10-08..10-15 (450 per day, calldata decoded with
code/fetch_calldata.py into sib7d67/calldata). Metrics on the same code path for both accounts:
  (1) price: its maker orders (deduped by salt / sign time) within one tick (0.01 inside [0.04, 0.96]) of the last
      public print stamped before signing, in the order's token space (rounded to the cent), the account's own
      transactions excluded; the same for the wallet's maker orders of 16-22 Oct (BUILD / VALIDATE split by game start);
  (2) its taker orders: count, sizes, and the signing lag behind the nearest earlier P4e taker order on the same token
      (P4e = 0x6f2a5d1c... from the census; looked up as the most frequent group-P member) in the same transactions;
  (3) whole-cent share, band [0.05, 0.95], sizes, and ladder bursts (same token within 50 ms).
Output: results/sibling_price.json
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
H = 1792713600
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
A = "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"


def tape(pm, cid, gs):
    p = OUT / "tapes" / f"{cid}_tkw.parquet"
    if p.exists():
        return pd.read_parquet(p)
    rows, _, _ = pm.market_trades(cid, start=int(gs) - 3600, end=int(min(gs + 4 * 3600 + 600, H - 1)), taker_only=True)
    return pd.DataFrame(rows)


def anchor_metric(orders: pd.DataFrame, tapes: dict, own_tx: set, tok2: dict) -> dict:
    rows = []
    for cid, g in orders.groupby("cid"):
        d = tapes.get(cid)
        if d is None or not len(d):
            continue
        d = d[~d.transactionHash.isin(own_tx)].sort_values("timestamp")
        ts = d.timestamp.to_numpy(float)
        p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        k = np.searchsorted(ts, g.sign_ms.to_numpy() / 1000.0, side="left")
        lp = np.where(k > 0, p0[np.maximum(k - 1, 0)], np.nan)
        oi = g.token_id.map(lambda t: tok2[t][1]).to_numpy()
        lp = np.where(oi == 0, lp, 1 - lp)
        age = np.where(k > 0, g.sign_ms.to_numpy() / 1000.0 - ts[np.maximum(k - 1, 0)], np.nan)
        rows.append(pd.DataFrame({"p": g.price.to_numpy(float), "a": np.round(lp, 2), "age": age}))
    if not rows:
        return {"n": 0}
    a = pd.concat(rows).dropna()
    tick = np.where((a.a >= 0.04) & (a.a <= 0.96), 0.01, 0.001)
    w = np.abs(a.p - a.a) <= tick + 1e-9
    return {"n": int(len(a)), "within_tick_last_print": round(float(w.mean()), 3),
            "exact_last_print": round(float((np.abs(a.p - a.a) <= 0.001 + 1e-9).mean()), 3),
            "median_offset_c": round(float(np.median(a.p - a.a)) * 100, 2),
            "within_tick_print_age_le_10s": round(float(w[a.age <= 10].mean()), 3) if (a.age <= 10).any() else None,
            "within_tick_print_age_gt_60s": round(float(w[a.age > 60].mean()), 3) if (a.age > 60).any() else None}


def describe(o: pd.DataFrame) -> dict:
    o = o.sort_values(["token_id", "sign_ms"])
    nb, sizes = 0, []
    for _, g in o.groupby("token_id"):
        s = g.sign_ms.to_numpy(np.int64)
        st = 0
        for i in range(1, len(s) + 1):
            if i == len(s) or s[i] - s[i - 1] > 50:
                nb += 1
                sizes.append(i - st)
                st = i
    pc = o.price.to_numpy(float)
    return {"orders": int(len(o)), "whole_cent": round(float(np.mean(np.isclose(pc * 100, np.round(pc * 100)))), 3),
            "outside_band_005_095": round(float(np.mean((pc < 0.05 - 1e-9) | (pc > 0.95 + 1e-9))), 4),
            "sizes": o.shares.round(0).value_counts().head(5).to_dict(), "bursts": nb,
            "orders_per_burst_mean": round(float(np.mean(sizes)), 2) if sizes else None}


def main():
    pm = PolymarketData()
    cols = ["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt", "sig_type", "side"]
    ca = pd.concat([pd.read_parquet(f, columns=cols) for f in glob.glob(str(OUT / "sib7d67/calldata/part_*.parquet"))])
    ca["maker"] = ca.maker.str.lower()
    ca["token_id"] = ca.token_id.astype(str)
    act = pd.read_parquet(OUT / "sib7d67/activity_1008_1015.parquet")
    own_a = set(act.transactionHash)
    cids = sorted(act.conditionId.unique())
    mk, _ = pm.markets_by_condition(cids)
    tok2 = {}
    gs = {}
    for cid, x in mk.items():
        toks = json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds")
        for i, t in enumerate(toks):
            tok2[str(t)] = (cid, i)
        g = x.get("gameStartTime") or x.get("startDate")
        try:
            gs[cid] = pd.Timestamp(str(g).replace("+00", "+00:00") if str(g).endswith("+00") else g).timestamp()
        except Exception:  # noqa: BLE001
            gs[cid] = None
    ao = ca[(ca.maker == A) & (ca.idx != -1) & ca.token_id.isin(tok2)].drop_duplicates(["salt", "sign_ms"]).copy()
    ao = ao[(ao.sign_ms > 1.7e12) & (ao.sign_ms < 1.8e12)]
    ao["cid"] = ao.token_id.map(lambda t: tok2[t][0])
    at = ca[(ca.maker == A) & (ca.idx == -1)].drop_duplicates(["salt", "sign_ms"])
    tapes = {}
    for cid in ao.cid.unique():
        if gs.get(cid):
            try:
                tapes[cid] = tape(pm, cid, gs[cid])
            except Exception as e:  # noqa: BLE001
                print("tape fail", cid[:10], type(e).__name__, flush=True)
    out = {"sibling_7d67": {"describe": describe(ao), "price": anchor_metric(ao, tapes, own_a, tok2),
                            "taker_orders": int(len(at)), "taker_sizes": at.shares.round(0).value_counts().head(5).to_dict(),
                            "markets_with_orders": int(ao.cid.nunique()), "tapes": len(tapes)}}
    # the wallet on the same code path (16-22 Oct)
    cw = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["cid", "oi", "gs_ts"])
    cw["maker"] = cw.maker.str.lower()
    cw["token_id"] = cw.token_id.astype(str)
    wtx = set(cw.loc[cw.maker == W, "tx"])
    wo = cw[(cw.maker == W) & (cw.idx != -1)].drop_duplicates(["salt", "sign_ms"]).copy()
    tokw = {}
    for r in wo[["token_id", "cid", "oi"]].drop_duplicates("token_id").itertuples():
        tokw[r.token_id] = (r.cid, int(r.oi))
    tw = {}
    for cid in wo.cid.unique():
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if p.exists():
            tw[cid] = pd.read_parquet(p)
    for name, sel in (("BUILD", wo.gs_ts < 1792540800), ("VALIDATE", wo.gs_ts >= 1792540800)):
        out[f"wallet_{name}"] = {"describe": describe(wo[sel]), "price": anchor_metric(wo[sel], tw, wtx, tokw)}
    # the sibling's maker orders on 10-16 inside the wallet's markets (co-signed period), same metric
    s16 = cw[(cw.maker == A) & (cw.idx != -1)].drop_duplicates(["salt", "sign_ms"]).copy()
    if len(s16):
        out["sibling_7d67_1016_in_wallet_markets"] = {"describe": describe(s16), "price": anchor_metric(s16, tw, wtx | set(s16.tx), tokw)}
    (RES / "sibling_price.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
