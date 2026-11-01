"""Iteration 6, Q2 step 4 (X36): direct identity of the exact-500/100 maker orders. Calldata of EVERY match recorded in
the own raw book (BTC 5m current/next + 15m) in a 20-minute live slice; share of filled exact-500/100 maker orders that
belong to the cluster, by size class. python code6/q2_identity.py <a> <b> (x parquet period) <s0> <s1> (slice)"""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
sys.path.insert(0, str(HERE.parent / "code4"))
import fetch_calldata as F
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
a, b, s0, s1 = map(int, sys.argv[1:5])
x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
x = x[(x.s >= s0 * 1000) & (x.s < s1 * 1000) & (x.h.str.len() > 10)]
tmp = C / "it6" / f"allmatch_{s0}_{s1}.parquet"
pd.DataFrame({"txh": x.h.str.lower(), "ts": (x.s // 1000).astype(int)}).drop_duplicates("txh").to_parquet(tmp)
tag = f"allmatch{s0}"
F.main(str(tmp), tag, s0, s1)
cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / f"{tag}_*.parquet"))])
mk = cd[cd.role == "maker"].copy()
mk["maker"] = mk.maker.str.lower()
mk["S"] = (np.where(mk.oside == 0, mk.taker_amount, mk.maker_amount) / 1e6).round(2)
mk["cl"] = mk.maker.isin(CL)
out = {"txs": int(cd.tx.nunique()), "maker_orders": int(len(mk)), "cluster_share_all_maker_orders": round(float(mk.cl.mean()), 4)}
for S in (500.0, 100.0, 250.0, 62.0):
    m = mk[mk.S == S]
    out[f"S{int(S)}"] = {"n": int(len(m)), "cluster_share": round(float(m.cl.mean()), 3) if len(m) else None,
                          "distinct_other_makers": int(m[~m.cl].maker.nunique()), "top_other": m[~m.cl].maker.value_counts().head(3).to_dict()}
cm = mk[mk.cl]
out["cluster_orders_size_mix"] = cm.S.value_counts(normalize=True).head(6).round(3).to_dict()
(HERE.parent / "results" / f"iter6_q2_identity_{s0}_{s1}.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))
