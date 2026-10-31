"""Recompute stage A1, persistence and income split for the three cluster wallets from the cached user-pnl series."""
import sys, json
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums
from polyrea.workflows.screen import wallet_pnl_metrics, apply_criteria
from polyrea.stats import significance as S
from polyrea.stats.persistence import persistence_report

AS_OF = 1793318400
W = {"GoodFallen": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "x-MoneyForWhiskas": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "dangerously": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
a1 = {r["wallet"]: r for r in json.load(open("/home/user/PolymarketResearchAgent/research/stage_a/stage_a1.json"))["wallets"]}
pm = PolymarketData()
out = {}
for name, w in W.items():
    body, src = pm.user_pnl(w, max_age=None)
    m = wallet_pnl_metrics(body.get("points") or [], AS_OF)
    df = daily_frame(body.get("points") or [], as_of=AS_OF)
    d = df["d_economic_pnl"].iloc[1:]
    m["deflated_sharpe"] = S.deflated_sharpe_ratio(d.to_numpy(), n_trials=500)
    rec = a1[w]["metrics"]
    m["p_holm_pre"] = rec["p_holm_pre"]
    reasons = apply_criteria(m)
    keys = ["history_days", "last_30d_pnl", "median_month_pnl", "monthly_pnl_recent_first", "annual_sharpe", "share_positive_weeks", "share_positive_months", "hac_t_pre", "p_pre", "p_boot_pre", "deflated_sharpe", "pre_selection_days"]
    diff = {k: (m.get(k), rec.get(k)) for k in keys}
    # income over last 30 days
    last = df.iloc[-30:]
    inc = {k: float(last[f"d_{k}"].sum()) for k in ("economic_pnl", "trade_pnl", "wallet_income", "maker_rebate", "fees_paid", "volume_usdc", "trade_count") if f"d_{k}" in last}
    inc["taker_rebate_implied"] = inc["wallet_income"] - inc["maker_rebate"]
    inc["taker_rebate_rate"] = inc["taker_rebate_implied"] / -inc["fees_paid"]
    # PnL without any rebate (newcomer at 0% taker tier, still earning maker rebate? report both)
    inc["pnl_no_taker_rebate"] = inc["economic_pnl"] - inc["taker_rebate_implied"]
    inc["pnl_no_rebates_at_all"] = inc["economic_pnl"] - inc["wallet_income"]
    # median 30-day block on the trade_pnl excluding taker rebate, per block
    dd = df.iloc[1:]
    no_tr = dd["d_economic_pnl"] - (dd["d_wallet_income"] - dd["d_maker_rebate"])
    inc["blocks_pnl_no_taker_rebate"] = monthly_blocks(no_tr)
    # persistence: last 30 days
    pr = persistence_report(d.to_numpy(), recent_days=30)
    out[name] = {"recomputed_vs_recorded": diff, "a1_reasons_recomputed": reasons, "income_last30": inc,
                 "persistence": {"recent_p": pr.recent.p_value, "decline_p": pr.decline.p_value, "trend_p": pr.trend.p_value, "cusum_p": pr.cusum_break.p_value} if hasattr(pr, "recent") else str(pr)[:500],
                 "weekly_sums_last8": [float(x) for x in weekly_sums(d)[-8:]],
                 "worst_day": float(d.min()), "neg_days": int((d < 0).sum())}
print(json.dumps(out, indent=1, default=float))
json.dump(out, open("/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster/recheck_a1.json", "w"), indent=1, default=float)
