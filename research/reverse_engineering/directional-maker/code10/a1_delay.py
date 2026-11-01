"""Iteration 10 (A1 = X97, step 1): calibrate the sign-to-match delay of the taker orders that fill the cluster on the
development block 10-31 14:06-16:30 (live1031 calldata: taker sign_ms; shared/own recorder trade records: server match
ms by tx hash), by signatureType, and the block second minus match ms (live activity block ts)."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
cd["tx"] = cd.tx.str.lower(); cd["maker"] = cd.maker.str.lower()
tk = cd[(cd.role == "taker") & ~cd.maker.isin(CL)].drop_duplicates("tx")
xs = pd.concat([pd.read_parquet(p, columns=["h", "s"]) for p in glob.glob(str(C / "it6" / "x_*.parquet"))])
xs["h"] = xs.h.str.lower()
mms = xs.groupby("h").s.min()
tk = tk.assign(T=tk.tx.map(mms)).dropna(subset=["T"])
tk = tk[tk.sign_ms > 0]
tk["d"] = tk["T"] - tk["sign_ms"]
act = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_1793455200_*.parquet"))]) if glob.glob(str(C / "live_activity_1793455200_*.parquet")) else None
out = {"n": int(len(tk)), "delay_ms_quantiles": {q: float(tk.d.quantile(q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}}
out["by_sig_type"] = {int(k): {"n": int(len(g)), "median": float(g.d.median()), "q25": float(g.d.quantile(.25)), "q75": float(g.d.quantile(.75))} for k, g in tk.groupby("sig_type")}
if act is not None:
    print(act.columns.tolist()[:30])
    hcol = "transactionHash" if "transactionHash" in act.columns else ("tx" if "tx" in act.columns else None)
    if hcol:
        a2 = act[[hcol, "timestamp"]].rename(columns={hcol: "tx"}).drop_duplicates("tx"); a2["tx"] = a2.tx.str.lower()
        j = tk.merge(a2, on="tx")
        j["bm"] = j["timestamp"] * 1000 - j["T"]
        j["bs"] = j["timestamp"] * 1000 - j["sign_ms"]
        out["block_minus_match_ms"] = {q: float(j.bm.quantile(q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
        out["block_minus_sign_ms"] = {q: float(j.bs.quantile(q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
        out["n_block"] = int(len(j))
print(json.dumps(out, indent=1))
json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_a1_delay.json", "w"), indent=1)
