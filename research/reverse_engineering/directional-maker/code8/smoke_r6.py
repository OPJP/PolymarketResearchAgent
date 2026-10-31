"""Iteration 8: smoke test of final_rule.evaluate() with the BTC 15m family (R6 scope), development slice, local caches,
no Chainlink fetch, 2 rotation draws.  python code8/smoke_r6.py <start> <end>"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402

F.FETCH_CL = False
a, b = int(sys.argv[1]), int(sys.argv[2])
r = F.evaluate(a, b, local=True, n_perm=2)
keep = {k: r.get(k) for k in ("windows", "cluster_maker_fills", "presence", "side", "price", "pnl", "btc15m", "union_btc5m_15m", "scope")}
out = HERE.parent / "results" / f"iter8_smoke_r6_{a}_{b}.json"
out.write_text(json.dumps(r, indent=1, default=str))
print(json.dumps(keep, indent=1, default=str)[:6000])
