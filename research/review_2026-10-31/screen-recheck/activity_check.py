"""Part (2b): check leaderboard-vs-series disagreements against raw activity and
positions. For each wallet, over the leaderboard's ~30-day window:

* cash-flow PnL from /activity (own code): sells + redeems + merges + income
  (rebates, rewards, yield, conversions' cash) minus buys and splits;
* value change of the open book: value of positions held at window end
  (/positions currentValue, i.e. marked now) minus an estimate of the book at
  window start (positions with fills before the window that are still held or
  were closed inside the window are valued at their pre-window cost, which
  is a rough proxy);
* realized PnL of closed positions whose last activity falls in the window
  (/closed-positions realizedPnl).
Compared with the leaderboard figure and the user-pnl series' 30-day change.
Usage: activity_check.py <wallet> [<wallet> ...]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import AS_OF, OUT, REPO, load_a1, make_pm  # noqa: E402

D = 86400
lb = json.loads((REPO / "research/stage_a/leaderboard_snapshot.json").read_text())
LB_TS = lb["fetched_at"]
START = AS_OF - 30 * D
a1 = {w["wallet"]: w for w in load_a1()["wallets"]}
series = {r["wallet"]: r for r in json.loads((OUT / "lb_window.json").read_text())}
pm = make_pm()


def check(w: str) -> dict:
    rec = a1[w]
    act, srcs, cov = pm.activity(w, start=START, end=LB_TS)
    by_type = defaultdict(lambda: [0, 0.0])
    cash = 0.0
    big = []
    for r in act:
        t = r.get("type")
        usd = float(r.get("usdcSize") or 0.0)
        by_type[(t, r.get("side") or "")][0] += 1
        by_type[(t, r.get("side") or "")][1] += usd
        if t == "TRADE":
            cash += usd if r.get("side") == "SELL" else -usd
        elif t in ("REDEEM", "MERGE", "REWARD", "MAKER_REBATE", "YIELD", "CONVERSION", "REFERRAL_REWARD"):
            cash += usd
        elif t == "SPLIT":
            cash -= usd
        if usd > 50_000 and t != "TRADE":
            big.append({"type": t, "usdc": usd, "ts": r.get("timestamp"), "title": (r.get("title") or "")[:70]})
    closed, _ = pm.positions(w, closed=True, max_rows=3000)
    closed_in = [c for c in closed if START <= int(c.get("timestamp") or 0) <= LB_TS]
    realized_closed_in = float(sum(float(c.get("realizedPnl") or 0) for c in closed_in))
    openp, _ = pm.positions(w, closed=False, max_rows=5000)
    open_value = float(sum(float(p.get("currentValue") or 0) for p in openp))
    open_cashpnl = float(sum(float(p.get("cashPnl") or 0) for p in openp))
    out = {
        "wallet": w, "rank": rec["rank"], "name": rec["name"], "lb_pnl": rec["lb_pnl"], "lb_volume": rec["lb_volume"],
        "series_econ_30d": series[w]["economic_pnl|30d_complete"], "series_trade_30d_to_now": series[w]["trade_pnl|30d_to_now"],
        "series_all_time": series[w]["economic_pnl|all_time_to_now"],
        "activity_rows": len(act), "activity_coverage": getattr(cov, "status", str(cov)),
        "activity_by_type": {f"{k[0]}:{k[1]}": [v[0], round(v[1], 2)] for k, v in sorted(by_type.items())},
        "window_cash_flow": cash,
        "trade_volume_usdc": sum(v[1] for k, v in by_type.items() if k[0] == "TRADE"),
        "big_non_trade_rows": sorted(big, key=lambda b: -b["usdc"])[:8],
        "closed_positions_total": len(closed), "closed_positions_in_window": len(closed_in),
        "realized_pnl_closed_in_window": realized_closed_in,
        "closed_in_window_top": sorted(({"title": (c.get("title") or "")[:60], "realizedPnl": c.get("realizedPnl"), "avgPrice": c.get("avgPrice"),
                                          "totalBought": c.get("totalBought"), "ts": c.get("timestamp")} for c in closed_in),
                                        key=lambda c: -abs(float(c["realizedPnl"] or 0)))[:6],
        "open_positions": len(openp), "open_value_now": open_value, "open_cashPnl_now": open_cashpnl,
    }
    return out


if __name__ == "__main__":
    res = {}
    for arg in sys.argv[1:]:
        w = [k for k in a1 if k.startswith(arg.lower())][0]
        r = check(w)
        res[w] = r
        print(json.dumps(r, indent=1, default=float))
        print("-" * 80, flush=True)
    p = OUT / "activity_check.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    old.update(res)
    p.write_text(json.dumps(old, indent=1, default=float))
