"""Smoke test: final_rule.evaluate with intervals on a 4-hour slice of VALIDATE (only aggregate output kept)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule  # noqa
final_rule.CACHE = HERE.parents[3] / ".cache/re/directional-maker/exam"
r = final_rule.evaluate(1793145600, 1793160000, intervals=[[1793145600, 1793152800]], local=True, n_perm=2)
print(json.dumps({"windows": r["windows"], "presence": r["presence"]["auc"], "per_wallet_keys": list(r["per_wallet"])}, default=str))
