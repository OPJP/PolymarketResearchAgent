"""Finding-21 follow-up: what do its moves in the restart / buy window point to? For each print-clock round r (rows of
decided_early.py with bo3 equipment values of round r), its V-change decisions (and dark new highs, and visible informed
takes) in (a + 2, a + 20] s after the anchored end a of round r - 1: share whose team-A direction agrees with (1) the
winner of round r - 1 (a late round-end repricing), (2) the team with the higher equipment value in round r (buy-phase
information), (3) the winner of round r; and a logistic regression of the direction on (1) and (2). Same in the action
window for reference. Output: results/freeze_direction.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[5]
SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
D = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/iter15/decided_early_rows_print.parquet")
D = D[(D.z - D.a) >= 50 & D.eqA.notna() & D.eqB.notna()] if False else D[((D.z - D.a) >= 50) & D.eqA.notna() & D.eqB.notna()]
d = pd.read_parquet(SP).sort_values(["tok", "t"])
pm = d.groupby("tok").top.transform(lambda x: x.shift(1).rolling(3, min_periods=1).max())
d["new_high"] = (d.dtop > 0) & (d.top > pm + 1e-9)
d["ts"] = d.t / 1000.0
rows = []
for r in D.itertuples():
    x = d[d.cid == r.cid]
    eqd = np.sign(r.eqA - r.eqB)
    for win, lo, hi in (("freeze", r.a + 2, r.a + 20), ("action", r.a + 30, r.z - 5)):
        m = (x.ts > lo) & (x.ts <= hi)
        for t_, sg, vis, nh in zip(x.ts[m], x.sign[m], x.vis[m], x.new_high[m]):
            rows.append({"win": win, "sign": float(sg), "vis": vis, "nh": bool(nh), "prev": 1.0 if r.A_won_prev == 1 else -1.0,
                         "eq": float(eqd), "cur": 1.0 if r.A_won == 1 else -1.0, "cid": r.cid, "eq_gap_k": float(r.eqA - r.eqB) / 1000.0})
X = pd.DataFrame(rows)
out = {"rounds": int(len(D)), "decisions": int(len(X))}
for win in ("freeze", "action"):
    for nm, m in (("all", np.ones(len(X), bool)), ("dark_new_high", (X.vis == "dark") & X.nh), ("visible_agree", X.vis == "visible_agree")):
        y = X[(X.win == win) & m & (X["eq"] != 0)]
        if len(y) < 10:
            continue
        o = {"n": int(len(y)), "agree_prev_winner": round(float((y.sign == y.prev).mean()), 3), "agree_equipment": round(float((y["sign"] == y["eq"]).mean()), 3),
             "agree_round_winner": round(float((y.sign == y.cur).mean()), 3),
             "agree_equipment_when_prev_disagrees": round(float((y["sign"] == y["eq"])[y["prev"] != y["eq"]].mean()), 3) if (y["prev"] != y["eq"]).any() else None,
             "n_prev_disagrees_eq": int((y["prev"] != y["eq"]).sum())}
        try:
            Z = sm.add_constant(y[["prev", "eq"]])
            mod = sm.Logit((y.sign > 0).astype(float), Z).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(y.cid)[0]})
            o["logit"] = {k: {"coef": round(float(mod.params[k]), 3), "p": round(float(mod.pvalues[k]), 4)} for k in ("prev", "eq")}
        except Exception as e:  # noqa: BLE001
            o["logit"] = repr(e)[:100]
        out[f"{win}_{nm}"] = o
(RES / "freeze_direction.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
