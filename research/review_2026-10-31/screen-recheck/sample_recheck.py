"""Part (1): near misses (exactly one failed check) + 20 random other rejected
wallets (numpy default_rng(SEED)). Re-download user-pnl fresh (scratch cache,
network), compare with the cached body the screen used, recompute metrics."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import AS_OF, OUT, RepoCacheRO, daily_pnl, hac_t, holm, load_a1, make_pm, reason_codes, reasons, screen_metrics, stationary_bootstrap_p, user_pnl_url  # noqa: E402

SEED = 20261030
a1 = load_a1()
W = a1["wallets"]
near = [w for w in W if len(w["stage_a1_reasons"]) == 1]
others = sorted([w for w in W if len(w["stage_a1_reasons"]) >= 2], key=lambda r: r["rank"])
rng = np.random.default_rng(SEED)
pick = sorted(rng.choice(len(others), 20, replace=False).tolist())
rand = [others[i] for i in pick]
sample = near + rand
print("near misses:", len(near), "random:", [r["rank"] for r in rand])

allrows = json.loads((OUT / "recheck_all.json").read_text())  # cached-body recompute (for Holm over 500)
wallets = [w["wallet"] for w in W]
pm = make_pm(fresh_only=True)
rc = RepoCacheRO()
out = []
for w in sample:
    addr = w["wallet"]
    body, src = pm.user_pnl(addr)
    raw_new = json.dumps(body, sort_keys=True)
    pts_new = body.get("points") or []
    old = rc.get_raw(user_pnl_url(addr))
    pts_old = ((json.loads(old[1]) or {}).get("data") or {}).get("points") or []
    d_new, x_new = daily_pnl(pts_new)
    d_old, x_old = daily_pnl(pts_old)
    same_days = len(x_new) == len(x_old) and (len(x_new) == 0 or (d_new[0] == d_old[0]))
    maxdiff = float(np.max(np.abs(x_new - x_old))) if same_days and len(x_new) else None
    rec = {
        "wallet": addr, "rank": w["rank"], "name": w["name"], "group": "near" if w in near else "random",
        "recorded_reasons": reason_codes(w["stage_a1_reasons"]),
        "fresh_points": len(pts_new), "cached_points": len(pts_old),
        "fresh_fetched_at": src.fetched_at, "fresh_cached": src.cached,
        "daily_series_identical_to_cached": bool(same_days and (maxdiff is None or maxdiff < 1e-6)),
        "max_abs_daily_diff_vs_cached": maxdiff,
        "fresh_days": len(x_new), "cached_days": len(x_old),
    }
    if len(x_new):
        m = screen_metrics(x_new, n_boot=20000)
        # Holm: substitute this wallet's fresh p into the cached-body p vector of all 500
        pv = [allrows[v]["m"]["p_pre"] if allrows[v].get("m", {}).get("pre_days", 0) >= 60 else 1.0 for v in wallets]
        i = wallets.index(addr)
        pv[i] = m["p_pre"] if m["pre_days"] >= 60 else 1.0
        ph = float(holm(pv)[i])
        m["p_holm"] = ph
        rec["fresh_metrics"] = m
        rec["fresh_reasons"] = reasons(m, ph)
        rm = w["metrics"]
        rec["recorded"] = {k: rm.get(k) for k in ("pre_selection_days", "p_pre", "p_holm_pre", "p_boot_pre", "deflated_sharpe",
                                                   "last_30d_pnl", "median_month_pnl", "share_positive_months", "annual_sharpe",
                                                   "share_positive_weeks", "lb_series_inconsistent", "lb_vs_series_gap")}
        # robustness of the near-miss checks
        if w in near and m["pre_days"] >= 5:
            pre = x_new[: m["pre_days"]]
            rec["robust"] = {
                "p_pre_by_lag": {L: hac_t(pre, L)[1] for L in (1, 2, 5, 10, 20)},
                "p_boot_by_block": {b: stationary_bootstrap_p(pre, 20000, b) for b in (2, 5, 10, 20)},
                "holm_multiplier_needed": None,
            }
    else:
        rec["fresh_reasons"] = ["no history"]
    rec["fresh_vs_recorded_reasons_agree"] = sorted(rec["fresh_reasons"]) == sorted(rec["recorded_reasons"])
    out.append(rec)
    print(w["rank"], addr[:10], w["name"][:20] if w["name"] else "", rec["recorded_reasons"], "| fresh:", rec["fresh_reasons"],
          "| identical:", rec["daily_series_identical_to_cached"], rec["fresh_days"], rec["cached_days"])

(OUT / "sample_recheck.json").write_text(json.dumps({"seed": SEED, "rows": out}, indent=1, default=float))
