"""Self-proposed (iteration 16, X231): does a SMALL net cap turn the public bid-side ladder's realized PnL into locked
pair margin (the 81% component of the wallet's per-market PnL variance)? Same examinable tape engine and universe as
iteration 15's tape_exit_policy.py (data-api taker tape, strict trade-through fills, others' bid usable 2 s after its
block, refills every 10 s, band [0.05, 0.95]); variants differ only in the net cap (20 / 50 / 100 CS2 shares, x0.1 in
Dota) and the pair cap (0.99 / 0.97). Pre-registered (NOTES iteration 16, before the run): chosen on BUILD by
min(Pearson, Spearman) of per-market PnL with the wallet's; VALIDATE scored once; adopted into evaluate() only if the
choice beats v6 (0.197 / 0.027) on VALIDATE in both coefficients. Output: results/tiny_cap_pairlock.json"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter15"))
import tape_exit_policy as T  # noqa: E402

T.VARIANTS = {
    "L1_C0": dict(slots=1, cap=np.inf, taper=False),
    "L1_C20": dict(slots=1, cap=20.0, taper=False),
    "L1_C50": dict(slots=1, cap=50.0, taper=False),
    "L1_C100": dict(slots=1, cap=100.0, taper=False),
    "L1_C20_PC97": dict(slots=1, cap=20.0, taper=False, pair_cap=0.97),
    "L1_C50_PC97": dict(slots=1, cap=50.0, taper=False, pair_cap=0.97),
    "L1_C100_PC97": dict(slots=1, cap=100.0, taper=False, pair_cap=0.97),
}
res = {}
XB = T.split_rows(T.B0, T.VAL0)
XV = T.split_rows(T.VAL0, T.H)
res["BUILD"] = T.summarize(XB)
res["VALIDATE"] = T.summarize(XV)
score = {k: min(x if x is not None else -9 for x in res["BUILD"][k]["corr"][:2]) for k in T.VARIANTS}
best = max(score, key=score.get)
res["build_scores"] = score
res["chosen_on_BUILD"] = best
res["VALIDATE_chosen"] = res["VALIDATE"][best]
v = XV.sort_values("gs")
h = len(v) // 2
res["VALIDATE_chosen_halves"] = [T.corr(v.iloc[:h][best], v.iloc[:h].w), T.corr(v.iloc[h:][best], v.iloc[h:].w)]
res["adopt"] = bool(all(x is not None for x in res["VALIDATE_chosen"]["corr"][:2]) and res["VALIDATE_chosen"]["corr"][0] > 0.197 and res["VALIDATE_chosen"]["corr"][1] > 0.027)
(T.RES / "tiny_cap_pairlock.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps({k: res[k] for k in ("build_scores", "chosen_on_BUILD", "VALIDATE_chosen", "VALIDATE_chosen_halves", "adopt")}, indent=1, default=str))
for sp in ("BUILD", "VALIDATE"):
    print(sp, {k: res[sp][k]["corr"][:2] for k in T.VARIANTS}, "pnl", {k: res[sp][k]["pnl"] for k in T.VARIANTS}, "prints", res[sp]["prints_baseline"])
