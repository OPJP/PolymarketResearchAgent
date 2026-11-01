"""Mechanics panel X11 (strong form of the timing cross-correlogram): after a public taker order is signed, does the
wallet re-sign maker orders only when that taker order matched the WALLET (user channel: replenish after own fills)
or also when it matched only other makers (market channel: re-join a moved touch)? Rate of the wallet's maker
signings (any token of the market) in [+0.5, +2.0) s after each taker signing, split by whether the taker's
transaction includes a wallet maker fill; control = the same taker orders shifted by +-U(30, 300) s.
Development data 16-22 Oct, in-play only."""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import OUT, RES, SPLIT, WALLET  # noqa: E402


def main():
    cols = ["tx", "idx", "maker", "sign_ms", "condition_id"]
    pub = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])
    al = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["cid", "gs_ts"])
    wtx = set(al.loc[(al.maker == WALLET) & (al.idx >= 0), "tx"])
    allx = pd.concat([pub, al[cols]]).drop_duplicates(["tx", "idx"])
    tk = allx[(allx.idx == -1) & (allx.maker != WALLET) & (allx.sign_ms > 1.7e12) & (allx.sign_ms < 1.8e12)].copy()
    tk["matched_wallet"] = tk.tx.isin(wtx)
    o = pd.read_parquet(OUT / "orders.parquet")
    mo = o[(o.role == "maker") & (o.sign_ms > 1.7e12)]
    gs = o.groupby("cid").gs_ts.first()
    rng = np.random.default_rng(2)
    res = {}
    rows = []
    for cid, g in tk.groupby("condition_id"):
        if cid not in gs.index:
            continue
        ws = np.sort(mo.loc[mo.cid == cid, "sign_ms"].to_numpy())
        g = g[g.sign_ms / 1000 >= gs[cid]]
        if len(ws) == 0 or len(g) == 0:
            continue
        s = g.sign_ms.to_numpy()
        n = np.searchsorted(ws, s + 2000) - np.searchsorted(ws, s + 500)
        sh = s + rng.choice([-1, 1], len(s)) * rng.uniform(30000, 300000, len(s))
        nc = np.searchsorted(ws, sh + 2000) - np.searchsorted(ws, sh + 500)
        pre = np.searchsorted(ws, s) - np.searchsorted(ws, s - 1500)
        rows.append(pd.DataFrame({"cid": cid, "split": np.where(gs[cid] >= SPLIT, "VALIDATE", "BUILD"), "mw": g.matched_wallet.to_numpy(),
                                  "n": n, "nc": nc, "pre": pre}))
    x = pd.concat(rows, ignore_index=True)
    for (sp, mw), q in x.groupby(["split", "mw"]):
        res[f"{sp}_{'matched_wallet' if mw else 'matched_others_only'}"] = {
            "taker_orders": len(q), "rate_after_0.5_2s": round(float(q.n.mean()), 3), "rate_control": round(float(q.nc.mean()), 3),
            "ratio": round(float(q.n.mean() / max(q.nc.mean(), 1e-9)), 2), "rate_before_-1.5_0s": round(float(q.pre.mean()), 3)}
    json.dump(res, open(RES / "results/resign_split.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
