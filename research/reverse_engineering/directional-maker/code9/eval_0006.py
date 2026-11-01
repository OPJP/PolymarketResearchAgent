"""Iteration 9: the frozen R6 through evaluate() on the development block 10-31 00:00-06:00 UTC, which no earlier analysis
scored (no live recording: block-clock parts only; Chainlink from the recordings only, none exist for this block, so R5
falls back to R3). 2 rotation draws."""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402
F.FETCH_CL = False
a, b = 1793404800, 1793426400
r = F.evaluate(a, b, local=False, n_perm=2)
(HERE.parent / "results" / f"iter9_eval_r6_{a}_{b}.json").write_text(json.dumps(r, indent=1, default=str))
keep = {k: r.get(k) for k in ("windows", "cluster_maker_fills", "presence", "presence_r5", "side", "price", "pnl", "btc15m", "union_btc5m_15m", "scope", "selection")}
print(json.dumps(keep, indent=1, default=str)[:6000])
