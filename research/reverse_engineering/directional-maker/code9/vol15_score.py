"""Iteration 9: score H-VOL15 (pre-registered: v3600 k1 vs frozen 1.4 x v300) on the BTC 15m block-clock tables; BUILD and
STUDY with a lookback scan, VALIDATE aggregate with the 2-h block bootstrap of the gain."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker/it9"
out = {}
for sp_ in ("build", "study", "validate"):
    D = pd.read_parquet(C / f"volhist15_{sp_}.parquet")
    y = D.is_up.to_numpy() == 1; x = np.log(D.S / D.K).to_numpy(); m = D.mid_up.to_numpy(); st = np.sqrt(D.tau.to_numpy())
    ok0 = (norm.cdf(x / (1.4 * D.v300.to_numpy() * st)) > m) == y
    ok1 = (norm.cdf(x / (D.v3600.to_numpy() * st)) > m) == y
    rec = {"n": int(len(D)), "frozen": round(float(ok0.mean()), 4), "v3600k1": round(float(ok1.mean()), 4), "cheaper": round(float(np.mean((m < 0.5) == y)), 4)}
    if sp_ != "validate":
        rec["scan_k1"] = {f"v{L}": round(float(np.mean((norm.cdf(x / (D[f"v{L}"].to_numpy() * st)) > m) == y)), 4) for L in (300, 900, 1800, 3600, 7200)}
    blk = D.b.to_numpy() // 7200
    u, inv = np.unique(blk, return_inverse=True)
    s1 = np.bincount(inv, ok1.astype(float)); s0 = np.bincount(inv, ok0.astype(float)); cn = np.bincount(inv)
    rng = np.random.default_rng(7); g = []
    for _ in range(2000):
        idx = rng.integers(0, len(u), len(u)); g.append((s1[idx].sum() - s0[idx].sum()) / cn[idx].sum())
    rec["gain"] = round(float(ok1.mean() - ok0.mean()), 4)
    rec["gain_ci95"] = [round(float(np.quantile(g, 0.025)), 4), round(float(np.quantile(g, 0.975)), 4)]
    rec["p_gain_le_0"] = round(float(np.mean(np.array(g) <= 0)), 4)
    out[sp_] = rec
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "iter9_vol15.json").write_text(json.dumps(out, indent=1))
