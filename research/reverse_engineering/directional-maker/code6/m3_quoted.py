"""Iteration 6, panel iter5 mechanics M3(a) (X32): quoted vs filled per BTC 5m window in the live development block.
Quoted proxy = exact-500/100 adds (the stream whose rate tracks the cluster's salt counter, Q2) on each side within
3 ticks of the touch; fills = the cluster's BTC 5m maker BUY fills (activity). Descriptive.
    python code6/m3_quoted.py <start_ts> <end_ts>"""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
C = ROOT / ".cache" / "re" / "directional-maker"
a, b = int(sys.argv[1]), int(sys.argv[2])
ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet")
x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
ev = ev[ev.w.str.contains("btc-updown-5m") & ev.d.isin([500.0, 100.0])]
near = np.where(ev.side == 1, ev.p >= ev.bb - 0.031, ev.p <= ev.ba + 0.031)
ev = ev[near]
acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))]).drop_duplicates(subset=["transactionHash", "asset", "w", "size", "price"])
acts = acts[(acts.type == "TRADE") & (acts.side == "BUY") & acts.slug.str.contains("btc-updown-5m", na=False) & (acts.timestamp >= a) & (acts.timestamp < b)]
rows = []
for w, g in ev.groupby("w"):
    st = int(w.split("-")[-1])
    if st < a or st + 300 > b:
        continue
    gi = g[(g.s >= st * 1000) & (g.s < (st + 300) * 1000)]
    f = acts[acts.slug == w]
    xw = x[(x.w == w) & (x.s >= st * 1000) & (x.s < (st + 300) * 1000)]
    rows.append({"w": w, "adds_near_touch": len(gi), "fills": len(f), "prints": len(xw), "print_shares": float(xw.z.sum()),
                 "range": float(xw.p.max() - xw.p.min()) if len(xw) else 0.0})
D = pd.DataFrame(rows)
q = D[D.adds_near_touch >= 50]
out = {"windows": len(D), "quoted_windows(>=50 adds)": len(q), "P0_fills_given_quoted": round(float((q.fills == 0).mean()), 3) if len(q) else None,
       "zero_fill_windows": D[D.fills == 0][["w", "adds_near_touch", "prints", "print_shares"]].to_dict("records"),
       "corr_fills_prints": round(float(np.corrcoef(D.fills, D.prints)[0, 1]), 3) if len(D) > 3 else None,
       "corr_fills_adds": round(float(np.corrcoef(D.fills, D.adds_near_touch)[0, 1]), 3) if len(D) > 3 else None,
       "median_adds": float(D.adds_near_touch.median()), "median_fills": float(D.fills.median())}
(HERE.parent / "results" / f"iter6_m3_quoted_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str)[:2500])
