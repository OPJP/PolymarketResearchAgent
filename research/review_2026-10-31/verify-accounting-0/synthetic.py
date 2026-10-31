"""Synthetic check: feed per_market_decomposition / summarize_profile / price_bucket_calibration
a round trip (buy then sell) and compare to ground truth. Also feed the same events through
build_ledger to confirm the trades frame really carries positive size/usdc for SELLs."""
import json
import pandas as pd
from polyrea.analysis.profile import per_market_decomposition, summarize_profile, price_bucket_calibration, timing_features
from polyrea.analysis.ledger import build_ledger

TOK_YES, TOK_NO = "111", "222"
markets = {
    "c1": {"clobTokenIds": json.dumps([TOK_YES, TOK_NO]), "outcomePrices": json.dumps(["0", "1"]),
           "umaResolutionStatus": "resolved", "closed": True, "closedTime": "2026-10-01 12:00:00+00"},
}
# Build activity rows the way the data-api returns them, then go through the real ledger
activity = [
    {"type": "TRADE", "side": "BUY", "timestamp": 1000, "conditionId": "c1", "asset": TOK_YES, "outcomeIndex": 0,
     "price": 0.40, "size": 100.0, "usdcSize": 40.0, "transactionHash": "0xa", "slug": "cs2-a-b"},
    {"type": "TRADE", "side": "SELL", "timestamp": 2000, "conditionId": "c1", "asset": TOK_YES, "outcomeIndex": 0,
     "price": 0.60, "size": 100.0, "usdcSize": 60.0, "transactionHash": "0xb", "slug": "cs2-a-b"},
]
led = build_ledger("0xw", activity, {"c1": 10_000})
trades = pd.DataFrame(led.trades)
print("ledger trades frame:\n", trades[["side", "outcome_index", "price", "size", "usdc"]].to_string(index=False))
pm = per_market_decomposition(trades, markets)
print("CASE 1 buy 100 YES@0.40, sell 100 YES@0.60, market resolves NO")
print("  as coded: q0=%.1f q1=%.1f cost=%.1f payout=%.1f pnl=%.1f residual_pnl=%.1f" % tuple(pm.loc[0, ["q0", "q1", "cost", "payout", "pnl", "residual_pnl"]]))
print("  truth   : net shares held 0, cash +20 -> pnl +20.0")
print("  ledger realized on the same events:", sum(p.realized for p in led.positions.values()) if hasattr(led, "positions") else "n/a")

# Case 2: buy 100 YES @0.40, sell 100 YES @0.60, market resolves YES -> truth still +20 (nothing held)
m2 = {"c1": dict(markets["c1"], outcomePrices=json.dumps(["1", "0"]))}
pm2 = per_market_decomposition(trades, m2)
print("CASE 2 same fills, market resolves YES")
print("  as coded: pnl=%.1f (truth +20.0)" % pm2.loc[0, "pnl"])

# Case 3: two-sided: buy 100 YES@0.45, buy 100 NO@0.50 (pair cost 0.95 -> locked +5),
# then sell 50 YES@0.70. Resolves NO. Truth: cash = -45-50+35 = -60, hold 50 YES(0) + 100 NO(1) -> payout 100 -> +40
act3 = [
    {"type": "TRADE", "side": "BUY", "timestamp": 1000, "conditionId": "c1", "asset": TOK_YES, "outcomeIndex": 0, "price": 0.45, "size": 100.0, "usdcSize": 45.0, "transactionHash": "0x1", "slug": "cs2-a-b"},
    {"type": "TRADE", "side": "BUY", "timestamp": 1001, "conditionId": "c1", "asset": TOK_NO, "outcomeIndex": 1, "price": 0.50, "size": 100.0, "usdcSize": 50.0, "transactionHash": "0x2", "slug": "cs2-a-b"},
    {"type": "TRADE", "side": "SELL", "timestamp": 1500, "conditionId": "c1", "asset": TOK_YES, "outcomeIndex": 0, "price": 0.70, "size": 50.0, "usdcSize": 35.0, "transactionHash": "0x3", "slug": "cs2-a-b"},
]
t3 = pd.DataFrame(build_ledger("0xw", act3, {"c1": 10_000}).trades)
pm3 = per_market_decomposition(t3, markets)
r = pm3.iloc[0]
print("CASE 3 buy 100 YES@.45 + 100 NO@.50, sell 50 YES@.70, resolves NO")
print(f"  as coded: q0={r.q0} q1={r.q1} pairs={r.pairs} pair_cost={r.pair_cost:.4f} locked={r.locked_pnl:.2f} resid={r.residual_pnl:.2f} pnl={r.pnl:.2f}")
print("  truth   : pnl +40.00 (cash -60, payout 100); held 50 YES + 100 NO")
summ = summarize_profile(t3, pm3, timing_features(t3, markets))
print("  summarize_profile settled_pnl=%.2f locked=%.2f resid=%.2f usd_volume=%.2f" % (summ["settled_pnl"], summ["settled_locked_pnl"], summ["settled_residual_pnl"], summ["usd_volume"]))
cal = price_bucket_calibration(t3, markets)
print("  calibration buckets (SELL @0.70 counted as a bought share):")
for b in cal:
    print("   ", b)
