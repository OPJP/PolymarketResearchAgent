"""Mechanics panel X13: is the taker order size the visible depth up to its limit ("sweep what you see")?
For each wallet taker order in the 10-31 12-18 development block with a book snapshot before signing (clob_wallets,
token-0 book; buying token 1 at q consumes token-0 bids at >= 1 - q): cumulative depth up to the limit in the last
snapshot before signing, in the snapshot at -1.0 s, and the order size; ratio and exact matches. Also C7: does the
wallet ever match against itself (taker and maker in one transaction), 16-22 Oct."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from dev_books import BLOCK0, OUT, RES, WALLET  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import live  # noqa: E402


def main():
    end = min(time.time() - 60, BLOCK0 + 6 * 3600)
    a = pd.read_parquet(OUT / "activity_devblocks.parquet")
    mk, _ = PolymarketData().markets_by_condition(sorted(a.conditionId.unique()))
    tok = {}
    for cid, x in mk.items():
        t = x["clobTokenIds"]
        t = json.loads(t) if isinstance(t, str) else t
        tok[str(t[0])] = (cid, 0, str(t[0]))
        tok[str(t[1])] = (cid, 1, str(t[0]))
    tok0 = {v[2] for v in tok.values()}
    recs = []
    h = BLOCK0
    while h < end:
        try:
            for r in live.iter_live("clob_wallets", h, min(h + 3600, end)):
                if r.get("a") in tok0 and r.get("k") in ("q", "f"):
                    recs.append((r["t"], r["a"], [(float(p), float(z)) for p, z in (r.get("b") or [])], [(float(p), float(z)) for p, z in (r.get("o") or [])]))
        except Exception as e:  # noqa: BLE001
            print("hour stopped", type(e).__name__)
        h += 3600
    bk = pd.DataFrame(recs, columns=["t", "a", "b", "o"]).sort_values("t")
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.idx == -1) & (d.maker == WALLET) & (d.sign_ms > 1.79e12) & d.token_id.astype(str).isin(tok)]
    rows = []
    for o in d.itertuples():
        cid, oi, t0 = tok[str(o.token_id)]
        b = bk[bk.a == t0]
        if len(b) == 0:
            continue
        tt = b.t.to_numpy()
        bought0 = (oi == 0) == (o.side == 0)
        q = o.price if o.side == 0 else 1 - o.price  # limit in terms of the bought outcome
        def depth_at(dt):
            j = np.searchsorted(tt, o.sign_ms + dt, side="left") - 1
            if j < 0:
                return np.nan
            if bought0:
                return sum(z for p, z in b.o.iloc[j] if p <= q + 1e-9)
            return sum(z for p, z in b.b.iloc[j] if 1 - p <= q + 1e-9)
        dep0, dep1 = depth_at(0), depth_at(-1500)
        rows.append({"shares": o.shares, "fill": o.fill, "depth_now": dep0, "depth_m1_5": dep1})
    x = pd.DataFrame(rows).dropna()
    res = {"orders": len(x),
           "size_over_depth_now_q": (x.shares / x.depth_now.replace(0, np.nan)).quantile([.1, .25, .5, .75, .9]).round(3).tolist(),
           "size_over_depth_m1_5_q": (x.shares / x.depth_m1_5.replace(0, np.nan)).quantile([.1, .25, .5, .75, .9]).round(3).tolist(),
           "size_eq_depth_now_within_1": round(float(((x.shares - x.depth_now).abs() <= 1).mean()), 3),
           "size_eq_depth_m1_5_within_1": round(float(((x.shares - x.depth_m1_5).abs() <= 1).mean()), 3),
           "size_within_10pct_depth_now": round(float(((x.shares - x.depth_now).abs() <= 0.1 * x.depth_now).mean()), 3),
           "fill_over_size_q": (x.fill / x.shares).quantile([.25, .5, .75]).round(3).tolist(),
           "fill_over_depth_now_q": (x.fill / x.depth_now.replace(0, np.nan)).quantile([.25, .5, .75]).round(3).tolist()}
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker"])
    tk = set(cd[(cd.idx == -1) & (cd.maker == WALLET)].tx)
    mkx = set(cd[(cd.idx >= 0) & (cd.maker == WALLET)].tx)
    res["C7_self_match_txs"] = len(tk & mkx)
    res["C7_wallet_taker_txs"] = len(tk)
    json.dump(res, open(RES / "results/taker_size_depth.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
