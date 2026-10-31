"""Recompute every stage-A1 metric for all 500 wallets from the exact cached
user-pnl bodies the screen used (sha256 checked), with independent code."""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import AS_OF, OUT, RepoCacheRO, holm, load_a1, nonmidnight_count, reason_codes, reasons, screen_metrics, daily_pnl, user_pnl_url  # noqa: E402

a1 = load_a1()
assert a1["evidence"]["subject"]["as_of"] == AS_OF
rc = RepoCacheRO()
rows = {}
for w in a1["wallets"]:
    addr = w["wallet"]
    rec_src = w["metrics"].get("source") or {}
    url = rec_src.get("url") or user_pnl_url(addr)
    hit = rc.get_raw(url)
    entry = {"rank": w["rank"], "name": w["name"], "lb_pnl": w["lb_pnl"]}
    if hit is None:
        entry["cache"] = "missing"
        rows[addr] = entry
        continue
    fetched_at, raw = hit
    sha = hashlib.sha256(raw).hexdigest()
    entry["cache_fetched_at"] = fetched_at
    entry["sha_match"] = sha == rec_src.get("body_sha256")
    body = (json.loads(raw) or {}).get("data") or {}
    pts = body.get("points") or []
    entry["n_points"] = len(pts)
    entry["nonmidnight_points"] = nonmidnight_count(pts)
    days, x = daily_pnl(pts)
    _, xt = daily_pnl(pts, field="trade_pnl")
    entry["first_day"] = int(days[0]) if len(days) else None
    if len(x) == 0:
        entry["m"] = {"n": 0}
        rows[addr] = entry
        continue
    m = screen_metrics(x)
    m["total_trade"] = float(xt.sum()) if len(xt) else None
    m["last30_trade"] = float(xt[-30:].sum()) if len(xt) else None
    entry["m"] = m
    rows[addr] = entry

wallets = [w["wallet"] for w in a1["wallets"]]
p_for_holm = [rows[w]["m"]["p_pre"] if rows[w].get("m", {}).get("pre_days", 0) >= 60 else 1.0 for w in wallets]
ph = holm(p_for_holm)
for w, p in zip(wallets, ph):
    rows[w]["p_holm"] = float(p)
    m = rows[w].get("m") or {"n": 0}
    rows[w]["my_reasons"] = reasons(m, float(p)) if m.get("n") else ["no history"]

(OUT / "recheck_all.json").write_text(json.dumps(rows, indent=1, default=float))

# ---------------------------------------------------------------- compare with recorded
recmap = {w["wallet"]: w for w in a1["wallets"]}
num_keys = [
    ("pre_selection_days", "pre_days", 0),
    ("history_days", "n", 0),
    ("last_30d_pnl", "last30", 1.0),
    ("median_month_pnl", "median6", 1.0),
    ("share_positive_months", "pos_months", 1e-9),
    ("annual_sharpe", "sharpe", 1e-6),
    ("share_positive_weeks", "pos_weeks", 1e-9),
    ("p_pre", "p_pre", 1e-6),
    ("deflated_sharpe", "dsr", 1e-6),
]
diffs = []
sha_bad = [w for w in wallets if rows[w].get("sha_match") is False]
missing = [w for w in wallets if rows[w].get("cache") == "missing"]
reason_mismatch = []
for w in wallets:
    rec = recmap[w]
    rm = rec["metrics"]
    mine = rows[w].get("m") or {}
    for rk, mk, tol in num_keys:
        a, b = rm.get(rk), mine.get(mk)
        if a is None and b is None:
            continue
        if a is None or b is None:
            diffs.append((w, rk, a, b))
            continue
        if not (np.isfinite(a) and np.isfinite(b)):
            if not (np.isnan(a) and np.isnan(b)) and a != b:
                diffs.append((w, rk, a, b))
            continue
        rel = abs(a - b) / max(1.0, abs(a)) if tol >= 1 else abs(a - b)
        if (tol >= 1 and abs(a - b) > tol) or (tol < 1 and abs(a - b) > tol * max(1, abs(a))):
            diffs.append((w, rk, a, b))
    a, b = rm.get("p_holm_pre"), rows[w]["p_holm"]
    if a is not None and abs(a - b) > 1e-6:
        diffs.append((w, "p_holm_pre", a, b))
    rec_codes = sorted(reason_codes(rec["stage_a1_reasons"]))
    my_codes = sorted(rows[w]["my_reasons"])
    if rec_codes != my_codes:
        reason_mismatch.append((w, rec["rank"], rec_codes, my_codes,
                                rm.get("p_boot_pre"), mine.get("p_boot_pre")))

boot_pairs = [(recmap[w]["metrics"].get("p_boot_pre"), rows[w]["m"].get("p_boot_pre")) for w in wallets
              if rows[w].get("m", {}).get("pre_days", 0) >= 60 and recmap[w]["metrics"].get("p_boot_pre") is not None]
bp = np.array(boot_pairs, float)
print("sha mismatches:", len(sha_bad), "cache missing:", len(missing))
print("numeric diffs:", len(diffs))
for d in diffs[:40]:
    print("  ", d)
print("bootstrap: n=", len(bp), "max |diff|=", np.max(np.abs(bp[:, 0] - bp[:, 1])),
      "corr=", np.corrcoef(bp[:, 0], bp[:, 1])[0, 1])
side_flip = [(w, recmap[w]["metrics"]["p_boot_pre"], rows[w]["m"]["p_boot_pre"]) for w in wallets
             if rows[w].get("m", {}).get("pre_days", 0) >= 60 and recmap[w]["metrics"].get("p_boot_pre") is not None
             and (recmap[w]["metrics"]["p_boot_pre"] <= 0.01) != (rows[w]["m"]["p_boot_pre"] <= 0.01)]
print("bootstrap pass/fail flips at 0.01:", side_flip)
print("reason-set mismatches:", len(reason_mismatch))
for r in reason_mismatch:
    print("  ", r)
my_pass = [w for w in wallets if not rows[w]["my_reasons"]]
print("my passes:", len(my_pass), "recorded passes:", len(a1["evidence"]["derived"]["a1_pass"]),
      "same set:", set(my_pass) == set(a1["evidence"]["derived"]["a1_pass"]))
print("wallets with non-midnight points <= as_of:", sum(1 for w in wallets if rows[w].get("nonmidnight_points")))
json.dump({"diffs": diffs, "reason_mismatch": reason_mismatch, "boot_flips": side_flip, "sha_bad": sha_bad, "missing": missing},
          open(OUT / "recheck_all_compare.json", "w"), indent=1, default=float)
