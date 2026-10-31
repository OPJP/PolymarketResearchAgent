"""Does an edge still exist? Stability and decay tests over a PnL stream.

A strategy that "would still work if deployed now" must show (a) significant
profit in the most recent window on its own, (b) no significant downward break
in mean PnL, and (c) no significant negative trend in edge. These tests run on
the daily PnL of the wallet and of the reverse-engineered strategy's backtest.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

from polyrea.stats.significance import TestResult, _clean, hac_t_test, hac_variance_of_mean, sharpe


@dataclass(frozen=True)
class PersistenceReport:
    recent: TestResult
    earlier: TestResult
    decline: TestResult  # H1: recent mean < earlier mean
    late_decline: TestResult  # H1: last half of the recent window < its first half (regime change inside it)
    trend: TestResult  # H1: negative slope of daily PnL over time
    cusum_break: TestResult  # any mean shift
    rolling_sharpe_min: float
    rolling_sharpe_last: float
    share_positive_windows: float


def _diff_q(n1: int, n2: int) -> np.ndarray:
    """Null draws of (Q1/n1 + Q2/n2) / (1/n1 + 1/n2) for two independent iid-Gaussian samples."""
    from polyrea.stats.significance import _hac_q_samples, newey_west_lags

    key = ("diff", n1, n2)
    if key in _DIFF_CACHE:
        return _DIFF_CACHE[key]
    q1 = _hac_q_samples(n1, newey_west_lags(n1))
    q2 = np.random.default_rng(n1 * 7919 + n2).permutation(_hac_q_samples(n2, newey_west_lags(n2)))  # independent pairing
    _DIFF_CACHE[key] = (q1 / n1 + q2 / n2) / (1.0 / n1 + 1.0 / n2)
    return _DIFF_CACHE[key]


_DIFF_CACHE: dict[tuple, np.ndarray] = {}


def mean_difference_test(recent: np.ndarray, earlier: np.ndarray) -> TestResult:
    """HAC Welch-style test, H1: mean(recent) < mean(earlier) (edge decayed).

    The p-value uses the statistic's exact distribution for iid Gaussian data
    with the same sample sizes and lag counts (a N(0,1) reference over-rejects
    with short halves: 8% at a nominal 5% for 15 + 15 days)."""
    from polyrea.stats.significance import tail_from_q

    r, e = _clean(recent), _clean(earlier)
    if len(r) < 5 or len(e) < 5:
        return TestResult("mean_decline", float("nan"), 1.0, len(r) + len(e), "too few observations")
    se = math.sqrt(hac_variance_of_mean(r) + hac_variance_of_mean(e))
    z = (r.mean() - e.mean()) / se if se > 0 else 0.0
    p = tail_from_q(float(z), _diff_q(len(r), len(e)), upper=False)  # small when recent is much lower
    return TestResult("mean_decline", float(z), p, len(r) + len(e), f"recent={r.mean():.2f} earlier={e.mean():.2f}; exact reference")


def trend_test(x: np.ndarray) -> TestResult:
    """OLS slope of PnL on time with Newey-West SE, H1: slope < 0."""
    a = _clean(x)
    n = len(a)
    if n < 10:
        return TestResult("trend", float("nan"), 1.0, n, "too few observations")
    t = np.arange(n, dtype=float)
    tc = t - t.mean()
    beta = float(tc @ (a - a.mean()) / (tc @ tc))
    resid = a - a.mean() - beta * tc
    # HAC variance of beta: Var(sum tc*e)/ (sum tc^2)^2 using Bartlett weights
    u = tc * resid
    lags = max(1, int(math.floor(4 * (n / 100.0) ** (2 / 9))))
    s = float(u @ u)
    for k in range(1, min(lags, n - 1) + 1):
        s += 2 * (1 - k / (lags + 1)) * float(u[k:] @ u[:-k])
    se = math.sqrt(max(s, 1e-300)) / float(tc @ tc)
    z = beta / se
    return TestResult("trend", z, _trend_exact_lower(float(z), n, lags), n, f"slope_per_day={beta:.4g}; exact reference")


def _trend_exact_lower(z: float, n: int, lags: int) -> float:
    """P(T <= z) for the HAC slope t statistic under iid Gaussian data.

    T = Z sqrt(S) / sqrt(eps' A eps) with S = sum tc^2 and
    A = M_X D W D M_X (D = diag(tc), W Bartlett, M_X the residual maker of
    [1, t]); the quadratic form is independent of Z.
    """
    from polyrea.stats.significance import _bartlett_matrix, quadratic_form_samples, tail_from_q

    key = ("trend", n, lags)
    t = np.arange(n, dtype=float)
    tc = t - t.mean()
    S = float(tc @ tc)
    if key not in _TREND_W:
        X = np.column_stack([np.ones(n), tc])
        M = np.eye(n) - X @ np.linalg.solve(X.T @ X, X.T)
        D = np.diag(tc)
        A = M @ D @ _bartlett_matrix(n, lags) @ D @ M
        _TREND_W[key] = np.linalg.eigvalsh(A) / S
    return tail_from_q(z, quadratic_form_samples(key, _TREND_W[key]), upper=False)


_TREND_W: dict[tuple, np.ndarray] = {}


def cusum_test(x: np.ndarray) -> TestResult:
    """OLS-CUSUM test for a shift in mean (Ploberger-Kramer, HAC-scaled).

    Statistic: sup_k |S_k| / (sigma_LR * sqrt(n)) compared to the Kolmogorov
    distribution (asymptotic Brownian bridge supremum).
    """
    a = _clean(x)
    n = len(a)
    if n < 10:
        return TestResult("cusum", float("nan"), 1.0, n, "too few observations")
    e = a - a.mean()
    lr_var = hac_variance_of_mean(a) * n
    stat = float(np.max(np.abs(np.cumsum(e))) / math.sqrt(lr_var * n))
    p = float(stats.kstwobign.sf(stat))
    k = int(np.argmax(np.abs(np.cumsum(e))))
    return TestResult("cusum", stat, p, n, f"most_likely_break_index={k}")


def rolling_sharpes(x: np.ndarray, window: int = 30, step: int = 7) -> list[float]:
    a = _clean(x)
    return [sharpe(a[i : i + window]) for i in range(0, max(0, len(a) - window + 1), step)]


def persistence_report(daily_pnl: np.ndarray, recent_days: int = 30) -> PersistenceReport:
    a = _clean(daily_pnl)
    recent, earlier = a[-recent_days:], a[:-recent_days]
    rs = rolling_sharpes(a, window=min(30, max(10, len(a) // 3)))
    windows = [a[i : i + 30].sum() for i in range(0, max(0, len(a) - 29), 7)]
    return PersistenceReport(
        recent=hac_t_test(recent, reference="exact"),
        earlier=hac_t_test(earlier, reference="exact"),
        decline=mean_difference_test(recent, earlier),
        late_decline=mean_difference_test(recent[len(recent) // 2 :], recent[: len(recent) // 2]),
        trend=trend_test(a),
        cusum_break=cusum_test(a),
        rolling_sharpe_min=float(np.nanmin(rs)) if rs else float("nan"),
        rolling_sharpe_last=float(rs[-1]) if rs else float("nan"),
        share_positive_windows=float(np.mean([w > 0 for w in windows])) if windows else float("nan"),
    )
