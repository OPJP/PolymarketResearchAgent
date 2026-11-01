"""Iteration 6: smoke test of final_rule.evaluate (R4) on a 2-hour STUDY slice of the released lot (lot day files).
    python code6/smoke_r4.py <start_ts> <end_ts>"""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule  # noqa
final_rule.CACHE = ROOT / ".cache/re/directional-maker/exam"
a, b = int(sys.argv[1]), int(sys.argv[2])
t0 = time.time()
r = final_rule.evaluate(a, b, local=True, n_perm=2)
r["runtime_s"] = round(time.time() - t0)
print(json.dumps({k: r.get(k) for k in ("windows", "cluster_maker_fills", "presence", "price", "price_match_clock", "runtime_s")}, indent=1, default=str)[:3000])
