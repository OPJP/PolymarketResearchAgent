"""Independent recomputation of criteria (1)-(4) and (9) for RN1 from the cached user-pnl series
and the cached activity ledger. Uses own HAC implementation (Bartlett kernel) as a cross-check."""
import json, sys
import numpy as np, pandas as pd
from scipy import stats
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue, deflated_sharpe_ratio
from polyrea.stats.persistence import persistence_report

W = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
AS_OF = 1793318400
pm = PolymarketData()
body, src = pm.user_pnl(W)
print("user-pnl source cached:", src.cached, src.fetched_at, "points", len(body.get("points") or []))
df = daily_frame(body.get("points") or [], as_of=AS_OF)
d = df["d_economic_pnl"].iloc[1:]
x = d.to_numpy()
print("days", len(x), "first", d.index[0].date(), "last", d.index[-1].date())


def my_hac(x, L=None):
    n = len(x); L = L if L is not None else int(np.floor(4 * (n / 100) ** (2 / 9)))
    e = x - x.mean(); g0 = e @ e / n
    s = g0 + 2 * sum((1 - l / (L + 1)) * (e[l:] @ e[:-l] / n) for l in range(1, L + 1))
    t = x.mean() / np.sqrt(s / n)
    return t, 1 - stats.norm.cdf(t), L

pre = x[:-30]; last30 = x[-30:]
t_pre, p_pre, L = my_hac(pre)
print(f"pre-selection n={len(pre)} my HAC t={t_pre:.2f} (lags {L}) one-sided p={p_pre:.2e}; Holm x500 upper bound p<= {min(1, 500 * p_pre):.2e}")
print("project hac_t_test pre:", hac_t_test(pre))
print("bootstrap pre:", stationary_bootstrap_pvalue(pre, n_boot=4000).p_value)
print("deflated SR (500 trials):", deflated_sharpe_ratio(pre, n_trials=500))
sr = x.mean() / x.std(ddof=1) * np.sqrt(365)
print(f"annualized daily Sharpe (all {len(x)} days) {sr:.2f}; pre {pre.mean()/pre.std(ddof=1)*np.sqrt(365):.2f}")
k = len(x) // 7; wk = x[len(x) - 7 * k:].reshape(k, 7).sum(1)
print(f"positive weeks {np.mean(wk > 0):.3f} ({k} weeks)")
blocks = [x[len(x) - 30 * (i + 1): len(x) - 30 * i].sum() for i in range(len(x) // 30)]
print("30-day blocks recent first (first 6):", [round(b) for b in blocks[:6]], "positive share all blocks", np.mean(np.array(blocks) > 0), "n blocks", len(blocks))
print("last 30d", last30.sum(), "median of last 6 blocks", np.median(blocks[:6]))
# income split last 30 days
for f in ("wallet_income", "maker_rebate", "reward_income", "fees_paid", "trade_pnl"):
    if f"d_{f}" in df:
        print(f, round(float(df[f"d_{f}"].iloc[-30:].sum())))
# persistence
rep = persistence_report(x)
print("persistence:", rep)
t30, p30, _ = my_hac(last30, 3)
print(f"last 30 days my HAC t={t30:.2f} p={p30:.4f}")
# trade-only (ex incentives) last 30 days significance
xt = df["d_trade_pnl"].iloc[1:].to_numpy()
t30t, p30t, _ = my_hac(xt[-30:], 3)
print(f"trade_pnl last 30 days sum {xt[-30:].sum():.0f}, HAC t={t30t:.2f} p={p30t:.4f}")
# daily pnl ex all incentives = economic - wallet_income
xe = (df["d_economic_pnl"] - df["d_wallet_income"]).iloc[1:].to_numpy()
print(f"economic minus wallet income last30 {xe[-30:].sum():.0f}; Sharpe {xe.mean()/xe.std(ddof=1)*np.sqrt(365):.2f}")
