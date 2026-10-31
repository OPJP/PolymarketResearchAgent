"""Iteration 10 (A1 = X97 and I9-4 = X90): the Chainlink report stamps needed for a historical match clock.
Pre-registered (22:46 UTC, before any Chainlink value of these stamps was read):
  T_hat = clip(taker sign_ms + 620 ms, block_ms - 3,000, block_ms - 1,500)   (620 = median sign-to-match delay of
          the takers of 10-31 14:06-16:30; [1.5, 3.0] s = q10-q90 of block minus match on the same fills)
  stamp = floor((T_hat - 1,432) / 1,000)                                      (R6's report delay)
For fills without a usable taker sign_ms: T_hat = block_ms - 2,285 (median block minus match).
Priority 0: STUDY and VALIDATE BTC 5m fills, interleaved in one random order (seed 10).
Priority 1: BUILD BTC 5m fill seconds (no calldata: block clock stamp), 10-09 first (they expire first, ~11-08).
Priority 2: BUILD BTC 15m, then the lot 15m."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
rows = []
for sp, fn in (("study", "b1_takers_study"), ("validate", "b1_takers_valid")):
    v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "b", "st", "en"])
    t = pd.read_parquet(C / f"{fn}.parquet", columns=["tx", "sign_ms", "sig_type", "bts"])
    t["tx"] = t.tx.str.lower(); t = t.drop_duplicates("tx")
    v["txh"] = v.txh.str.lower()
    j = v.merge(t, left_on="txh", right_on="tx", how="left")
    bms = j.b.astype(np.int64) * 1000
    ok = j.sign_ms.notna() & (j.sign_ms > 0) & (bms - j.sign_ms < 60000) & (bms - j.sign_ms > -1000)
    th = np.where(ok, np.clip(j.sign_ms.fillna(0) + 620, bms - 3000, bms - 1500), bms - 2285)
    j["stamp"] = np.floor((th - 1432) / 1000).astype(np.int64)
    j["split"] = sp
    rows.append(j[["split", "stamp"]])
lot = pd.concat(rows).drop_duplicates("stamp")
rng = np.random.default_rng(10)
lot["pri"] = 0
lot["ord"] = rng.permutation(len(lot))
b5 = pd.read_parquet(C / "it9/volhist_build.parquet", columns=["b"])
b5 = pd.DataFrame({"stamp": (b5.b.astype(np.int64) - 4).unique()}); b5["split"] = "build5"; b5["pri"] = 1; b5["ord"] = b5.stamp.rank().astype(int)
parts = [lot, b5]
for sp in ("build", "study", "validate"):
    f = C / f"it9/volhist15_{sp}.parquet"
    if f.exists():
        b = pd.read_parquet(f, columns=["b"])
        b = pd.DataFrame({"stamp": (b.b.astype(np.int64) - 4).unique()}); b["split"] = sp + "15"; b["pri"] = 2; b["ord"] = b.stamp.rank().astype(int)
        parts.append(b)
allp = pd.concat(parts).sort_values(["pri", "ord"]).drop_duplicates("stamp")
allp.to_parquet(C / "cl" / "_queue10.parquet.tmp", index=False)
import os; os.replace(C / "cl" / "_queue10.parquet.tmp", C / "a1_queue10.parquet")
print(allp.groupby(["pri", "split"]).size())
