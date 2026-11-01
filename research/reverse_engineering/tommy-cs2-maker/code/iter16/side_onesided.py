"""Side item applicability (accuracy rule 3: scored only where the wallet is one-sided in >= 20% of its markets).
Per traded market (16-22 Oct, both roles, filled shares from orders.parquet): share of filled shares on token 0;
one-sided if > 0.95 or < 0.05 (also 0.9 / 0.1). BUILD / VALIDATE by game start; and for one-sided markets, how often
the bought token is the pre-game favourite (last print before the start > 0.5) and the eventual winner.
Output: results/side_onesided.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "oi", "role", "filled", "gs_ts", "event", "smt"])
o = o[o.filled > 0]
g = o.groupby(["cid", "oi"]).filled.sum().unstack(fill_value=0.0)
g.columns = [f"t{c}" for c in g.columns]
g["share0"] = g.t0 / (g.t0 + g.t1)
meta = o.groupby("cid").agg(gs=("gs_ts", "first"), event=("event", "first"), smt=("smt", "first"))
g = g.join(meta)
g["split"] = np.where(g.gs < 1792540800, "BUILD", "VALIDATE")
out = {}
for sp, x in g.groupby("split"):
    out[sp] = {"markets": int(len(x)), "one_sided_95": round(float(((x.share0 > 0.95) | (x.share0 < 0.05)).mean()), 3),
               "one_sided_90": round(float(((x.share0 > 0.9) | (x.share0 < 0.1)).mean()), 3),
               "share0_quantiles": [round(float(q), 3) for q in np.percentile(x.share0, [10, 25, 50, 75, 90])],
               "by_type": {t: round(float(((y.share0 > 0.95) | (y.share0 < 0.05)).mean()), 3) for t, y in x.groupby("smt")}}
(RES / "side_onesided.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
