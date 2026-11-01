"""iteration 15 (post hoc): the Chainlink noise level by day on the lot, from the X102 even-second Chainlink values
(code11/fetch_cl_x102.py, still fetching; 10-23..25 so far) against the Binance USD-M 1-s mids (fut1s): sd of 2-s changes
of Chainlink over sd of 2-s changes of the futures at the same seconds, per day and per 6-h block (STUDY days, case by
case; development data), plus 10-31 14-18 and 11-01 07-08 from the live recordings for comparison (iteration 15)."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
d = pd.concat([pd.read_parquet(f) for f in glob.glob(str(C / "cl/cl_hist11_*.parquet"))]).dropna(subset=["open"])
d = d.drop_duplicates("tau").sort_values("tau")
cl = pd.Series(d.open.to_numpy(float), index=d.tau.to_numpy(np.int64))
out = {}
f1 = sorted(glob.glob(str(C / "fut1s/*.parquet")))
print(pd.read_parquet(f1[0]).columns.tolist())
fut = pd.concat([pd.read_parquet(f) for f in f1 if Path(f).stem >= "2026-10-22"])
sc = [c for c in fut.columns if c in ("sec", "s", "ts")][0]; vc = [c for c in fut.columns if c not in (sc,)][0]
fs = pd.Series(fut[vc].to_numpy(float), index=fut[sc].to_numpy(np.int64)).sort_index()
fs = fs[~fs.index.duplicated()]
t = cl.index.to_numpy(); ok = np.isin(t + 2, t)
t0 = t[ok]; dcl = cl.reindex(t0 + 2).to_numpy() - cl.reindex(t0).to_numpy()
dfu = fs.reindex(t0 + 2).to_numpy() - fs.reindex(t0).to_numpy()
D = pd.DataFrame({"t": t0, "dcl": dcl, "dfu": dfu}).dropna()
D["block"] = pd.to_datetime(D.t, unit="s").dt.strftime("%m-%d_%H").str[:-2] + (pd.to_datetime(D.t, unit="s").dt.hour // 6 * 6).astype(str).str.zfill(2)
for b, g in D.groupby("block"):
    if len(g) >= 200:
        out[b] = {"n": int(len(g)), "sd_cl_2s": round(float(g.dcl.std()), 3), "sd_fut_2s": round(float(g.dfu.std()), 3),
                  "ratio": round(float(g.dcl.std() / g.dfu.std()), 3), "corr": round(float(np.corrcoef(g.dcl, g.dfu)[0, 1]), 3)}
for k, v in out.items(): print(k, v)
(HERE.parent / "results/iter15_noise_days.json").write_text(json.dumps(out, indent=1))
