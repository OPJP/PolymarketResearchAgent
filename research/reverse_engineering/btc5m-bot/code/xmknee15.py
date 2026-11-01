"""Iteration 15 (X140 = information P2 steps 1-2, compact): per-leader-wallet knee profile. First legs (rank 0), all six capture days
(descriptive): P(k_c > 0) = agreement of the 250-ms spot microprice return ending c ms before m0 with the bought outcome, by the
wallet that carried the first leg; two-segment knee fit per wallet on the fit days 10-17..19; fan-out gap of XM legs after a DS / GF
first leg. Usage: python -I xmknee15.py IT14_DIR OUT.json"""
import sys, json
import numpy as np, pandas as pd
D14, OUT = sys.argv[1], sys.argv[2]
KS = list(range(400, 140, -10))
d = pd.read_parquet(f"{D14}/dcclock14_frame.parquet", columns=["cid", "wallet", "up", "m", "m0", "rank", "ev", "start_ts"] + [f"k{c}" for c in KS])
first = d[d["rank"] == 0]
rep = {}
def knee(cs, ys):
    best = None
    for kc in cs[2:-2]:
        a = np.array(cs) >= kc
        X1 = np.column_stack([np.ones(len(cs)), np.where(a, np.array(cs) - kc, 0), np.where(~a, np.array(cs) - kc, 0)])
        b, res, *_ = np.linalg.lstsq(X1, ys, rcond=None)
        sse = float(((X1 @ b - ys) ** 2).sum())
        if best is None or sse < best[0]:
            best = (sse, kc, b)
    return {"knee_c": int(best[1]), "level": round(float(best[2][0]), 4), "slope_before_per10ms": round(float(-best[2][1] * 10), 4), "slope_after_per10ms": round(float(-best[2][2] * 10), 4)}
for part, sel in (("fit", first.start_ts < 1792454400), ("score", first.start_ts >= 1792454400)):
    for w in ("DS", "GF", "XM"):
        x = first[sel & (first.wallet == w)]
        sg = np.where(x.up.astype(int) == 1, 1.0, -1.0); prof = [float(np.where(np.sign(x[f"k{c}"].to_numpy() * sg) == 0, 0.5, (x[f"k{c}"].to_numpy() * sg > 0)).mean()) for c in KS]
        rep[f"{part}_{w}"] = {"n": int(len(x)), "profile": {c: round(p, 4) for c, p in zip(KS, prof)}, **knee(KS, np.array(prof))}
# XM legs after another wallet's first leg in the same event: gap distribution
ev = d.sort_values(["ev", "m"])
f0 = ev.groupby("ev").agg(w0=("wallet", "first"), mf=("m", "first"))
ev = ev.join(f0, on="ev")
xm = ev[(ev["rank"] > 0) & (ev.wallet == "XM")]
for w0 in ("DS", "GF"):
    g = (xm[xm.w0 == w0].m - xm[xm.w0 == w0].mf)
    rep[f"xm_after_{w0}_gap_ms"] = {"n": int(len(g)), "q10": float(g.quantile(0.1)), "q50": float(g.median()), "q90": float(g.quantile(0.9)), "share_lt60": round(float((g < 60).mean()), 4)}
ds = ev[(ev["rank"] > 0) & (ev.wallet == "DS")]
for w0 in ("GF", "XM"):
    g = (ds[ds.w0 == w0].m - ds[ds.w0 == w0].mf)
    rep[f"ds_after_{w0}_gap_ms"] = {"n": int(len(g)), "q10": float(g.quantile(0.1)), "q50": float(g.median()), "q90": float(g.quantile(0.9)), "share_lt60": round(float((g < 60).mean()), 4)}
gf = ev[(ev["rank"] > 0) & (ev.wallet == "GF")]
for w0 in ("DS", "XM"):
    g = (gf[gf.w0 == w0].m - gf[gf.w0 == w0].mf)
    rep[f"gf_after_{w0}_gap_ms"] = {"n": int(len(g)), "q10": float(g.quantile(0.1)), "q50": float(g.median()), "q90": float(g.quantile(0.9)), "share_lt60": round(float((g < 60).mean()), 4)}
json.dump(rep, open(OUT, "w"), indent=1)
for k, v in rep.items():
    print(k, {kk: vv for kk, vv in v.items() if kk != "profile"})
for w in ("DS", "GF", "XM"):
    print(w, "fit profile", [rep[f"fit_{w}"]["profile"][c] for c in (400, 360, 340, 320, 300, 280, 260, 240, 220, 200, 150)])
