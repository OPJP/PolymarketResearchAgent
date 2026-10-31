"""(a) Start each wallet's track record at its first real activity (first day the running sum of
|daily PnL| exceeds $1,000) and rerun the whole A1 screen (Holm recomputed over the same family rule).
(b) Rerun the A1 Holm step with alternative HAC bandwidths (Schwert 12(n/100)^0.25, Andrews AR(1)
plug-in) to see how many of the 11 survivors depend on the bandwidth choice."""
import json

import numpy as np

from common import AS_OF, SCR, board, points
from polyrea.analysis.pnl import daily_frame
from polyrea.stats import significance as S
from polyrea.workflows.screen import CRITERIA, apply_criteria, wallet_pnl_metrics

rows = board()
wallets = [r["user_id"].lower() for r in rows]
names = {r["user_id"].lower(): (r["rank"], r["user_name"]) for r in rows}
orig = json.load(open(f"{SCR}/a1_recomputed.json"))
orig_pass = {w for w in wallets if "error" not in orig[w] and not apply_criteria(orig[w])}


def screen(metric_fn):
    res = {}
    for w in wallets:
        pts = points(w)
        res[w] = metric_fn(w, pts) if pts else {"history_days": 0, "error": "none"}
    p_pre = [res[w].get("p_pre", 1.0) if res[w].get("pre_selection_days", 0) >= CRITERIA.min_pre_selection_days else 1.0 for w in wallets]
    for w, ph in zip(wallets, S.holm_bonferroni(p_pre)):
        res[w]["p_holm_pre"] = ph
    return res


# (a) trim leading dormancy
def trimmed(w, pts):
    pts = sorted(pts, key=lambda p: p["timestamp"])
    df = daily_frame(pts, as_of=AS_OF)
    d = df["d_economic_pnl"].iloc[1:]
    act = np.flatnonzero(np.cumsum(np.abs(d.to_numpy())) > 1000.0)
    if len(act) and act[0] > 0:
        start_ts = int(d.index[act[0]].timestamp()) - 86400  # keep the level row before the first active day
        pts = [p for p in pts if p["timestamp"] >= start_ts]
    m = wallet_pnl_metrics(pts, AS_OF)
    if m.get("history_days", 0) > 0:
        dd = daily_frame(pts, as_of=AS_OF)["d_economic_pnl"].iloc[1:].to_numpy()
        m["deflated_sharpe"] = S.deflated_sharpe_ratio(dd, n_trials=len(wallets))
    m["trimmed_days"] = int(act[0]) if len(act) else 0
    return m


ra = screen(trimmed)
pass_a = {w for w in wallets if "error" not in ra[w] and not apply_criteria(ra[w])}
print("(a) trimmed leading dormancy: A1 passes", len(pass_a), "| new:", [(names[w], ra[w]["trimmed_days"]) for w in pass_a - orig_pass],
      "| lost:", [names[w] for w in orig_pass - pass_a])
for w in pass_a - orig_pass:
    m = ra[w]
    print("   ", names[w], {k: m[k] for k in ("history_days", "pre_selection_days", "p_pre", "p_holm_pre", "p_boot_pre", "deflated_sharpe", "annual_sharpe", "share_positive_weeks", "share_positive_months", "last_30d_pnl", "median_month_pnl")})


# (b) bandwidth sensitivity of the Holm step
def andrews_lags(a):
    e = a - a.mean()
    rho = np.clip(np.corrcoef(e[1:], e[:-1])[0, 1], -0.97, 0.97)
    alpha = 4 * rho**2 / ((1 - rho) ** 2 * (1 + rho) ** 2)
    return max(1, int(1.1447 * (alpha * len(a)) ** (1 / 3)))


for label, lagf in [("Schwert 12(n/100)^0.25", lambda a: int(12 * (len(a) / 100) ** 0.25)), ("Andrews AR(1) plug-in", andrews_lags)]:
    res = {w: dict(orig[w]) for w in wallets}
    for w in wallets:
        if res[w].get("pre_selection_days", 0) >= 60:
            pre = daily_frame(points(w), as_of=AS_OF)["d_economic_pnl"].iloc[1:].to_numpy()[:-30]
            res[w]["p_pre"] = S.hac_t_test(pre, lags=lagf(pre)).p_value
    p_pre = [res[w].get("p_pre", 1.0) if res[w].get("pre_selection_days", 0) >= 60 else 1.0 for w in wallets]
    for w, ph in zip(wallets, S.holm_bonferroni(p_pre)):
        res[w]["p_holm_pre"] = ph
    ps = {w for w in wallets if "error" not in res[w] and not apply_criteria(res[w])}
    print(f"(b) {label}: A1 passes {len(ps)}; lost {[names[w][1] for w in orig_pass - ps]}; new {[names[w][1] for w in ps - orig_pass]}")
    for w in orig_pass - ps:
        print(f"     {names[w][1]}: p_pre={res[w]['p_pre']:.2e} Holm={res[w]['p_holm_pre']:.3f} (as run: {orig[w]['p_holm_pre']:.2e})")
