"""X212 historical form (freeze-time refractory test on the filled record): rate per second of its dark new-high
decisions (dark_newhigh.py definition) and of all V-changes in the restart + freeze window (a + 2, a + 20] s after the
print-anchored end a of the previous round, against the action window (a + 30, z - 5], over the 412 print-clock rounds of
decided_early.py; plus the signed 60-s markout of the dark new highs in each window. K (in-round events only) predicts a
much lower informed rate in the freeze window; information about economy or buys (or a late round-end message) would
not. Clock noise (snaps 1.30x placebo) blurs the windows. Output: results/freeze_rate.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
D = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/iter15/decided_early_rows_print.parquet")
D = D[(D.z - D.a) >= 50]
d = pd.read_parquet(SP).sort_values(["tok", "t"])
pm = d.groupby("tok").top.transform(lambda x: x.shift(1).rolling(3, min_periods=1).max())
d["new_high"] = (d.dtop > 0) & (d.top > pm + 1e-9)
d["ts"] = d.t / 1000.0
out = {"rounds": int(len(D))}
acc = {k: {"n": 0, "secs": 0.0, "m60": []} for k in ("freeze_dark_nh", "action_dark_nh", "freeze_all", "action_all", "freeze_visible", "action_visible")}
for r in D.itertuples():
    x = d[d.cid == r.cid]
    for win, lo, hi in (("freeze", r.a + 2, r.a + 20), ("action", r.a + 30, r.z - 5)):
        if hi <= lo:
            continue
        m = (x.ts > lo) & (x.ts <= hi)
        for nm, mm in (("dark_nh", m & (x.vis == "dark") & x.new_high), ("all", m), ("visible", m & (x.vis == "visible_agree"))):
            k = f"{win}_{nm}"
            acc[k]["n"] += int(mm.sum())
            acc[k]["secs"] += hi - lo
            if nm == "dark_nh":
                acc[k]["m60"] += list(x.loc[mm, "m60"].to_numpy(float))
for k, v in acc.items():
    out[k] = {"n": v["n"], "rate_per_min": round(60 * v["n"] / max(v["secs"], 1e-9), 3)}
    if v["m60"]:
        a = np.array(v["m60"])
        out[k].update({"m60_c": round(float(a.mean()), 2), "up": round(float((a > 0).mean()), 3), "down": round(float((a < 0).mean()), 3)})
for nm in ("dark_nh", "all", "visible"):
    f, a = out[f"freeze_{nm}"]["rate_per_min"], out[f"action_{nm}"]["rate_per_min"]
    out[f"ratio_freeze_over_action_{nm}"] = round(f / a, 3) if a else None
(RES / "freeze_rate.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
