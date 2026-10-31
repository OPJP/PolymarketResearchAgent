"""Iteration 9: aggregate diagnostics of the block-clock side tables (BUILD, STUDY, VALIDATE aggregate only): accuracy of
R6's sigma (1.4 v300), the slow sigma (e1800, v3600; k 1) and the cheaper-side baseline by the age of the mid proxy, by
mid level and by day."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker/it9"
for split in ("build", "study", "validate"):
    D = pd.read_parquet(C / f"volhist_{split}.parquet")
    y = D.is_up.to_numpy() == 1
    x = np.log(D.S / D.K).to_numpy()
    st = np.sqrt(D.tau.to_numpy())
    m = D.mid_up.to_numpy()
    p = {"R6": norm.cdf(x / (1.4 * D.v300.to_numpy() * st)) > m, "e1800": norm.cdf(x / (D.e1800.to_numpy() * st)) > m,
         "v3600": norm.cdf(x / (D.v3600.to_numpy() * st)) > m, "cheaper": m < 0.5}
    ok = {k: v == y for k, v in p.items()}
    def show(lab, g):
        print(f"{split:8s} {lab:14s}", " ".join(f"{k}={np.mean(ok[k][g]):.3f}" for k in ok), f"n={g.sum()}")
    show("all", np.ones(len(D), bool))
    for lo, hi in ((0, 1), (2, 3), (4, 9), (10, 10**9)):
        show(f"age{lo}-{hi}", (D.age.to_numpy() >= lo) & (D.age.to_numpy() <= hi))
    fav = np.maximum(m, 1 - m)
    for lo, hi in ((0.5, 0.6), (0.6, 0.75), (0.75, 0.9), (0.9, 1.01)):
        show(f"fav{lo}-{hi}", (fav >= lo) & (fav < hi))
    sh = D.shares.to_numpy()
    show("shares>=100", sh >= 100)
    show("shares<100", sh < 100)
