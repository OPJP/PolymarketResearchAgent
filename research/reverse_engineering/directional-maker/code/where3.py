"""Iteration 3, N7c (descriptive): where in the window, and at which fair levels, did the cluster's BTC 5m maker
fills earn (BUILD) and lose (VALIDATE)? Per fill (more than 60 s before the end): Binance fair of the filled side at
the fill (seconds published by ts), its move over the next 60 s (description only), payout minus price."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa: E402
from panel2 import OUT, H  # noqa: E402

VAL0 = 1792108800


def main():
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[w["end_ts"] <= H]
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    mk = fills[(fills["role"] == "maker") & (fills["side"] == "BUY")].merge(w, on="cid")
    mk = mk[mk["ts"] < mk["end_ts"] - 60].copy()
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[spd["sec"] < H]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    up = (mk["token_id"] == mk["up_token"]).to_numpy()
    f0, _ = fair_up(sp, mk["start_ts"].to_numpy(), mk["end_ts"].to_numpy(), mk["ts"].to_numpy())
    f60, _ = fair_up(sp, mk["start_ts"].to_numpy(), mk["end_ts"].to_numpy(), mk["ts"].to_numpy() + 61)
    mk["F"] = np.where(up, f0, 1 - f0)
    mk["dF60"] = np.where(up, f60 - f0, f0 - f60)
    mk["won"] = np.where(up, mk["up_payout"], 1 - mk["up_payout"])
    mk["pnl"] = (mk["won"] - mk["price"]) * mk["shares"]
    mk["usd"] = mk["price"] * mk["shares"]
    mk["rel"] = mk["ts"] - mk["start_ts"]
    mk["edge"] = mk["F"] - mk["price"]
    res = {}
    for split, part in (("build", mk[mk["ts"] < VAL0]), ("validate", mk[mk["ts"] >= VAL0])):
        r = {}
        for col, bins in (("rel", [0, 10, 30, 120, 240]), ("F", [0, 0.2, 0.4, 0.6, 0.8, 1.0]), ("edge", [-1, 0, 0.02, 0.05, 0.1, 1])):
            c = pd.cut(part[col], bins).rename("bucket")
            g = part.groupby(c, observed=True).agg(n=("pnl", "size"), usd=("usd", "sum"), pnl=("pnl", "sum"), dF60=("dF60", "mean"),
                                                   edge_mean=("edge", "mean"))
            g["ret"] = g["pnl"] / g["usd"]
            r[col] = g[["n", "edge_mean", "dF60", "ret"]].round(4).reset_index().astype(str).values.tolist()
        res[split] = r
        print(split)
        for col in r:
            for row in r[col]:
                print("  ", col, row)
    (HERE.parent / "results_iter3_where.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
