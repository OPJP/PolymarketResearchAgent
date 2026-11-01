"""Iteration 9: aggregate scale scan (k) of v300 and v3600 per split on the block-clock tables (VALIDATE aggregate only)."""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker/it9"
for split in ("build", "study", "validate"):
    D = pd.read_parquet(C / f"volhist_{split}.parquet")
    y = D.is_up.to_numpy() == 1
    x = np.log(D.S / D.K).to_numpy(); st = np.sqrt(D.tau.to_numpy()); m = D.mid_up.to_numpy()
    zm = norm.ppf(np.clip(m, 0.005, 0.995)); regA = np.sign(x) == np.sign(zm)
    line = []
    for nm in ("v300", "v3600"):
        for k in (0.5, 1.0, 1.4, 2.0, 3.0, 5.0):
            ok = (norm.cdf(x / (k * D[nm].to_numpy() * st)) > m) == y
            line.append(f"{nm}x{k}={ok.mean():.3f}/A{ok[regA].mean():.3f}")
    print(split, "regionD acc(sigma-free)=%.3f n=%d" % (((x > 0) == y)[~regA].mean(), (~regA).sum()), "underdog=%.3f" % ((m < 0.5) == y).mean())
    print("   ", " ".join(line))
