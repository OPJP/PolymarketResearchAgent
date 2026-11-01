"""X225 step 4b (pre-registered in NOTES iteration 16): do the taker regime's sign moments (about 1.07 per round) sit at
round ends? Per map (iter16/taker_map_rows.parquet): round ends e_r = begin + delta + cumsum(d_i + G), bo3 round durations
d_i, G in {0, 5, 10, 15, 20} s, delta in [-180, +180] s on a 5-s grid, fitted per map to maximize snaps (a sign moment
within +-5 s of an end); the same fit with the reversed duration sequence (equal freedom). Clock iff snaps >= 1.5x the
reversed fit. Also the CV of within-map gaps between moments (>= 5 s) against the CV of round durations.
Output: results/taker_moment_clock.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
D = pd.read_parquet(OUT / "iter16/taker_map_rows.parquet")


def snaps(mom, begin, d, G, tol=5.0):
    best = (0, None)
    ends0 = np.cumsum(d + G)
    for delta in np.arange(-180, 181, 5.0):
        e = begin + delta + ends0
        j = np.searchsorted(mom, e)
        lo = np.abs(e - mom[np.clip(j - 1, 0, len(mom) - 1)])
        hi = np.abs(mom[np.clip(j, 0, len(mom) - 1)] - e)
        n = int((np.minimum(lo, hi) <= tol).sum())
        if n > best[0]:
            best = (n, delta)
    return best


tot, tot_rev, rows = 0, 0, []
cv_gap, cv_dur = [], []
for r in D.itertuples():
    mom = np.sort(np.array(json.loads(r.mom_ts), float))
    d = np.array(json.loads(r.round_dur), float)
    if len(mom) < 5 or len(d) < 13 or not np.all(d > 0):
        continue
    bt = max((snaps(mom, r.begin, d, G) + (G,) for G in (0, 5, 10, 15, 20)), key=lambda x: x[0])
    br = max((snaps(mom, r.begin, d[::-1].copy(), G) + (G,) for G in (0, 5, 10, 15, 20)), key=lambda x: x[0])
    tot += bt[0]
    tot_rev += br[0]
    g = np.diff(mom)
    g = g[g >= 5]
    if len(g) >= 5:
        cv_gap.append(float(np.std(g) / np.mean(g)))
    cv_dur.append(float(np.std(d) / np.mean(d)))
    rows.append({"cid": r.cid[:12], "rounds": int(len(d)), "moments": int(len(mom)), "snaps": bt[0], "snaps_rev": br[0], "G": bt[2], "delta": bt[1]})
R = pd.DataFrame(rows)
out = {"maps": int(len(R)), "rounds": int(R.rounds.sum()), "moments": int(R.moments.sum()), "snaps": int(tot), "snaps_reversed": int(tot_rev),
       "ratio": round(tot / max(tot_rev, 1), 3), "clock": bool(tot >= 1.5 * tot_rev),
       "share_rounds_snapped": round(tot / R.rounds.sum(), 3), "share_rounds_snapped_reversed": round(tot_rev / R.rounds.sum(), 3),
       "cv_gap_median": round(float(np.median(cv_gap)), 3) if cv_gap else None, "cv_round_duration_median": round(float(np.median(cv_dur)), 3),
       "maps_ratio_gt_1": round(float((R.snaps > R.snaps_rev).mean()), 3), "maps_ratio_lt_1": round(float((R.snaps < R.snaps_rev).mean()), 3),
       "G_counts": R.G.value_counts().to_dict()}
(RES / "taker_moment_clock.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))
