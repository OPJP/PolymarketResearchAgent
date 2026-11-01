"""Smoke test of the examiner path: final_rule.evaluate with local=False (polyrea adapters only) on 1 hour of VALIDATE."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule  # noqa
t0 = time.time()
r = final_rule.evaluate(1793059200, 1793062800, local=False, n_perm=2)
print(json.dumps({"windows": r["windows"], "fills": r["cluster_maker_fills"], "presence": round(r["presence"]["auc"], 4),
                  "baseline": round(r["presence"]["auc_activity_baseline"], 4), "price": round(r["price"]["within_0.01"], 4),
                  "per_wallet": {k: round(v["presence_auc"], 4) for k, v in r["per_wallet"].items()}, "s": round(time.time() - t0)}))
