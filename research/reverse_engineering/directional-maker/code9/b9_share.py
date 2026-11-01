"""Iteration 9 (catalog B9): the cluster's share of maker volume per BTC 5m window (BUILD 10-09..22: data-api taker tapes
= every print once; cluster maker fills from the BUILD fill table) and the maker-rebate rows, as a proxy of its maker
rebate pool share; does its share rise where total volume (competition) is low?"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker"
f = pd.read_parquet(C / "cluster_btc5m_fills.parquet")
f = f[f.role == "maker"]
cl = f.groupby("cid").shares.sum()
tot = []
for day in range(1791504000, 1792713600, 86400):
    t = pd.read_parquet(C / f"taker5m_day_{day}.parquet", columns=["cid", "size"])
    tot.append(t.groupby("cid")["size"].sum())
tot = pd.concat(tot).groupby(level=0).sum()
W = pd.DataFrame({"tot": tot}).join(cl.rename("cl")).fillna(0)
W = W[W.tot > 0]
W["share"] = W.cl / W.tot
act = [pd.read_parquet(C / f"activity_{n}.parquet", columns=["type", "usdcSize", "timestamp"]) for n in ("bosona", "almach", "momoney")]
A = pd.concat(act)
reb = A[A.type == "MAKER_REBATE"].usdcSize.sum()
rew = A[A.type == "REWARD"].usdcSize.sum()
out = {"windows": int(len(W)), "cluster_share_of_volume_pooled": float(W.cl.sum() / W.tot.sum()),
       "share_median": float(W.share.median()), "share_p90": float(W.share.quantile(0.9)),
       "spearman_share_vs_total_volume": float(spearmanr(W.share, W.tot).correlation),
       "share_by_volume_quintile": {str(k): round(float(v), 4) for k, v in W.groupby(pd.qcut(W.tot, 5, labels=False)).apply(lambda d: d.cl.sum() / d.tot.sum()).items()},
       "maker_rebates_usd_build": float(reb), "rewards_usd_build": float(rew)}
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parents[1] / "results" / "iter9_b9_share.json").write_text(json.dumps(out, indent=1))
