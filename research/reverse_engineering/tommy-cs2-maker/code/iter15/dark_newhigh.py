"""X211 step 1 (simplified censoring-free label): among the mechanics panel's E3-1 decision split (scratchpad
m14/dark_split.parquet, 16-22 Oct, development), keep only RISING tops that set a new high against the previous three
burst tops on the token (a refill-then-return cannot do that), and compare their signed clean-print markouts (decision
direction, cents) with all dark decisions, dark falling tops and visible-agree decisions, by period. Output:
results/dark_newhigh.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
d = pd.read_parquet(SP).sort_values(["tok", "t"])
prev_max = d.groupby("tok").top.transform(lambda x: x.shift(1).rolling(3, min_periods=1).max())
prev_min = d.groupby("tok").top.transform(lambda x: x.shift(1).rolling(3, min_periods=1).min())
# the previous tops of a decision's own token: d.top is the new top; d.dtop the change from the previous burst top
d["new_high"] = (d.dtop > 0) & (d.top > prev_max + 1e-9)
d["new_low"] = (d.dtop < 0) & (d.top < prev_min - 1e-9)
out = {}
for per in ("BUILD", "VALIDATE"):
    x = d[d.period == per]
    o = {}
    for name, m in (("dark_all", x.vis == "dark"), ("dark_up", (x.vis == "dark") & (x.dtop > 0)), ("dark_down", (x.vis == "dark") & (x.dtop < 0)),
                    ("dark_new_high", (x.vis == "dark") & x.new_high), ("dark_new_low", (x.vis == "dark") & x.new_low),
                    ("visible_agree", x.vis == "visible_agree"), ("visible_agree_new_high", (x.vis == "visible_agree") & x.new_high)):
        y = x[m]
        o[name] = {"n": int(len(y)), "m10_c": round(float(y.m10.mean()), 2), "m60_c": round(float(y.m60.mean()), 2),
                   "share_up60": round(float((y.m60 > 0).mean()), 3), "share_down60": round(float((y.m60 < 0).mean()), 3)}
    out[per] = o
(RES / "dark_newhigh.json").write_text(json.dumps(out, indent=1))
for per, o in out.items():
    print(per, {k: (v["n"], v["m10_c"], v["m60_c"], v["share_up60"], v["share_down60"]) for k, v in o.items()})
