"""Iteration 11: smoke test of evaluate() with R7-price (in-block execution-order anchor) on a development slice, beside
the live match clock (shared recorder) and the block clock on the same fills (Chainlink from the live recordings only,
2 rotation draws).
    python code11/smoke_r7.py <start_ts> <end_ts>
"""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402
F.FETCH_CL = False
a, b = int(sys.argv[1]), int(sys.argv[2])
r = F.evaluate(a, b, local=False, n_perm=2)
(HERE.parent / "results" / f"iter11_eval_r7_{a}_{b}.json").write_text(json.dumps(r, indent=1, default=str))
keep = {k: r.get(k) for k in ("price", "price_inblock", "price_match_clock")}
keep["btc15m_price_inblock"] = (r.get("btc15m") or {}).get("price_inblock")
keep["union"] = {k: v for k, v in (r.get("union_btc5m_15m") or {}).items() if "price" in k}
print(json.dumps(keep, indent=1, default=str)[:5000])
