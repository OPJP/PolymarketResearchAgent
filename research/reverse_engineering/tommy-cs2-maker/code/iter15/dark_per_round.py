"""X211 step 3 (per-round count): informed dark moments per round against the round's kills. Rounds = the print-anchored
clock rows of decided_early.py (both ends snapped; bo3 deaths per side); decisions = dark new-high V-changes of
dark_newhigh.py on the same map book inside (e_{r-1} + 10, e_r + 4]. Poisson GLM: count ~ log(round length) offset +
total deaths (and, separately, the loser's deaths), map-clustered SEs. K predicts a positive kills coefficient; R none.
Output: results/dark_per_round.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[5]
SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
D = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/iter15/decided_early_rows_print.parquet")
d = pd.read_parquet(SP).sort_values(["tok", "t"])
pm = d.groupby("tok").top.transform(lambda x: x.shift(1).rolling(3, min_periods=1).max())
d["new_high"] = (d.dtop > 0) & (d.top > pm + 1e-9)
dk = d[(d.vis == "dark") & d.new_high]
allv = d  # every V-change decision, for a second count
D = D[D.ct_dead.notna() & D.t_dead.notna() & D.a.notna()].copy()
cnt, cnt_all = [], []
for r in D.itertuples():
    x = dk[dk.cid == r.cid]
    tt = x.t.to_numpy(float) / 1000.0
    cnt.append(int(((tt > r.a + 10) & (tt <= r.z + 4)).sum()))
    y = allv[allv.cid == r.cid].t.to_numpy(float) / 1000.0
    cnt_all.append(int(((y > r.a + 10) & (y <= r.z + 4)).sum()))
D["n_dark"] = cnt
D["n_all"] = cnt_all
D["deaths"] = D.ct_dead + D.t_dead
cw = D.end_reason.isin(["CTWin", "BombDefused", "TargetSaved"])
D["loser_deaths"] = np.where(cw, D.t_dead, D.ct_dead)
D["winner_deaths"] = np.where(cw, D.ct_dead, D.t_dead)
out = {"rounds": int(len(D)), "mean_dark_new_high_per_round": round(float(D.n_dark.mean()), 3), "mean_all_vchanges_per_round": round(float(D.n_all.mean()), 3)}
for ycol in ("n_dark", "n_all"):
    for xs in (["deaths"], ["winner_deaths", "loser_deaths"]):
        X = sm.add_constant(D[xs].astype(float))
        try:
            m = sm.GLM(D[ycol].astype(float), X, family=sm.families.Poisson(), offset=np.log(D.len.astype(float))).fit(
                cov_type="cluster", cov_kwds={"groups": pd.factorize(D.cid)[0]})
            out[f"{ycol}~{'+'.join(xs)}"] = {k: {"coef": round(float(m.params[k]), 4), "se": round(float(m.bse[k]), 4), "p": round(float(m.pvalues[k]), 4)} for k in xs}
        except Exception as e:  # noqa: BLE001
            out[f"{ycol}~{'+'.join(xs)}"] = repr(e)[:120]
(RES / "dark_per_round.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
