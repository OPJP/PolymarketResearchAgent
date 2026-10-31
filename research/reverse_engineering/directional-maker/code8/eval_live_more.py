"""Iteration 8: evaluate() (R6) on the other development live slices of 10-31: 12:00-15:00 UTC (Chainlink from the
endpoint where no live recording exists, up to 3,000 requests) and 16:30-18:00 UTC (BTC 5m off from 16:53; 15m on)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402

for a, b, fetch in ((1793464200, 1793469600, False), (1793448000, 1793458800, True)):
    F.FETCH_CL = fetch
    try:
        r = F.evaluate(a, b, local=False, n_perm=2)
    except Exception as ex:  # noqa: BLE001
        print(a, b, "error", repr(ex)[:300], flush=True)
        continue
    (HERE.parent / "results" / f"iter8_eval_r6_{a}_{b}.json").write_text(json.dumps(r, indent=1, default=str))
    keep = {k: r.get(k) for k in ("windows", "cluster_maker_fills", "side_posture_match_clock", "union_btc5m_15m", "scope")}
    keep["price_match_clock"] = {k: (r.get("price_match_clock") or {}).get(k) for k in ("n_match_clock", "within_0.01", "anchor_last_print_within_0.01", "error")}
    keep["btc15m_presence"] = (r.get("btc15m") or {}).get("presence")
    print(a, b, json.dumps(keep, default=str)[:3000], flush=True)
