"""Significance tests for a wallet's PnL stream.

All tests are one-sided (H1: mean PnL > 0) unless stated. Daily PnL is
autocorrelated (multi-day positions, mark-to-market), so the primary tests use
heteroskedasticity-and-autocorrelation-consistent (Newey-West) standard errors
and a stationary block bootstrap rather than iid formulas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class TestResult:
    name: str
    statistic: float
    p_value: float
    n: int
    detail: str = ""


def _clean(x: np.ndarray | list[float]) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    return a[np.isfinite(a)]


def newey_west_lags(n: int) -> int:
    """Standard automatic bandwidth floor(4 (n/100)^(2/9))."""
    return max(1, int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0))))


def hac_variance_of_mean(x: np.ndarray, lags: int | None = None) -> float:
    x = _clean(x)
    n = len(x)
    if n < 2:
        return float("nan")
    lags = newey_west_lags(n) if lags is None else lags
    e = x - x.mean()
    gamma0 = float(e @ e) / n
    s = gamma0
    for k in range(1, min(lags, n - 1) + 1):
        w = 1.0 - k / (lags + 1.0)  # Bartlett kernel
        s += 2.0 * w * float(e[k:] @ e[:-k]) / n
    return max(s, 1e-300) / n


def hac_t_test(x: np.ndarray | list[float], lags: int | None = None, reference: str = "t") -> TestResult:
    """One-sided t-test of mean > 0 with Newey-West standard error.

    ``reference="t"`` compares the statistic with t(n-1), which is too
    thin-tailed for a HAC statistic in short samples: at the tiny alphas a
    Holm correction over hundreds of wallets needs, it over-rejects several
    fold. ``reference="exact"`` uses the statistic's exact null distribution
    for iid Gaussian data with the same n and lag count
    (:func:`hac_exact_pvalue`).
    """
    a = _clean(x)
    n = len(a)
    if n < 5:
        return TestResult("hac_t", float("nan"), 1.0, n, "too few observations")
    L = newey_west_lags(n) if lags is None else lags
    se = math.sqrt(hac_variance_of_mean(a, L))
    t = float(a.mean() / se) if se > 0 else float("inf") * np.sign(a.mean())
    if a.std() == 0:  # constant series: no evidence either way
        return TestResult("hac_t", float("nan"), 1.0, n, f"lags={L}; constant series")
    p = hac_exact_pvalue(t, n, L) if reference == "exact" else float(stats.t.sf(t, df=n - 1))
    return TestResult("hac_t", t, p, n, f"lags={L}; reference={reference}")


_Q_CACHE: dict[tuple[int, int], np.ndarray] = {}


def _hac_q_samples(n: int, lags: int, draws: int = 40_000, seed: int = 20261030) -> np.ndarray:
    """Draws of Q = s / sigma^2 for iid N(0, sigma^2) data of length n.

    With e = M eps (demeaned noise) the HAC variance estimate is
    s = sigma^2 * eps' M W M eps / n, W the Bartlett-weighted Toeplitz matrix,
    so Q is a weighted sum of chi-square(1) variables with weights equal to
    the eigenvalues of M W M / n, independent of the sample mean.
    """
    key = (n, min(lags, n - 1))
    if key in _Q_CACHE:
        return _Q_CACHE[key]
    L = key[1]
    w = np.zeros(n)
    w[0] = 1.0
    for k in range(1, L + 1):
        w[k] = 1.0 - k / (L + 1.0)
    idx = np.abs(np.subtract.outer(np.arange(n), np.arange(n)))
    W = w[idx]
    M = np.eye(n) - 1.0 / n
    lam = np.linalg.eigvalsh(M @ W @ M) / n
    lam = lam[lam > 1e-12]
    rng = np.random.default_rng(seed)
    q = np.empty(draws)
    chunk = max(1, min(draws, 4_000_000 // max(1, len(lam))))
    for i in range(0, draws, chunk):
        m = min(chunk, draws - i)
        q[i : i + m] = (rng.chisquare(1.0, size=(m, len(lam))) * lam).sum(axis=1)
    _Q_CACHE[key] = np.maximum(q, 1e-300)
    return _Q_CACHE[key]


def hac_exact_pvalue(t: float, n: int, lags: int) -> float:
    """P(T >= t) for the HAC t statistic under iid Gaussian data.

    T = Z / sqrt(Q) with Z ~ N(0, 1) independent of Q, so
    P(T >= t) = E_Q[Phi(-t sqrt(Q))]: the normal tail is evaluated exactly
    for every draw of Q (conditional Monte Carlo), which keeps the relative
    error small even for p-values around 1e-6.
    """
    if not np.isfinite(t):
        return 0.0 if t > 0 else 1.0
    q = _hac_q_samples(n, lags)
    logs = stats.norm.logsf(t * np.sqrt(q))
    mx = float(np.max(logs))
    return float(min(1.0, math.exp(mx) * np.mean(np.exp(logs - mx))))


def stationary_bootstrap_pvalue(
    x: np.ndarray | list[float], n_boot: int = 5000, mean_block: float | None = None, seed: int = 0
) -> TestResult:
    """Politis-Romano stationary bootstrap test of mean > 0.

    The series is centered (imposing the null) and resampled in geometric
    blocks; p = share of bootstrap means >= observed mean (with +1 smoothing).
    """
    a = _clean(x)
    n = len(a)
    if n < 5:
        return TestResult("stationary_bootstrap", float("nan"), 1.0, n, "too few observations")
    rng = np.random.default_rng(seed)
    mean_block = mean_block or max(2.0, n ** (1 / 3))
    p_new = 1.0 / mean_block
    centered = a - a.mean()
    obs = a.mean()
    # vectorized index generation: start new block with prob p_new
    idx = np.empty((n_boot, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, n_boot)
    starts = rng.random((n_boot, n)) < p_new
    jumps = rng.integers(0, n, (n_boot, n))
    for j in range(1, n):
        idx[:, j] = np.where(starts[:, j], jumps[:, j], (idx[:, j - 1] + 1) % n)
    boot_means = centered[idx].mean(axis=1)
    p = (1 + int(np.sum(boot_means >= obs))) / (n_boot + 1)
    return TestResult("stationary_bootstrap", float(obs), float(p), n, f"mean_block={mean_block:.1f}, n_boot={n_boot}")


def sign_test(x: np.ndarray | list[float]) -> TestResult:
    """Binomial test that P(day > 0) > 1/2 (zero days dropped)."""
    a = _clean(x)
    a = a[a != 0]
    n = len(a)
    if n == 0:
        return TestResult("sign", float("nan"), 1.0, 0)
    k = int(np.sum(a > 0))
    p = float(stats.binomtest(k, n, 0.5, alternative="greater").pvalue)
    return TestResult("sign", k / n, p, n, f"{k}/{n} positive")


def sharpe(x: np.ndarray | list[float], periods_per_year: float = 365.0) -> float:
    a = _clean(x)
    if len(a) < 2:
        return float("nan")
    sd = a.std(ddof=1)
    if sd == 0:
        return float("inf") if a.mean() > 0 else float("nan")
    return float(a.mean() / sd * math.sqrt(periods_per_year))


def probabilistic_sharpe_ratio(x: np.ndarray | list[float], sr_benchmark: float = 0.0) -> float:
    """Bailey & Lopez de Prado PSR: P(true per-period SR > benchmark).

    Uses non-annualized SR and adjusts its standard error for skew/kurtosis.
    """
    a = _clean(x)
    n = len(a)
    if n < 5 or a.std(ddof=1) == 0:
        return float("nan")
    sr = a.mean() / a.std(ddof=1)
    g3 = float(stats.skew(a))
    g4 = float(stats.kurtosis(a, fisher=False))
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr**2))
    z = (sr - sr_benchmark) * math.sqrt(n - 1) / denom
    return float(stats.norm.cdf(z))


def deflated_sharpe_ratio(x: np.ndarray | list[float], n_trials: int, sr_trials_std: float | None = None) -> float:
    """PSR against the expected maximum SR of ``n_trials`` independent null trials.

    Under the null every trial is noise, so the dispersion of SR estimates
    across trials is the sampling std of one SR estimate, ~1/sqrt(T-1), which
    is the default. Passing the cross-sectional std of *observed* SRs instead
    mixes genuine skill and short-history noise into the null and makes the
    benchmark arbitrarily strict, so it is only accepted explicitly.
    """
    a = _clean(x)
    if n_trials <= 1 or len(a) < 5:
        return probabilistic_sharpe_ratio(a, 0.0)
    sd = sr_trials_std if sr_trials_std is not None else 1.0 / math.sqrt(len(a) - 1)
    return probabilistic_sharpe_ratio(a, expected_max_sr(n_trials, sd))


def expected_max_sr(n_trials: int, sr_std: float) -> float:
    """Expected maximum of ``n_trials`` null SR estimates with std ``sr_std``."""
    em = 0.5772156649
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * math.e))
    return sr_std * ((1 - em) * z1 + em * z2)


def max_drawdown(cumulative: np.ndarray | list[float]) -> float:
    c = _clean(cumulative)
    if len(c) == 0:
        return 0.0
    peak = np.maximum.accumulate(np.concatenate([[0.0], c]))[1:]
    return float(np.max(peak - c)) if len(c) else 0.0


def holm_bonferroni(pvals: list[float]) -> list[float]:
    """Holm step-down adjusted p-values (family-wise error control)."""
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj.tolist()


def benjamini_hochberg(pvals: list[float]) -> list[float]:
    """BH step-up adjusted p-values (false discovery rate control)."""
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    order = np.argsort(p)[::-1]
    adj = np.empty(m)
    running = 1.0
    for rank_from_top, i in enumerate(order):
        rank = m - rank_from_top
        running = min(running, p[i] * m / rank)
        adj[i] = min(1.0, running)
    return adj.tolist()


def permutation_pvalue(observed: float, null_samples: np.ndarray, greater: bool = True) -> float:
    null_samples = np.asarray(null_samples, dtype=float)
    k = int(np.sum(null_samples >= observed)) if greater else int(np.sum(null_samples <= observed))
    return (1 + k) / (1 + len(null_samples))
