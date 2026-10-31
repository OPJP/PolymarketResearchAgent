"""Part (3b): dormant stretches (no trades) count as non-positive weeks/months
in the screen. Re-run the full screen (own code, all thresholds unchanged,
including the 60-day pre-selection rule) on each wallet's last activity spell:
history starts after the last run of >= GAP consecutive days with zero trades
and zero PnL. Holm over all 500."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RepoCacheRO, daily_pnl, holm, load_a1, reason_codes, reasons, screen_metrics, stationary_bootstrap_p, user_pnl_url  # noqa: E402

GAP = 30
a1 = load_a1()
WR = a1["wallets"]
W = [w["wallet"] for w in WR]
rec = {w["wallet"]: w for w in WR}
rc = RepoCacheRO()
M = {}
info = {}
for w in W:
    pts = ((json.loads(rc.get_raw(user_pnl_url(w))[1]) or {}).get("data") or {}).get("points") or []
    _, x = daily_pnl(pts)
    _, tc = daily_pnl(pts, field="trade_count")
    if len(x) == 0:
        continue
    idle = (tc == 0) & (x == 0) if len(tc) == len(x) else (x == 0)
    start = 0
    run = 0
    for i, z in enumerate(idle):
        run = run + 1 if z else 0
        if run >= GAP:
            start = i + 1
    # do not cut into the selection window
    start = min(start, max(0, len(x) - 30))
    info[w] = {"cut_days": start, "n_full": len(x), "idle_days_total": int(idle.sum())}
    M[w] = screen_metrics(x[start:], boot=False)
    M[w]["_x"] = x[start:]
pv = [M[w]["p_pre"] if w in M and M[w]["pre_days"] >= 60 else 1.0 for w in W]
ph = dict(zip(W, holm(pv)))
passed = []
for w in W:
    if w not in M:
        continue
    m = M[w]
    if not reasons({**m, "p_boot_pre": 0.0}, float(ph[w])):
        m["p_boot_pre"] = stationary_bootstrap_p(m["_x"][: m["pre_days"]], 20000)
    else:
        m["p_boot_pre"] = None
    m["reasons"] = reasons(m, float(ph[w])) if m["p_boot_pre"] is not None else [r for r in reasons({**m, "p_boot_pre": 0.0}, float(ph[w]))]
    if not m["reasons"]:
        passed.append(w)
cut = [w for w in W if info.get(w, {}).get("cut_days")]
print(f"wallets with a >= {GAP}-day dormant run before their last activity spell: {len(cut)}")
print("passes on last-activity-spell history:", len(passed))
new = [w for w in passed if w not in a1["evidence"]["derived"]["a1_pass"]]
lost = [w for w in a1["evidence"]["derived"]["a1_pass"] if w not in passed]
for w in new:
    m = M[w]
    print(f"  NEW #{rec[w]['rank']} {rec[w]['name']} {w}: cut {info[w]['cut_days']} dormant days of {info[w]['n_full']}; n={m['n']} pre={m['pre_days']} p={m['p_pre']:.2e} "
          f"holm={ph[w]:.3g} boot={m['p_boot_pre']:.5f} dsr={m['dsr']:.4f} l30=${m['last30']:,.0f} med=${m['median6']:,.0f} posM={m['pos_months']:.2f} "
          f"sh={m['sharpe']:.1f} posW={m['pos_weeks']:.2f}; recorded reasons {reason_codes(rec[w]['stage_a1_reasons'])}")
print("  recorded passes lost:", [rec[w]["rank"] for w in lost])
# near passes on active history (fail exactly one check, excluding bootstrap-not-run)
one = [(rec[w]["rank"], rec[w]["name"], M[w]["reasons"], info[w]["cut_days"]) for w in W if w in M and len(M[w]["reasons"]) == 1 and info[w]["cut_days"] > 0]
print("  fail exactly one check on active history AND had a dormant cut:", one)
(OUT / "dormancy.json").write_text(json.dumps({"gap": GAP, "passed": passed, "new": new, "lost": lost,
                                               "info": info, "reasons": {w: M[w]["reasons"] for w in M}}, indent=1, default=float))
