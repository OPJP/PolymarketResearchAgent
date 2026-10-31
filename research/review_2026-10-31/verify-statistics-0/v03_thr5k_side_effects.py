"""Why does a $5k trim threshold flip GoodFallen out and CrouchPredictions in?"""
import gzip, json, sys
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path("/home/user/PolymarketResearchAgent"); sys.path.insert(0, str(REPO))
from polyrea.workflows import screen as SC
from polyrea.analysis.pnl import daily_frame, weekly_sums, monthly_blocks
OUT = Path(__file__).parent
blob = json.load(gzip.open(OUT / "points.json.gz", "rt")); as_of, points = blob["as_of"], blob["points"]
a1 = json.loads((REPO / "research/stage_a/stage_a1.json").read_text())
byname = {r["name"]: r for r in a1["wallets"]}
for nm in ["GoodFallen", "CrouchPredictions", "mo-money"]:
    r = byname[nm]; m = r["metrics"]
    d = daily_frame(points[r["wallet"]], as_of=as_of)["d_economic_pnl"].iloc[1:]
    run = d.abs().cumsum().to_numpy()
    k1 = int(np.nonzero(run > 1000)[0][0]); k5 = int(np.nonzero(run > 5000)[0][0])
    print(nm, "rank", r["rank"], "stored reasons:", r["stage_a1_reasons"])
    print("   history", len(d), "pre", m["pre_selection_days"], "trim@1k", k1, "trim@5k", k5, "first days:", [round(x) for x in d.iloc[:k5+3]])
    print("   weekly (oldest first):", [round(x) for x in weekly_sums(d)][:12], "... n=", len(weekly_sums(d)), " zero weeks:", int((weekly_sums(d)==0).sum()))
