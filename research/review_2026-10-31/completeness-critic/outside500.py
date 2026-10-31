"""Universe-coverage probe: wallets NOT in the screened top-500 whose BTC-5m buy fills settled positive in both the
cached FIT and TEST tapes. Fetch their user-pnl (scratch cache, not the repo cache) and apply the stage-A1 metrics.
Holm is approximated by multiplying p_pre by 500 (the screen's family size)."""
import json, sys, os
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import numpy as np
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.screen import wallet_pnl_metrics, apply_criteria
from polyrea.stats import significance as S
from polyrea.analysis.pnl import daily_frame
OUT = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/completeness-critic"
AS_OF = 1793318400
tw = json.load(open(f"{OUT}/tape_wallets.json"))
cand = [r for r in tw["top25_wallets_by_sampled_pnl"] if r.get("lb_rank") is None and (r.get("pnl_fit") or 0) > 0 and (r.get("pnl_test") or 0) > 0]
print("candidates", len(cand))
pm = PolymarketData()
res = {}
for r in cand[:10]:
    w = r["wallet"]
    body, src = pm.user_pnl(w)
    m = wallet_pnl_metrics(body.get("points") or [], AS_OF)
    if m.get("history_days", 0) > 0:
        df = daily_frame(body.get("points") or [], as_of=AS_OF)
        m["deflated_sharpe"] = S.deflated_sharpe_ratio(df["d_economic_pnl"].iloc[1:].to_numpy(), n_trials=500)
        m["p_holm_pre"] = min(1.0, 500 * m["p_pre"]) if m.get("pre_selection_days", 0) >= 60 else 1.0
    reasons = apply_criteria(m)
    res[w] = {k: m.get(k) for k in ("history_days", "pre_selection_days", "last_30d_pnl", "median_month_pnl", "share_positive_months", "annual_sharpe", "share_positive_weeks", "p_pre", "p_holm_pre", "deflated_sharpe", "volume_30d")}
    res[w]["sampled_btc5m_pnl_fit_test"] = [r.get("pnl_fit"), r.get("pnl_test")]
    res[w]["a1_reasons"] = reasons
    print(w, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res[w].items() if k != "a1_reasons"}), "| reasons:", len(reasons), [x[:40] for x in reasons], flush=True)
json.dump(res, open(f"{OUT}/outside500.json", "w"), indent=1, default=float)
