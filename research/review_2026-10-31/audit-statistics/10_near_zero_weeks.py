"""Sensitivity: treat weeks / 30-day blocks whose |PnL| is below a small tolerance as inactive (excluded
from the positive-share denominators) and count A1 flips."""
import json
import numpy as np
from common import AS_OF, SCR, board, points
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums
from polyrea.workflows.screen import apply_criteria
res = json.load(open(f"{SCR}/a1_recomputed.json"))
rows = board(); names = {r["user_id"].lower(): (r["rank"], r["user_name"]) for r in rows}
ser = {}
for r in rows:
    w = r["user_id"].lower(); pts = points(w)
    if pts: ser[w] = daily_frame(pts, as_of=AS_OF)["d_economic_pnl"].iloc[1:]
for tol_w, tol_m in [(1e-9, 1e-9), (10, 100), (100, 1000), (1000, 5000)]:
    flips = []
    for w, d in ser.items():
        m = dict(res[w]); wk = weekly_sums(d); mb = np.array(monthly_blocks(d))
        if "error" in m or not apply_criteria(m): continue
        if np.any(np.abs(wk) > tol_w): m["share_positive_weeks"] = float(np.mean(wk[np.abs(wk) > tol_w] > 0))
        if np.any(np.abs(mb) > tol_m): m["share_positive_months"] = float(np.mean(mb[np.abs(mb) > tol_m] > 0))
        if not apply_criteria(m): flips.append(names[w])
    print(f"inactive if |week|<{tol_w}, |block|<{tol_m}: flips to pass {flips}")
