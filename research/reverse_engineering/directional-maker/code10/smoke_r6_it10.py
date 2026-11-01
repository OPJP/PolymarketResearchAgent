"""Iteration 10: smoke test of evaluate() with the iteration-10 order-class diagnostic on a development slice (Chainlink from the
live recordings only, 2 rotation draws)."""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402
F.FETCH_CL = False
a, b = int(sys.argv[1]), int(sys.argv[2])
r = F.evaluate(a, b, local=False, n_perm=2)
(HERE.parent / "results" / f"iter10_eval_r6_{a}_{b}.json").write_text(json.dumps(r, indent=1, default=str))
print(json.dumps(r.get("side_posture_match_clock"), indent=1, default=str)[:4000])
