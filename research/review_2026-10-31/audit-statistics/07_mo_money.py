"""mo-money (rank 242): fails A1 only on positive weeks / positive 30-day blocks. Show why."""
import json
import numpy as np
from common import AS_OF, SCR, board, points
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums
from polyrea.workflows.screen import apply_criteria

rows = {r["user_name"]: r["user_id"].lower() for r in board()}
w = rows["mo-money"]
res = json.load(open(f"{SCR}/a1_recomputed.json"))[w]
d = daily_frame(points(w), as_of=AS_OF)["d_economic_pnl"].iloc[1:]
print("wallet", w, "history", res["first_day"], "->", res["last_day"], "days", len(d))
a = d.to_numpy()
nz = np.flatnonzero(np.abs(a) > 1e-9)
print("first non-zero day index", nz[0], "date", d.index[nz[0]].date(), "; exact-zero days total", int(np.sum(np.abs(a) < 1e-9)))
wk = weekly_sums(d); mb = monthly_blocks(d)
print("weekly sums (oldest first):", np.round(wk).astype(int).tolist())
print("30-day blocks (recent first):", np.round(mb).astype(int).tolist())
print("share_positive_weeks stored", res["share_positive_weeks"], " excluding exact-zero weeks", np.mean(wk[np.abs(wk) > 1e-9] > 0))
print("share_positive_months stored", res["share_positive_months"], " excluding exact-zero blocks", np.mean(np.array(mb)[np.abs(mb) > 1e-9] > 0))
# trimming leading inactivity (series starts at first non-zero day)
d2 = d.iloc[nz[0]:]
wk2 = weekly_sums(d2); mb2 = monthly_blocks(d2)
print("after trimming leading zeros: weeks", len(wk2), "share pos", np.mean(wk2 > 0), "| blocks", len(mb2), "share pos", np.mean(np.array(mb2) > 0))
print("A1 reasons:", apply_criteria(res))
print({k: res[k] for k in ("pre_selection_days", "p_pre", "p_holm_pre", "p_boot_pre", "deflated_sharpe", "annual_sharpe", "last_30d_pnl", "median_month_pnl")})
