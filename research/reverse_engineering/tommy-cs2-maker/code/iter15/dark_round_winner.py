"""X211 step 2(a): do its dark mid-round decisions point to the winner of the round in progress beyond the previous
round's result? Print-clock rounds of decided_early.py; decisions of the mechanics panel's split (dark new highs, all dark,
visible-agree) inside the mid-round window (a + 30, z - 1] (after the restart window, before the round's own anchor).
Agreement of the decision's team-A direction with the round's winner and with the previous round's winner; logistic
direction ~ current winner + previous winner, map-clustered. Output: results/dark_round_winner.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[5]
SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
import os
ANCHOR = os.environ.get("TOMMY_CLOCK_ANCHOR", "print")
D = pd.read_parquet(ROOT / f".cache/re/tommy-cs2-maker/iter15/decided_early_rows_{ANCHOR}.parquet")
D = D[(D.z - D.a) >= 45]
d = pd.read_parquet(SP).sort_values(["tok", "t"])
pm = d.groupby("tok").top.transform(lambda x: x.shift(1).rolling(3, min_periods=1).max())
d["new_high"] = (d.dtop > 0) & (d.top > pm + 1e-9)
d["ts"] = d.t / 1000.0
rows = []
for r in D.itertuples():
    x = d[d.cid == r.cid]
    m = (x.ts > r.a + 30) & (x.ts <= r.z - 1)
    for sg, vis, nh, per in zip(x.sign[m], x.vis[m], x.new_high[m], x.period[m]):
        rows.append({"sign": float(sg), "vis": vis, "nh": bool(nh), "cur": 1.0 if r.A_won == 1 else -1.0,
                     "prev": 1.0 if r.A_won_prev == 1 else -1.0, "cid": r.cid, "period": per})
X = pd.DataFrame(rows)
out = {"rounds": int(len(D)), "decisions": int(len(X))}
for nm, m in (("dark_new_high", (X.vis == "dark") & X.nh), ("dark_all", X.vis == "dark"), ("visible_agree", X.vis == "visible_agree")):
    for per in ("ALL", "BUILD", "VALIDATE"):
        y = X[m & ((X.period == per) if per != "ALL" else True)]
        if len(y) < 20:
            continue
        o = {"n": int(len(y)), "agree_cur": round(float((y["sign"] == y["cur"]).mean()), 3), "agree_prev": round(float((y["sign"] == y["prev"]).mean()), 3),
             "agree_cur_when_cur_ne_prev": round(float((y["sign"] == y["cur"])[y["cur"] != y["prev"]].mean()), 3), "n_cur_ne_prev": int((y["cur"] != y["prev"]).sum())}
        try:
            Z = sm.add_constant(y[["cur", "prev"]])
            mod = sm.Logit((y["sign"] > 0).astype(float), Z).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(y.cid)[0]})
            o["logit"] = {k: {"coef": round(float(mod.params[k]), 3), "p": round(float(mod.pvalues[k]), 4)} for k in ("cur", "prev")}
        except Exception as e:  # noqa: BLE001
            o["logit"] = repr(e)[:80]
        out[f"{nm}_{per}"] = o
(RES / ("dark_round_winner.json" if ANCHOR == "print" else f"dark_round_winner_{ANCHOR}.json")).write_text(json.dumps(out, indent=1))
for k, v in out.items():
    if isinstance(v, dict):
        print(k, v["n"], "cur", v["agree_cur"], "prev", v["agree_prev"], "cur|cur!=prev", v["agree_cur_when_cur_ne_prev"], v["n_cur_ne_prev"], v["logit"])
