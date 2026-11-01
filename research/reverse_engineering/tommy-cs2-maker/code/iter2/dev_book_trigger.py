"""A7 strong form (mechanics/information panel X): does a public book event precede the wallet's / the pack's taker
signings? Development block 10-31 12-18 UTC, units that started in it. For each taker order (calldata_dev, signing ms)
on the side it consumes (token-0 asks if it buys token 0, token-0 bids if it buys token 1): depth within 3c of the touch
on that side in the last snapshot before t-2 s, t-1 s, t-0.2 s and the first after t+1 s, t+3 s; the number of book
snapshots in [t-2, t) vs [t, t+2). Control: random times in the same markets' in-play spans."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dev_books import read_books, BLOCK0, OUT, RES, WALLET  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import time

PACK = {"0xfe8a28be83ba295a9384f72f240d2cfa96bc23ce", "0x2529c68db36ce8aa64c64affe620267744a3548a",
        "0x72aaaaf9f6b0286e390de5b568af0f99a00c90e0", "0xf1ee4842fa0c7283632185e42577027452d4519c",
        "0x4ebc2722adc772bde8680792d0a6fdf15499a33d", "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3"}


def depth(L, side, ref, w=0.03):
    if not L:
        return 0.0
    if side == "o":
        best = min(p for p, z in L)
        return sum(z for p, z in L if p <= best + w + 1e-9)
    best = max(p for p, z in L)
    return sum(z for p, z in L if p >= best - w - 1e-9)


def main():
    a = pd.read_parquet(OUT / "activity_devblocks.parquet")
    cids = sorted(a.conditionId.unique())
    mk, _ = PolymarketData().markets_by_condition(cids)
    tok = {}
    for cid, x in mk.items():
        t = x["clobTokenIds"]
        t = json.loads(t) if isinstance(t, str) else t
        tok[str(t[0])] = (cid, 0, str(t[0]))
        tok[str(t[1])] = (cid, 1, str(t[0]))
    tok0 = {v[2] for v in tok.values()}
    end = min(time.time() - 60, BLOCK0 + 6 * 3600)
    bk = pd.DataFrame(read_books(tok0, BLOCK0, end), columns=["t", "a", "k", "b", "o"]).sort_values("t")
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.idx == -1) & (d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12)]
    d = d[d.token_id.astype(str).isin(tok)]
    d["grp"] = np.where(d.maker == WALLET, "W", np.where(d.maker.isin(PACK), "pack", "other"))
    rng = np.random.default_rng(1)
    rows = []
    for tok0_, b in bk.groupby("a"):
        tt = b.t.to_numpy()
        orders = d[d.token_id.astype(str).map(lambda t: tok[t][2]) == tok0_]
        if len(orders) == 0 or len(tt) < 50:
            continue
        evs = [(s, grp, tok[str(t)][1], side) for s, grp, t, side in zip(orders.sign_ms, orders.grp, orders.token_id, orders.side)]
        evs += [(rng.uniform(tt[0] + 5000, tt[-1] - 5000), "ctrl", int(rng.integers(0, 2)), 0) for _ in range(len(orders))]
        for s, grp, oi, side in evs:
            bought0 = (oi == 0) == (side == 0)
            sd = "o" if bought0 else "b"
            def at(dt):
                j = np.searchsorted(tt, s + dt, side="left") - 1
                return depth(b[sd].iloc[j], sd, None) if j >= 0 else np.nan
            def after(dt):
                j = np.searchsorted(tt, s + dt, side="left")
                return depth(b[sd].iloc[j], sd, None) if j < len(tt) else np.nan
            n_pre = int(((tt >= s - 2000) & (tt < s)).sum())
            n_post = int(((tt >= s) & (tt < s + 2000)).sum())
            rows.append({"grp": grp, "d_m2": at(-2000), "d_m1": at(-1000), "d_m02": at(-200), "d_p1": after(1000), "d_p3": after(3000),
                         "n_pre": n_pre, "n_post": n_post})
    x = pd.DataFrame(rows)
    x["drop_pre"] = (x.d_m02 < 0.7 * x.d_m2)
    x["drop_post"] = (x.d_p3 < 0.7 * x.d_m02)
    res = {}
    for g, s in x.groupby("grp"):
        res[g] = {"n": len(s), "depth_drop30_in_last2s_before": round(float(s.drop_pre.mean()), 3),
                  "depth_drop30_in_3s_after": round(float(s.drop_post.mean()), 3),
                  "snapshots_pre2s_mean": round(float(s.n_pre.mean()), 2), "snapshots_post2s_mean": round(float(s.n_post.mean()), 2),
                  "depth_ratio_m02_over_m2_median": round(float((s.d_m02 / s.d_m2).median()), 3),
                  "depth_ratio_p3_over_m02_median": round(float((s.d_p3 / s.d_m02).median()), 3)}
    json.dump(res, open(RES / "results/dev_book_trigger.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
