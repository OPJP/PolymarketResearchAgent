"""Iteration 14, X133 (panel iter12 information I12-4; own state, reported): is a BTC 5m window's entry side set by the
cluster's aggregate BTC exposure across its other open windows (5m, 15m, 4h)? Exposure at the entry = sum over other
open BTC windows (fills before the entry, end after it) of net Up - Down shares (BUY +, SELL -). Development folds:
BUILD 10-08..22, STUDY 10-23..26 (case level allowed), VALIDATE 10-27..30 (aggregate only)."""
import json, re
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[4]; C = ROOT / ".cache/re/directional-maker"
parts = []
for n in ("bosona", "almach", "momoney"):
    for p in (C / f"activity_{n}.parquet", C / "exam" / f"activity_{n}.parquet"):
        d = pd.read_parquet(p, columns=["timestamp", "type", "slug", "outcome", "side", "size", "price", "transactionHash", "asset"])
        parts.append(d)
D = pd.concat(parts, ignore_index=True)
D = D[(D.type == "TRADE")].drop_duplicates(subset=["transactionHash", "asset", "size", "price", "timestamp", "side"])
m = D.slug.str.extract(r"^btc-updown-(5m|15m|4h)-(\d+)$")
D = D[m[0].notna()].copy(); D["fam"] = m[0][m[0].notna()]; D["st"] = m[1][m[0].notna()].astype(np.int64)
D["end"] = D.st + D.fam.map({"5m": 300, "15m": 900, "4h": 14400})
D["d_up"] = np.where(D.outcome == "Up", 1.0, -1.0) * D["size"] * np.where(D.side == "BUY", 1.0, -1.0)
D = D.sort_values("timestamp", kind="stable")
ent = D[(D.fam == "5m") & (D.side == "BUY")].groupby("slug").first()
ts = D.timestamp.to_numpy(np.int64); en = D.end.to_numpy(np.int64); sl = D.slug.to_numpy(object); du = D.d_up.to_numpy()
rows = []
for slug, e in ent.iterrows():
    t = int(e.timestamp)
    msk = (ts < t) & (en > t) & (sl != slug)
    rows.append((slug, t, int(e.outcome == "Up"), float(du[msk].sum()), int(msk.sum())))
R = pd.DataFrame(rows, columns=["slug", "t", "up", "expo", "n_other"])
out = {}
for fo, (a, b) in (("build", (1791417600, 1792713600)), ("study", (1792713600, 1793059200)), ("validate_agg", (1793059200, 1793404800))):
    g = R[(R.t >= a) & (R.t < b)]; h = g[g.expo.abs() >= 10]
    out[fo] = {"entries": int(len(g)), "with_exposure_ge10": int(len(h)),
               "entry_offsets_exposure": float(((h.expo < 0) == (h.up == 1)).mean()) if len(h) else None,
               "entry_follows_exposure": float(((h.expo > 0) == (h.up == 1)).mean()) if len(h) else None,
               "big_exposure_ge500_offsets": float(((h[h.expo.abs() >= 500].expo < 0) == (h[h.expo.abs() >= 500].up == 1)).mean()) if (h.expo.abs() >= 500).any() else None,
               "n_big": int((h.expo.abs() >= 500).sum())}
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parent.parent / "results/iter14_agg_delta.json").write_text(json.dumps(out, indent=1))
