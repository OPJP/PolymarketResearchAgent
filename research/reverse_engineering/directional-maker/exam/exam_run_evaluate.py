"""Examiner: run the frozen code/final_rule.py evaluate() on the holdout, unchanged.

Only mechanical change, made here and not in final_rule.py: final_rule.CACHE (the directory of its local day files) is
pointed at .cache/re/directional-maker/exam/, where exam_fetch.py stored the holdout data fetched through the same
polyrea adapters in the format of code/fetch_local.py. Reason: evaluate()'s adapter path keeps every tape row of the
period as a Python tuple before building a frame (~2 GB for 8 days, above this laptop's per-process budget).
`check` mode compares local=True with the adapter path (local=False) on a 2-hour slice to show they agree.

python exam_run_evaluate.py full START END     -> results/exam_evaluate_holdout.json
python exam_run_evaluate.py check START END    -> results/exam_evaluate_equivalence.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule  # noqa: E402

final_rule.CACHE = ROOT / ".cache/re/directional-maker/exam"
RES = HERE.parent / "results"

if __name__ == "__main__":
    mode, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    t0 = time.time()
    if mode == "full":
        r = final_rule.evaluate(a, b, local=True)
        r["runtime_s"] = round(time.time() - t0)
        (RES / "exam_evaluate_holdout.json").write_text(json.dumps(r, indent=1, default=str))
        print(json.dumps(r, indent=1, default=str))
    else:
        r1 = final_rule.evaluate(a, b, local=True, n_perm=5)
        r2 = final_rule.evaluate(a, b, local=False, n_perm=5)
        keys = ["windows", "bins", "cluster_maker_fills", "cluster_taker_fills", "tape_rows", "tape_rows_removed_cluster_tx"]
        cmp = {"local": {k: r1[k] for k in keys} | {"presence": r1["presence"], "price": r1["price"], "pnl": r1["pnl"]},
               "adapter": {k: r2[k] for k in keys} | {"presence": r2["presence"], "price": r2["price"], "pnl": r2["pnl"]}}
        (RES / "exam_evaluate_equivalence.json").write_text(json.dumps(cmp, indent=1, default=str))
        print(json.dumps(cmp, indent=1, default=str))
