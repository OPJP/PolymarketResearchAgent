"""X176 step 3 (mechanics panel iter-12 P1): census of every maker in the wallet's 16-22 Oct markets for the
same-process signature found for 0x52661b8e: orders signed 0-5 ms AFTER a wallet order on the same token (before the
wallet's order can reach the book, ~18-24 ms transit), at the same price, against the [5, 50) ms rate.
Also the wallet's own signature as a reference and the share of such orders at a price inside the wallet burst.
Output: results/same_process_census.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    cols = ["tx", "idx", "maker", "token_id", "price", "shares", "sign_ms", "salt", "sig_type"]
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    cd["maker"] = cd.maker.str.lower()
    cd["token_id"] = cd.token_id.astype(str)
    cd = cd[(cd.sign_ms > 1.7e12) & (cd.sign_ms < 1.8e12)]
    orders = cd.drop_duplicates(["maker", "salt", "sign_ms"])
    w = orders[orders.maker == W][["token_id", "sign_ms", "price"]].sort_values("sign_ms")
    wt = {t: (g.sign_ms.to_numpy(np.int64), g.price.to_numpy(float)) for t, g in w.groupby("token_id")}
    oth = orders[(orders.maker != W) & (orders.idx != -1)]
    rows = []
    for m, g in oth.groupby("maker"):
        if len(g) < 100:
            continue
        lag = np.full(len(g), np.nan)
        same = np.zeros(len(g), bool)
        for tok, gg in g.groupby("token_id"):
            if tok not in wt:
                continue
            ws, wp = wt[tok]
            s = gg.sign_ms.to_numpy(np.int64)
            k = np.searchsorted(ws, s, side="right") - 1
            ok = k >= 0
            ii = gg.index.to_numpy()
            pos = g.index.get_indexer(ii)
            lag[pos[ok]] = s[ok] - ws[k[ok]]
            same[pos[ok]] = np.isclose(gg.price.to_numpy(float)[ok], wp[k[ok]])
        a = np.sum((lag >= 0) & (lag < 5))
        a_same = np.sum((lag >= 0) & (lag < 5) & same)
        b = np.sum((lag >= 5) & (lag < 50)) / 9.0
        rows.append({"maker": m, "orders": int(len(g)), "lag0_5": int(a), "lag0_5_same_price": int(a_same),
                     "per5ms_5_50": round(float(b), 2), "ratio": round(float(a / b), 2) if b > 0 else None,
                     "sizes_top": g.shares.round(0).value_counts().head(3).to_dict(), "sig_type": int(g.sig_type.mode().iloc[0]),
                     "tokens": int(g.token_id.nunique()), "first": int(g.sign_ms.min() // 1000), "last": int(g.sign_ms.max() // 1000)})
    df = pd.DataFrame(rows)
    df["excess"] = df.lag0_5 - df.per5ms_5_50
    df = df.sort_values("excess", ascending=False)
    top = df.head(15)
    out = {"makers_scanned": int(len(df)), "top": top.to_dict(orient="records"),
           "n_ratio_ge_3_and_excess_ge_20": int(((df.ratio >= 3) & (df.excess >= 20)).sum())}
    (RES / "same_process_census.json").write_text(json.dumps(out, indent=1, default=str))
    print(top[["maker", "orders", "lag0_5", "lag0_5_same_price", "per5ms_5_50", "ratio", "sizes_top", "sig_type", "tokens"]].to_string())
    print("candidates", out["n_ratio_ge_3_and_excess_ge_20"])


if __name__ == "__main__":
    main()
