"""Part (2a): which window/field of the user-pnl series reproduces the leaderboard's
monthly PnL? Tests each candidate on all 500 wallets (cached bodies, read-only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import AS_OF, OUT, REPO, RepoCacheRO, load_a1, user_pnl_url  # noqa: E402

a1 = load_a1()
lb = json.loads((REPO / "research/stage_a/leaderboard_snapshot.json").read_text())
LB_TS = lb["fetched_at"]
rc = RepoCacheRO()
D = 86400
FIELDS = ["economic_pnl", "trade_pnl", "position_pnl", "realized_pnl", "settled_pnl", "realized_market_pnl"]


def level_at(pts, ts, field):
    """Cumulative level at the last point stamped <= ts (0 before the series starts)."""
    v = 0.0
    for p in pts:
        if int(p["timestamp"]) <= ts and p.get(field) is not None:
            v = float(p[field])
        elif int(p["timestamp"]) > ts:
            break
    return v


rows = []
for w in a1["wallets"]:
    pts = sorted(((json.loads(rc.get_raw(user_pnl_url(w["wallet"]))[1]) or {}).get("data") or {}).get("points") or [],
                 key=lambda p: int(p["timestamp"]))
    if not pts:
        continue
    now_ts = int(pts[-1]["timestamp"])
    r = {"wallet": w["wallet"], "rank": w["rank"], "name": w["name"], "lb": float(w["lb_pnl"] or 0),
         "partial_ts": now_ts, "first_ts": int(pts[0]["timestamp"]),
         "inconsistent": bool(w["metrics"].get("lb_series_inconsistent"))}
    for f in FIELDS:
        r[f"{f}|30d_complete"] = level_at(pts, AS_OF, f) - level_at(pts, AS_OF - 30 * D, f)
        r[f"{f}|30d_to_now"] = level_at(pts, now_ts, f) - level_at(pts, AS_OF - 30 * D, f)
        r[f"{f}|29d_to_now"] = level_at(pts, now_ts, f) - level_at(pts, AS_OF - 29 * D, f)
        r[f"{f}|31d_to_now"] = level_at(pts, now_ts, f) - level_at(pts, AS_OF - 31 * D, f)
        r[f"{f}|cal_oct_to_now"] = level_at(pts, now_ts, f) - level_at(pts, 1790812800, f)  # 2026-10-01 00:00 UTC
        r[f"{f}|all_time_to_now"] = level_at(pts, now_ts, f)
    rows.append(r)

keys = [k for k in rows[0] if "|" in k]
lbv = np.array([r["lb"] for r in rows])
summ = []
for k in keys:
    v = np.array([r[k] for r in rows])
    gap = lbv - v
    ok = np.abs(gap) <= np.maximum(25_000, 0.25 * np.abs(lbv))
    close = np.abs(gap) <= np.maximum(1_000, 0.02 * np.abs(lbv))
    summ.append((k, int(ok.sum()), int(close.sum()), float(np.median(np.abs(gap)))))
summ.sort(key=lambda t: -t[1])
print(f"wallets with a series: {len(rows)}; leaderboard fetched {LB_TS} (as_of {AS_OF}); median partial point lag vs lb fetch: "
      f"{np.median([LB_TS - r['partial_ts'] for r in rows]) / 3600:.1f} h")
print("candidate | consistent (project band) | within 2%/$1k | median |gap|")
for s in summ:
    print(f"  {s[0]:40s} {s[1]:4d} {s[2]:4d} {s[3]:12,.0f}")
(OUT / "lb_window.json").write_text(json.dumps(rows, indent=0))
