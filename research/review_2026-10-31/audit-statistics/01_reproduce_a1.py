"""Recompute stage A1 for all 500 wallets from the cached series with the repo code and
compare to research/stage_a/stage_a1.json. Also checks the raw series (gaps, non-midnight
points, last day vs as_of, first-row level)."""
import collections
import json

import numpy as np

from common import AS_OF, SCR, board, points, stage_a1
from polyrea.analysis.pnl import daily_frame
from polyrea.stats import significance as S
from polyrea.workflows.screen import CRITERIA, apply_criteria, wallet_pnl_metrics

a1 = {r["wallet"]: r for r in stage_a1()["wallets"]}
rows = board()
wallets = [r["user_id"].lower() for r in rows]
res = {}
raw_info = {}
for w in wallets:
    pts = points(w)
    if pts is None:
        res[w] = {"history_days": 0, "error": "not cached"}
        continue
    res[w] = wallet_pnl_metrics(pts, AS_OF)
    ts = [p["timestamp"] for p in pts]
    mid = [t for t in ts if t % 86400 == 0 and t <= AS_OF]
    raw_info[w] = {
        "n_points": len(pts),
        "non_midnight": [t for t in ts if t % 86400],
        "gaps": collections.Counter((b - a) // 86400 for a, b in zip(mid, mid[1:])),
        "last_mid": max(mid) if mid else None,
        "first_level": next((p.get("economic_pnl") for p in pts if p["timestamp"] in mid[:1]), None),
    }

p_pre = [res[w].get("p_pre", 1.0) if res[w].get("pre_selection_days", 0) >= CRITERIA.min_pre_selection_days else 1.0 for w in wallets]
holm = S.holm_bonferroni(p_pre)
bh = S.benjamini_hochberg(p_pre)
for w, ph, pb in zip(wallets, holm, bh):
    res[w]["p_holm_pre"] = ph
    res[w]["p_bh_pre"] = pb
for w in wallets:
    if res[w].get("history_days", 0) > 0:
        df = daily_frame(points(w), as_of=AS_OF)
        res[w]["deflated_sharpe"] = S.deflated_sharpe_ratio(df["d_economic_pnl"].iloc[1:].to_numpy(), n_trials=len(rows))

mism = 0
keys = ["history_days", "pre_selection_days", "p_pre", "p_boot_pre", "p_holm_pre", "deflated_sharpe", "annual_sharpe", "last_30d_pnl", "median_month_pnl", "share_positive_weeks", "share_positive_months"]
passes = []
for w in wallets:
    m = res[w]
    reasons = apply_criteria(m) if "error" not in m else ["err"]
    if not reasons:
        passes.append(w)
    old = a1[w]["metrics"]
    for k in keys:
        a, b = m.get(k), old.get(k)
        if a is None and b is None:
            continue
        if a is None or b is None or not np.isclose(a, b, rtol=1e-9, atol=1e-12):
            mism += 1
            print("MISMATCH", w, k, a, b)
print("recomputed passes:", len(passes), "stored:", len(stage_a1()["evidence"]["derived"]["a1_pass"]), "same set:", set(passes) == set(stage_a1()["evidence"]["derived"]["a1_pass"]))
print("metric mismatches:", mism)

# raw series checks
nm = [w for w, r in raw_info.items() if len([t for t in r["non_midnight"] if t <= AS_OF]) > 0]
print("wallets with non-midnight points at or before as_of:", len(nm))
gappy = {w: dict(r["gaps"]) for w, r in raw_info.items() if any(k != 1 for k in r["gaps"])}
print("wallets with gaps between midnight points (gap_days->count):", len(gappy), list(gappy.items())[:10])
late = collections.Counter((AS_OF - r["last_mid"]) // 86400 for r in raw_info.values() if r["last_mid"])
print("days between last midnight point and as_of:", dict(late))
fl = [r["first_level"] for r in raw_info.values() if r["first_level"] is not None]
print("first midnight point economic_pnl: zero:", sum(1 for x in fl if x == 0), "nonzero:", sum(1 for x in fl if x != 0),
      "abs>10k:", sum(1 for x in fl if abs(x) > 1e4))
json.dump({w: {k: v for k, v in m.items() if k != "source"} for w, m in res.items()}, open(f"{SCR}/a1_recomputed.json", "w"), default=float)
