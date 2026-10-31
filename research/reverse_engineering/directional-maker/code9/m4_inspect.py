"""Iteration 9: inspect the cluster's salts around the 10-31 16:53 BTC 5m switch-off (development)."""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
     "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "mo-money"}
act = pd.read_parquet(C / "it9" / "act_1793448000_1793469600.parquet")
act = act[act.type == "TRADE"].copy()
act["tx"] = act.transactionHash.str.lower()
ts = act.groupby("tx").timestamp.min()
slug = act.groupby("tx").slug.first()
rows = []
for p in glob.glob(str(C / "calldata" / "*1031_*.parquet")) + glob.glob(str(C / "calldata" / "it9sw_*.parquet")):
    d = pd.read_parquet(p, columns=["tx", "maker", "salt", "role"])
    d["tx"] = d.tx.str.lower()
    d["src"] = Path(p).name[:8]
    rows.append(d)
D = pd.concat(rows)
D["maker"] = D.maker.str.lower()
D = D[D.maker.isin(W)].copy()
D["ts"] = D.tx.map(ts)
D["slug"] = D.tx.map(slug)
D["salt"] = pd.to_numeric(D.salt.astype(str), errors="coerce")
print("cluster orders", len(D), "with ts", D.ts.notna().sum())
print(D.groupby("src").ts.agg(["count", "min", "max"]))
D = D.dropna(subset=["ts"])
print("cluster txs in activity >= 15:50:", act[act.timestamp >= 1793465400].tx.nunique(), "with calldata:", D[D.ts >= 1793465400].tx.nunique())
for w, n in W.items():
    g = D[(D.maker == w) & (D.ts >= 1793464800)].sort_values("ts").drop_duplicates("salt")
    g = g.assign(t=pd.to_datetime(g.ts, unit="s").dt.strftime("%H:%M:%S"), fam=g.slug.str.replace(r"-\d{9,}$", "", regex=True).str[:22])
    print("==", n, len(g))
    print(g[["t", "salt", "role", "fam"]].to_string(index=False, max_rows=80))
