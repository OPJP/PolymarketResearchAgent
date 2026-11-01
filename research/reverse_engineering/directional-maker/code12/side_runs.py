"""Iteration 12, X129 (own): the side per fill run. A run = consecutive cluster BTC 5m maker BUY fills of one window on one
outcome (all three wallets, ordered by block second) with no fill on the other outcome in between. Each run is scored once,
at its first fill, with the public R8 side (decided window -> cheaper token, else the Chainlink posture) and the baselines
(cheaper token; the previous run's outcome = own history). STUDY case by case, VALIDATE aggregate.
    python code12/side_runs.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"


def main():
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet").sort_values(["cid", "b"], kind="stable").reset_index(drop=True)
    mid = V.mid_up.to_numpy()
    post = np.where(np.isfinite(V.f_cl) & np.isfinite(mid), V.f_cl > mid, V.f_bn > mid)
    dec = np.abs(mid - 0.5) > 0.4
    pub = np.where(dec, mid < 0.5, post)
    y = (V.is_up == 1).to_numpy()
    cid = V.cid.to_numpy()
    new_run = np.ones(len(V), dtype=bool)
    new_run[1:] = (cid[1:] != cid[:-1]) | (y[1:] != y[:-1])
    run_id = np.cumsum(new_run)
    first_in_window = np.ones(len(V), dtype=bool)
    first_in_window[1:] = cid[1:] != cid[:-1]
    prev_run_up = np.full(len(V), -1)
    prev_run_up[1:] = np.where(cid[1:] == cid[:-1], y[:-1].astype(int), -1)
    out = {}
    for sp in ("study", "validate"):
        ms = (V.sp == sp).to_numpy() & np.isfinite(mid)
        r0 = ms & new_run
        sizes = pd.Series(run_id[ms]).value_counts()
        rec = {"fills": int(ms.sum()), "runs": int(r0.sum()), "mean_fills_per_run": round(float(sizes.mean()), 3),
               "public_per_fill": round(float((pub == y)[ms].mean()), 4), "public_per_run": round(float((pub == y)[r0].mean()), 4),
               "cheaper_per_run": round(float(((mid < 0.5) == y)[r0].mean()), 4),
               "posture_per_run": round(float((post == y)[r0].mean()), 4),
               "public_first_run_of_window": round(float((pub == y)[r0 & first_in_window].mean()), 4),
               "public_later_runs": round(float((pub == y)[r0 & ~first_in_window].mean()), 4),
               "n_later_runs": int((r0 & ~first_in_window).sum())}
        # a later run is by construction on the outcome opposite to the previous run: own-history-by-run = 0
        rec["note"] = "later runs always switch outcome (that is what starts a run), so 'same as previous run' scores 0 by construction"
        out[sp] = rec
    (HERE.parent / "results" / "iter12_side_runs.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
