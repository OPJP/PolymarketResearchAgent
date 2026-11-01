"""Iteration 8: evaluate() on the live VALIDATE slice 10-31 15:00-16:30 UTC (development block): tapes and activity via the
cached adapters, Chainlink from the live recordings only (no endpoint fetch), 2 rotation draws. Reports the R6 parts."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402

F.FETCH_CL = False
a, b = int(sys.argv[1]), int(sys.argv[2])
r = F.evaluate(a, b, local=False, n_perm=2)
out = HERE.parent / "results" / f"iter8_eval_r6_{a}_{b}.json"
out.write_text(json.dumps(r, indent=1, default=str))
keep = {k: r.get(k) for k in ("windows", "cluster_maker_fills", "presence", "side", "price", "price_match_clock", "pnl", "btc15m",
                              "union_btc5m_15m", "scope", "side_posture_match_clock")}
print(json.dumps(keep, indent=1, default=str)[:9000])
