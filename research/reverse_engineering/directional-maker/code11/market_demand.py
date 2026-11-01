"""Iteration 11 (X111): did the market's taker demand move to the favourite, or did the cluster's quote move to the
underdog? Per lot day, over clean taker prints (no cluster transaction) of BTC 5m windows: the share of taker BUY shares
on the favourite (price > 0.5), the share of taker BUY shares that are favourite buys at 0.5-0.9 (the band the cluster's
underdog bids complement), and the same for the prints that filled the cluster (cluster transactions). Aggregates only.
    python code11/market_demand.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
F = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["txh"])
cl_tx = set(F.txh.str.lower())
for n in ("bosona", "almach", "momoney"):
    cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
out = {}
for day in sorted(set((W.start_ts // 86400 * 86400).astype(int))):
    T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["side", "price", "size", "tx", "wallet"])
    T["cl"] = T.tx.str.lower().isin(cl_tx)
    T = T[~T.wallet.str.lower().isin({"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"})]
    rec = {}
    for nm, m in (("clean", ~T.cl), ("cluster_tx", T.cl)):
        b = T[m & (T.side == "BUY")]
        s = T[m & (T.side == "SELL")]
        rec[nm] = {"buy_shares": float(b["size"].sum()), "fav_share_of_buys": round(float(b["size"][b.price > 0.5].sum() / max(b["size"].sum(), 1)), 4),
                   "sell_share": round(float(s["size"].sum() / max(b["size"].sum() + s["size"].sum(), 1)), 4),
                   "fav_share_of_sells": round(float(s["size"][s.price > 0.5].sum() / max(s["size"].sum(), 1)), 4)}
    out[str(pd.to_datetime(day, unit="s").date())] = rec
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "iter11_market_demand.json").write_text(json.dumps(out, indent=1))
