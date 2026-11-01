"""Iteration 13: smoke test of evaluate() after the reporting-only per-burst-start block in side_sm.py, on the
historical VALIDATE hour 10-29 12-13 (as iteration 12's smoke test; aggregate output only)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402
F.FETCH_CL = False
a, b = int(sys.argv[1]), int(sys.argv[2])
r = F.evaluate(a, b, local=False, n_perm=2)
(HERE.parent / "results" / f"iter13_smoke_r8_{a}_{b}.json").write_text(json.dumps(r, indent=1, default=str))
ss = r.get("side_state_machine") or {}
print(json.dumps({"windows": r.get("windows"), "fills": r.get("cluster_maker_fills"), "presence": (r.get("presence") or {}).get("auc"),
                  "sm_no_own": ss.get("no_own_state"), "sm_comp": ss.get("composite_own_state"), "per_burst_start": ss.get("per_burst_start"),
                  "err": ss.get("per_burst_start_error"), "btc15m_burst": ((r.get("btc15m") or {}).get("side_state_machine") or {}).get("per_burst_start")}, indent=1, default=str))
