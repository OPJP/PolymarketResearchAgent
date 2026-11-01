"""Iteration 11 (X101 price part): list the transactions whose in-block position is needed for the in-block price
anchor: every BTC 5m cluster maker BUY fill tx of the lot and every clean print tx of the same market stamped in the
same block second. Writes it11/inblock_needed.parquet (hash, split). No per-fill output.
    python code11/inblock_needed.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
SPLIT_V = 1793059200
W = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
F = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
F = F[(F.role == "maker") & (F.side == "BUY") & F.cid.isin(W.index)].copy()
F["txh"] = F.txh.str.lower()
cl_tx = set(F.txh)
for n in ("bosona", "almach", "momoney"):
    cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
need = []
for day in sorted(set((W.start_ts // 86400 * 86400).astype(int))):
    T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "tx"])
    T["tx"] = T.tx.str.lower()
    T = T[~T.tx.isin(cl_tx)]
    keys = set(zip(F.cid, F.ts.astype(int)))
    m = [(c, int(t)) in keys for c, t in zip(T.cid, T.ts)]
    sub = T[m]
    need.append(pd.DataFrame({"h": sub.tx.unique(), "kind": "clean"}).assign(split="study" if day < SPLIT_V else "validate"))
    print(day, len(sub), sub.tx.nunique(), flush=True)
fx = F.drop_duplicates("txh")
need.append(pd.DataFrame({"h": fx.txh, "kind": "cluster", "split": np.where(fx.ts < SPLIT_V, "study", "validate")}))
N = pd.concat(need).drop_duplicates("h")
N.to_parquet(C / "it11" / "inblock_needed.parquet")
print(N.groupby(["split", "kind"]).size())
