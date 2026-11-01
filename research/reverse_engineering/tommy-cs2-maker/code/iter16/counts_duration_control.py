"""Robustness of X226 / X225 (iteration 16): add log(map duration) to the per-map count models, so that a count that is
proportional to time (a Poisson process at a constant rate, CV of gaps about 1 as in taker_moment_clock.json) cannot
pose as a round-count effect. Output: results/counts_duration_control.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
out = {}
for nm, f, ycols in (("maker_X226", "iter16/map_counts_rows.parquet", ["n_all", "n_large", "n_small"]),
                     ("taker_X225", "iter16/taker_map_rows.parquet", ["moments"])):
    D = pd.read_parquet(OUT / f)
    if "orders" in D and nm.startswith("taker"):
        D = D[D.orders > 0]
    D = D[(D.dur > 600) & (D.dur < 7200)].copy()
    D["kpr_c"] = D.kills / D.rounds - (D.kills / D.rounds).mean()
    D["ppr_c"] = D.plants / D.rounds - (D.plants / D.rounds).mean()
    D["l_rounds"] = np.log(D.rounds)
    D["l_dur"] = np.log(D.dur)
    o = {"maps": int(len(D)), "corr_log_rounds_log_dur": round(float(np.corrcoef(D.l_rounds, D.l_dur)[0, 1]), 3)}
    for y in ycols:
        for spec, xs in (("dur_and_rounds", ["l_rounds", "l_dur", "kpr_c", "ppr_c"]), ("dur_only", ["l_dur", "kpr_c", "ppr_c"])):
            X = sm.add_constant(D[xs].astype(float))
            try:
                m = sm.NegativeBinomial(D[y].astype(float), X).fit(disp=0, maxiter=300)
            except Exception:  # noqa: BLE001
                m = sm.GLM(D[y].astype(float), X, family=sm.families.Poisson()).fit(cov_type="HC1")
            o[f"{y}|{spec}"] = {k: {"coef": round(float(m.params[k]), 3), "se": round(float(m.bse[k]), 3), "p": round(float(m.pvalues[k]), 4)} for k in xs}
    out[nm] = o
(RES / "counts_duration_control.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
