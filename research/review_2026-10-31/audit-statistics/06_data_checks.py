"""Checks on the real series: dormant (exact-zero) periods, selection-window effects on Sharpe/DSR
and on the persistence 'recent' test, autocorrelation, HAC-lag / bootstrap-block sensitivity, and the
rolling-window alignment in persistence_report."""
import json
import math

import numpy as np
from scipy import stats

from common import AS_OF, SCR, board, points
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums
from polyrea.stats import persistence as P
from polyrea.stats import significance as S
from polyrea.workflows.screen import apply_criteria

res = json.load(open(f"{SCR}/a1_recomputed.json"))
fails = json.load(open(f"{SCR}/a1_fail_tags.json"))
rows = board()
wallets = [r["user_id"].lower() for r in rows]
names = {r["user_id"].lower(): r["user_name"] for r in rows}
rank = {r["user_id"].lower(): r["rank"] for r in rows}
survivors = [w for w in wallets if not fails[w]]
series = {}
for w in wallets:
    pts = points(w)
    if pts:
        df = daily_frame(pts, as_of=AS_OF)
        series[w] = df["d_economic_pnl"].iloc[1:]

# ---------------------------------------------------------------- 1. dormant periods
print("== 1. exact-zero PnL weeks / 30-day blocks (dormant periods) and their effect")
zero_w = zero_m = lead = 0
flip = []
for w, d in series.items():
    wk = weekly_sums(d)
    mb = np.array(monthly_blocks(d))
    zw = np.sum(np.abs(wk) < 1e-9)
    zm = np.sum(np.abs(mb) < 1e-9)
    zero_w += zw > 0
    zero_m += zm > 0
    a = d.to_numpy()
    nz = np.flatnonzero(np.abs(a) > 1e-9)
    lead += (nz[0] if len(nz) else len(a)) >= 7
    # alternative: drop exactly-zero weeks/blocks from the share
    m2 = dict(res[w])
    if len(wk[np.abs(wk) > 1e-9]):
        m2["share_positive_weeks"] = float(np.mean(wk[np.abs(wk) > 1e-9] > 0))
    if len(mb[np.abs(mb) > 1e-9]):
        m2["share_positive_months"] = float(np.mean(mb[np.abs(mb) > 1e-9] > 0))
    if fails[w] and not apply_criteria(m2):
        flip.append((rank[w], names[w], fails[w]))
print(f"  wallets with >=1 exact-zero week: {zero_w}; with >=1 exact-zero 30-day block: {zero_m}; with >=7 leading zero days: {lead}")
print(f"  wallets that would pass A1 if exact-zero weeks/blocks were excluded from the shares: {flip}")

# ---------------------------------------------------------------- 2. survivors: selection window inside Sharpe / DSR
print("\n== 2. survivors: annualized Sharpe and DSR on full history (as used) vs pre-selection only")
for w in survivors:
    d = series[w].to_numpy()
    pre = d[:-30]
    print(f"  {names[w][:24]:24s} n={len(d):4d} Sharpe full={S.sharpe(d):6.2f} pre={S.sharpe(pre):6.2f} | DSR full={S.deflated_sharpe_ratio(d, 500):.4f} pre={S.deflated_sharpe_ratio(pre, 500):.4f}")

# ---------------------------------------------------------------- 3. autocorrelation and DSR
print("\n== 3. long-run/short-run variance ratio (Bartlett LRV / gamma0) and an autocorrelation-adjusted DSR")


def dsr_ac(a, n_trials=500):
    a = a[np.isfinite(a)]
    n = len(a)
    k = S.hac_variance_of_mean(a) * n / a.var()  # LRV / gamma0
    sr = a.mean() / a.std(ddof=1)
    g3 = stats.skew(a)
    g4 = stats.kurtosis(a, fisher=False)
    sr0 = S.expected_max_sr(n_trials, math.sqrt(k) / math.sqrt(n - 1))
    den = math.sqrt(max(1e-12, k * (1 - g3 * sr + (g4 - 1) / 4 * sr**2)))
    return k, float(stats.norm.cdf((sr - sr0) * math.sqrt(n - 1) / den))


for w in survivors + [w for w in wallets if fails[w] in (["HOLM"], ["MEDIAN"], ["LAST30"], ["PRE<60"])]:
    d = series[w].to_numpy()
    k, v = dsr_ac(d)
    rho1 = np.corrcoef(d[1:], d[:-1])[0, 1]
    print(f"  {names[w][:24]:24s} fails={fails[w]} rho1={rho1:+.2f} LRV/g0={k:.2f} DSR={res[w]['deflated_sharpe']:.4f} DSR_ac={v:.4f}")

# ---------------------------------------------------------------- 4. HAC lag / bootstrap block sensitivity
print("\n== 4. pre-selection p-values under alternative bandwidths (survivors + HOLM-only failures)")


def andrews_lags(a):
    e = a - a.mean()
    rho = np.clip(np.corrcoef(e[1:], e[:-1])[0, 1], -0.97, 0.97)
    alpha = 4 * rho**2 / ((1 - rho) ** 2 * (1 + rho) ** 2)
    return max(1, int(1.1447 * (alpha * len(a)) ** (1 / 3)))


holm_only = [w for w in wallets if fails[w] == ["HOLM"]]
for w in survivors + holm_only:
    pre = series[w].to_numpy()[:-30]
    n = len(pre)
    Ls = {"NW94": S.newey_west_lags(n), "Schwert": int(12 * (n / 100) ** 0.25), "Andrews": andrews_lags(pre)}
    ps = {k: S.hac_t_test(pre, lags=L).p_value for k, L in Ls.items()}
    pb = {mb: S.stationary_bootstrap_pvalue(pre, n_boot=4000, mean_block=mb).p_value for mb in (None, 10.0, 20.0)}
    print(f"  {names[w][:22]:22s} n={n:4d} lags {Ls} p_hac " + " ".join(f"{k}={v:.2e}" for k, v in ps.items())
          + " | p_boot block n^1/3=%.4f 10=%.4f 20=%.4f" % (pb[None], pb[10.0], pb[20.0]))

# ---------------------------------------------------------------- 5. selection bias of the 'recent 30 days significant' persistence test
print("\n== 5. selection effect on the 'last 30 days significant' rule (criterion 9)")
sel = prev = tot = 0
for w, d in series.items():
    a = d.to_numpy()
    if len(a) < 60:
        continue
    tot += 1
    sel += S.hac_t_test(a[-30:]).p_value < 0.05
    prev += S.hac_t_test(a[-60:-30]).p_value < 0.05
print(f"  of {tot} leaderboard wallets with >=60 days: last 30 days (the ranking window) p<0.05: {sel} ({sel/tot:.0%}); "
      f"previous 30 days p<0.05: {prev} ({prev/tot:.0%})")

# ---------------------------------------------------------------- 6. rolling-window alignment
print("\n== 6. persistence_report rolling windows are anchored at the first day, not the last")
for w in survivors:
    a = series[w].to_numpy()
    n = len(a)
    rep = P.persistence_report(a)
    win = min(30, max(10, n // 3))
    last_start = ((n - win) // 7) * 7
    print(f"  {names[w][:22]:22s} n={n} rolling_sharpe_last={rep.rolling_sharpe_last:7.2f} covers days [{last_start},{last_start+win}) "
          f"-> misses last {n-last_start-win} days; Sharpe of the true last {win} days={S.sharpe(a[-win:]):7.2f}")
