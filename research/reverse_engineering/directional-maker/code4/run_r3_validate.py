"""Run the frozen rule R3 (code/final_rule.py) on the new VALIDATE half of the released lot
[2026-10-27, 2026-10-31) using the lot day files in .cache/re/directional-maker/exam (aggregate metrics only)."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule  # noqa
final_rule.CACHE = ROOT / ".cache/re/directional-maker/exam"
a, b = int(sys.argv[1]), int(sys.argv[2])
t0 = time.time()
r = final_rule.evaluate(a, b, local=True, n_perm=int(sys.argv[3]) if len(sys.argv) > 3 else 99)
r["runtime_s"] = round(time.time() - t0)
out = HERE.parent / "results" / f"iter4_r3_validate_{a}_{b}.json"
out.write_text(json.dumps(r, indent=1, default=str))
print(json.dumps({k: r[k] for k in list(r)[:40]}, indent=1, default=str)[:4000])
