"""Part (3): did the >=60-day pre-selection rule or the >=80% positive 30-day
blocks rule eliminate wallets whose recent record is strongly significant?

A. pre<60d wallets: waive the 60-day rule (still require >=14 pre-selection
   days), compute HAC p on the days they have, Holm over all 500 (vector with
   every waived wallet included), bootstrap, and every other criterion.
B. pos_months failures: recompute every criterion on the recent record only
   (last 180 days = the six 30-day blocks the median already uses; its
   pre-selection part is days -180..-31), Holm over all 500 with the same
   recent-window p for every wallet. Also report positive share among
   non-zero (active) blocks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RepoCacheRO, blocks_back, daily_pnl, holm, load_a1, reason_codes, reasons, screen_metrics, stationary_bootstrap_p, user_pnl_url  # noqa: E402

a1 = load_a1()
WR = a1["wallets"]
W = [w["wallet"] for w in WR]
rec = {w["wallet"]: w for w in WR}
rc = RepoCacheRO()
X = {}
for w in W:
    pts = ((json.loads(rc.get_raw(user_pnl_url(w))[1]) or {}).get("data") or {}).get("points") or []
    X[w] = daily_pnl(pts)[1]
base = json.loads((OUT / "recheck_all.json").read_text())

# ------------------------------------------------------------------ A. 60-day rule waived
MIN_PRE = 14
mA = {}
for w in W:
    x = X[w]
    if len(x) == 0:
        continue
    mA[w] = screen_metrics(x, boot=False)
pv = []
for w in W:
    m = mA.get(w)
    pv.append(m["p_pre"] if m and m["pre_days"] >= MIN_PRE else 1.0)
phA = dict(zip(W, holm(pv)))
rowsA = []
for w in W:
    codes = reason_codes(rec[w]["stage_a1_reasons"])
    if "pre<60d" not in codes:
        continue
    m = mA.get(w)
    if not m or m["pre_days"] < MIN_PRE:
        rowsA.append({"wallet": w, "rank": rec[w]["rank"], "name": rec[w]["name"], "pre_days": m["pre_days"] if m else 0, "note": f"<{MIN_PRE} pre-selection days"})
        continue
    m["p_boot_pre"] = stationary_bootstrap_p(X[w][: m["pre_days"]], 20000)
    r = reasons({**m, "pre_days": 60}, float(phA[w]))  # treat as if history sufficed
    rowsA.append({"wallet": w, "rank": rec[w]["rank"], "name": rec[w]["name"], "pre_days": m["pre_days"], "n": m["n"],
                  "p_pre": m["p_pre"], "p_holm_waived": float(phA[w]), "p_boot_pre": m["p_boot_pre"], "dsr": m["dsr"],
                  "last30": m["last30"], "median6": m["median6"], "n_blocks": len(m["months"]), "pos_months": m["pos_months"],
                  "sharpe": m["sharpe"], "pos_weeks": m["pos_weeks"], "t_full": m["t_full"], "p_full": m["p_full"],
                  "fails_if_waived": r, "recorded_reasons": codes,
                  "lb_pnl": rec[w]["lb_pnl"], "lb_inconsistent": rec[w]["metrics"].get("lb_series_inconsistent")})
print(f"A. pre<60d wallets: {len(rowsA)}; with >={MIN_PRE} pre days: {sum(1 for r in rowsA if 'p_pre' in r)}")
passA = [r for r in rowsA if "p_pre" in r and not r["fails_if_waived"]]
print("   would pass every other A1 check if the 60-day rule were waived:", [(r["rank"], r["name"]) for r in passA])
strongA = sorted([r for r in rowsA if "p_pre" in r and r["p_pre"] < 1e-3], key=lambda r: r["p_pre"])
print("   raw pre-selection HAC p < 0.001:")
for r in strongA:
    print(f"   #{r['rank']:3d} {str(r['name'])[:22]:22s} pre={r['pre_days']:2d}d n={r['n']:3d} p={r['p_pre']:.2e} holm={r['p_holm_waived']:.3g} boot={r['p_boot_pre']:.4f} "
          f"dsr={r['dsr']:.3f} l30=${r['last30']:,.0f} med=${r['median6']:,.0f}({r['n_blocks']}blk) posM={r['pos_months']} sh={r['sharpe']:.1f} posW={r['pos_weeks']:.2f} "
          f"other_fails={r['fails_if_waived']}")

# ------------------------------------------------------------------ B. recent record only (last 180 days)
R = 180
mB = {}
for w in W:
    x = X[w]
    if len(x) == 0:
        continue
    xr = x[-R:]
    mB[w] = screen_metrics(xr, boot=False)
pvB = [mB[w]["p_pre"] if w in mB and mB[w]["pre_days"] >= 60 else 1.0 for w in W]
phB = dict(zip(W, holm(pvB)))
rowsB = []
for w in W:
    codes = reason_codes(rec[w]["stage_a1_reasons"])
    if "pos_months" not in codes:
        continue
    x = X[w]
    months_all = blocks_back(x, 30)
    active = months_all[months_all != 0]
    mb = mB[w]
    mb["p_boot_pre"] = stationary_bootstrap_p(x[-R:][: mb["pre_days"]], 20000) if mb["pre_days"] >= 5 else None
    r_recent = reasons(mb, float(phB[w]))
    # what fails on the full record apart from pos_months?
    other_full = [c for c in base[w]["my_reasons"] if c != "pos_months"]
    rowsB.append({"wallet": w, "rank": rec[w]["rank"], "name": rec[w]["name"], "n": len(x), "blocks": len(months_all),
                  "pos_months_all": float(np.mean(months_all > 0)) if len(months_all) else None,
                  "zero_blocks": int(np.sum(months_all == 0)),
                  "pos_months_active": float(np.mean(active > 0)) if len(active) else None,
                  "full_other_fails": other_full,
                  "recent_pre_days": mb["pre_days"], "recent_p_pre": mb["p_pre"], "recent_p_holm": float(phB[w]), "recent_p_boot": mb["p_boot_pre"],
                  "recent_dsr": mb["dsr"], "recent_sharpe": mb["sharpe"], "recent_pos_weeks": mb["pos_weeks"], "recent_pos_months": mb["pos_months"],
                  "recent_months": mb["months"], "last30": mb["last30"], "median6": mb["median6"], "recent_fails": r_recent,
                  "lb_inconsistent": rec[w]["metrics"].get("lb_series_inconsistent")})
print(f"\nB. pos_months failures: {len(rowsB)}")
only_pm = [r for r in rowsB if not r["full_other_fails"]]
print("   pos_months is the ONLY failure on the full record:", [(r["rank"], r["name"]) for r in only_pm])
pm_plus_hist = [r for r in rowsB if set(r["full_other_fails"]) <= {"pre<60d"} and r["full_other_fails"]]
print("   pos_months + only pre<60d:", [(r["rank"], r["name"]) for r in pm_plus_hist])
passB = [r for r in rowsB if not r["recent_fails"]]
print("   pass every A1 check on the last-180-day record (Holm over 500 on that record):", [(r["rank"], r["name"]) for r in passB])
strongB = sorted([r for r in rowsB if r["recent_p_pre"] < 1e-3], key=lambda r: r["recent_p_pre"])
print("   recent pre-selection (days -180..-31) HAC p < 0.001:")
for r in strongB:
    print(f"   #{r['rank']:3d} {str(r['name'])[:22]:22s} posM_all={r['pos_months_all']:.2f} ({r['blocks']} blk, {r['zero_blocks']} zero) posM_active={r['pos_months_active']} "
          f"| recent: p={r['recent_p_pre']:.2e} holm={r['recent_p_holm']:.3g} boot={r['recent_p_boot']} dsr={r['recent_dsr']:.3f} sh={r['recent_sharpe']:.1f} "
          f"posW={r['recent_pos_weeks']:.2f} posM6={r['recent_pos_months']:.2f} med=${r['median6']:,.0f} l30=${r['last30']:,.0f} | recent_fails={r['recent_fails']} full_other_fails={r['full_other_fails']}")

# ------------------------------------------------------------------ C. how the whole screen looks on the recent record (for context)
allB = [w for w in W if w in mB]
for w in allB:
    mB[w].setdefault("p_boot_pre", None)
passB_all = []
for w in allB:
    r0 = reasons({**mB[w], "p_boot_pre": 0.0}, float(phB[w]))
    if not r0:
        mB[w]["p_boot_pre"] = stationary_bootstrap_p(X[w][-R:][: mB[w]["pre_days"]], 20000)
        if not reasons(mB[w], float(phB[w])):
            passB_all.append(w)
print("\nC. whole screen applied to last-180-day record only: passes =", len(passB_all),
      "| not in recorded A1 passes:", [(rec[w]["rank"], rec[w]["name"], reason_codes(rec[w]["stage_a1_reasons"])) for w in passB_all if w not in a1["evidence"]["derived"]["a1_pass"]],
      "| recorded passes lost:", [rec[w]["rank"] for w in a1["evidence"]["derived"]["a1_pass"] if w not in passB_all])

(OUT / "part3.json").write_text(json.dumps({"A_pre60": rowsA, "B_posmonths": rowsB, "C_recent_passes": passB_all}, indent=1, default=float))
