"""Check each formula in polyrea/stats against an independent reference."""
import math

import numpy as np
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests

import common  # noqa: F401  (sets sys.path)
from polyrea.stats import persistence as P
from polyrea.stats import significance as S

rng = np.random.default_rng(0)


def ar1(n, phi, rng, mu=0.0):
    e = rng.standard_normal(n)
    x = np.empty(n)
    x[0] = e[0] / math.sqrt(1 - phi**2)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x + mu


print("== 1. Newey-West variance of the mean vs statsmodels OLS(const) HAC, Bartlett, no small-sample correction")
worst = 0
for n in (30, 69, 123, 448, 1279):
    x = ar1(n, 0.4, rng, 0.1)
    L = S.newey_west_lags(n)
    r = sm.OLS(x, np.ones(n)).fit(cov_type="HAC", cov_kwds={"maxlags": L, "use_correction": False})
    mine = S.hac_variance_of_mean(x)
    worst = max(worst, abs(mine / r.cov_params()[0, 0] - 1))
    print(f"  n={n:5d} lags={L} repo={mine:.6e} statsmodels={r.cov_params()[0,0]:.6e}")
print(f"  max rel diff {worst:.2e}")
print("  bandwidth floor(4(n/100)^(2/9)) for n=30,60,69,100,448,1279:", [S.newey_west_lags(n) for n in (30, 60, 69, 100, 448, 1279)])

print("== 2. HAC trend slope vs statsmodels OLS([1,t]) HAC")
for n in (40, 186, 477):
    x = ar1(n, 0.3, rng, 1.0) - 0.002 * np.arange(n)
    res = P.trend_test(x)
    X = sm.add_constant(np.arange(n, dtype=float))
    L = S.newey_west_lags(n)
    r = sm.OLS(x, X).fit(cov_type="HAC", cov_kwds={"maxlags": L, "use_correction": False})
    print(f"  n={n} repo z={res.statistic:.6f} statsmodels z={r.params[1]/r.bse[1]:.6f} slope repo={res.detail} sm={r.params[1]:.4g}")

print("== 3. Holm / BH vs statsmodels.multipletests (with ties)")
mx_h = mx_b = 0
for _ in range(200):
    m = rng.integers(1, 60)
    p = np.round(rng.random(m) ** 3, 3)
    mx_h = max(mx_h, np.max(np.abs(np.array(S.holm_bonferroni(p)) - multipletests(p, method="holm")[1])))
    mx_b = max(mx_b, np.max(np.abs(np.array(S.benjamini_hochberg(p)) - multipletests(p, method="fdr_bh")[1])))
print(f"  max |diff| Holm={mx_h:.2e} BH={mx_b:.2e}")

print("== 4. Expected max of N null SRs: formula vs Monte Carlo (sr_std=1)")
for N in (10, 100, 500):
    mc = np.mean(np.max(rng.standard_normal((20000, N)), axis=1))
    print(f"  N={N:4d} formula={S.expected_max_sr(N, 1.0):.4f} MC mean max={mc:.4f}")

print("== 5. PSR vs an independent implementation of Bailey & Lopez de Prado (2012) eq.")
for skew_case in ("normal", "neg-skew", "pos-skew"):
    if skew_case == "normal":
        x = rng.standard_normal(250) + 0.2
    elif skew_case == "neg-skew":
        x = np.where(rng.random(250) < 0.05, -8.0, 1.0)
    else:
        x = np.where(rng.random(250) < 0.05, 12.0, -0.3)
    sr = x.mean() / x.std(ddof=1)
    g3 = stats.skew(x)
    g4 = stats.kurtosis(x, fisher=False)
    ref = stats.norm.cdf(sr * math.sqrt(len(x) - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr**2))
    print(f"  {skew_case:8s} SR={sr:.3f} g3={g3:.2f} g4={g4:.2f} repo={S.probabilistic_sharpe_ratio(x):.6f} ref={ref:.6f}")

print("== 6. DSR null calibration (max-SR of 500 iid N(0,1) wallets, T=200) and of 500 AR(1) phi=0.3 wallets")
for phi in (0.0, 0.3):
    ex = 0
    reps = 60
    for _ in range(reps):
        X = rng.standard_normal((500, 200))
        if phi:
            for j in range(1, 200):
                X[:, j] = phi * X[:, j - 1] + X[:, j]
        srs = X.mean(1) / X.std(1, ddof=1)
        best = X[np.argmax(srs)]
        ex += S.deflated_sharpe_ratio(best, n_trials=500) > 0.95
    print(f"  phi={phi}: share of null 'best of 500' with DSR>0.95 = {ex/reps:.3f} (nominal <= 0.05)")

print("== 7. CUSUM: kstwobign is sup|Brownian bridge|; null size at 5%")
for phi in (0.0, 0.3, 0.6):
    for n in (104, 477):
        rej = np.mean([P.cusum_test(ar1(n, phi, rng)).p_value < 0.05 for _ in range(1000)])
        print(f"  phi={phi} n={n}: rejection rate {rej:.3f}")

print("== 8. Stationary bootstrap direction/centering")
for mu in (-0.3, 0.0, 0.3):
    x = ar1(120, 0.3, np.random.default_rng(5), mu)
    print(f"  mu={mu:+.1f}: mean={x.mean():+.3f} p_boot={S.stationary_bootstrap_pvalue(x, n_boot=4000).p_value:.4f} p_hac={S.hac_t_test(x).p_value:.4f}")
