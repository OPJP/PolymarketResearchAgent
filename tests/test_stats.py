import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from polyrea.stats import persistence as P
from polyrea.stats import significance as S


def _ar1(n, phi, rng, mu=0.0):
    e = rng.standard_normal(n)
    x = np.empty(n)
    x[0] = e[0]
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x + mu


def test_hac_t_size_under_autocorrelated_null():
    """HAC test keeps roughly nominal size where the iid t-test over-rejects."""
    rng = np.random.default_rng(1)
    rej_hac = rej_iid = 0
    reps = 400
    for _ in range(reps):
        x = _ar1(250, 0.6, rng)
        rej_hac += S.hac_t_test(x).p_value < 0.05
        from scipy import stats

        rej_iid += stats.ttest_1samp(x, 0, alternative="greater").pvalue < 0.05
    assert rej_hac / reps < 0.10
    assert rej_iid / reps > rej_hac / reps  # naive test is anti-conservative


def test_hac_t_power():
    rng = np.random.default_rng(2)
    x = rng.standard_normal(200) + 0.5
    r = S.hac_t_test(x)
    assert r.p_value < 1e-6 and r.statistic > 5


def test_bootstrap_calibration_and_power():
    rng = np.random.default_rng(3)
    null_p = [S.stationary_bootstrap_pvalue(_ar1(120, 0.3, rng), n_boot=500, seed=i).p_value for i in range(120)]
    assert 0.0 < np.mean(np.array(null_p) < 0.05) < 0.12
    alt = S.stationary_bootstrap_pvalue(rng.standard_normal(150) + 0.6, n_boot=2000)
    assert alt.p_value < 0.002


def test_sign_test():
    r = S.sign_test([1] * 30 + [-1] * 5)
    assert r.p_value < 1e-4
    assert S.sign_test([0, 0]).p_value == 1.0


@given(st.lists(st.floats(0, 1), min_size=1, max_size=60))
def test_holm_properties(p):
    adj = S.holm_bonferroni(p)
    assert all(a >= b - 1e-12 for a, b in zip(adj, p))
    assert all(0 <= a <= 1 for a in adj)
    order = np.argsort(p)
    assert all(adj[order[i]] <= adj[order[i + 1]] + 1e-12 for i in range(len(p) - 1))


@given(st.lists(st.floats(0, 1), min_size=1, max_size=60))
def test_bh_properties(p):
    adj = S.benjamini_hochberg(p)
    holm = S.holm_bonferroni(p)
    assert all(a >= b - 1e-12 for a, b in zip(adj, p))
    assert all(a <= h + 1e-12 for a, h in zip(adj, holm))  # BH never stricter than Holm


def test_bh_known_values():
    # classic example: p = [0.01, 0.04, 0.03, 0.005] -> BH adj [0.02, 0.04, 0.04, 0.02]
    assert np.allclose(S.benjamini_hochberg([0.01, 0.04, 0.03, 0.005]), [0.02, 0.04, 0.04, 0.02])
    assert np.allclose(S.holm_bonferroni([0.01, 0.04, 0.03, 0.005]), [0.03, 0.06, 0.06, 0.02])


@given(st.lists(st.floats(-1e6, 1e6), min_size=3, max_size=50), st.floats(0.1, 100))
@settings(max_examples=50)
def test_sharpe_scale_invariant(x, k):
    a = np.array(x)
    if a.std() < 1e-6:
        return
    assert S.sharpe(a) == pytest.approx(S.sharpe(a * k), rel=1e-6)


def test_max_drawdown():
    assert S.max_drawdown(np.cumsum([1, 1, 1])) == 0
    assert S.max_drawdown(np.cumsum([5, -3, 1, -4])) == pytest.approx(6)
    assert S.max_drawdown(np.cumsum([-2, 1])) == pytest.approx(2)  # drawdown from zero start


def test_psr_and_dsr_ordering():
    rng = np.random.default_rng(4)
    x = rng.standard_normal(300) * 1.0 + 0.15
    psr = S.probabilistic_sharpe_ratio(x)
    dsr = S.deflated_sharpe_ratio(x, n_trials=500, sr_trials_std=0.1)
    assert 0.9 < psr <= 1.0
    assert dsr < psr  # deflating for selection can only lower confidence
    assert S.deflated_sharpe_ratio(x, n_trials=500) < psr


def test_dsr_null_calibration():
    """Max of 500 null wallets should rarely clear DSR 0.95 (that is its purpose)."""
    rng = np.random.default_rng(11)
    exceed = 0
    for rep in range(20):
        best = max((rng.standard_normal(200) for _ in range(500)), key=lambda a: a.mean() / a.std())
        exceed += S.deflated_sharpe_ratio(best, n_trials=500) > 0.95
    assert exceed <= 3


def test_dsr_passes_strong_real_edge():
    rng = np.random.default_rng(12)
    x = rng.standard_normal(200) * 1.0 + 0.5  # daily SR 0.5 ~ annual 9.6
    assert S.deflated_sharpe_ratio(x, n_trials=500) > 0.99


def test_persistence_detects_decay():
    rng = np.random.default_rng(5)
    decayed = np.concatenate([rng.standard_normal(150) + 1.0, rng.standard_normal(40) - 0.2])
    rep = P.persistence_report(decayed, recent_days=30)
    assert rep.decline.p_value < 0.01
    assert rep.recent.p_value > 0.05
    assert rep.cusum_break.p_value < 0.05


def test_persistence_stable_edge():
    rng = np.random.default_rng(6)
    stable = rng.standard_normal(200) + 0.8
    rep = P.persistence_report(stable, recent_days=30)
    assert rep.recent.p_value < 0.01
    assert rep.decline.p_value > 0.05
    assert rep.trend.p_value > 0.05


def test_cusum_null_size():
    rng = np.random.default_rng(7)
    rej = np.mean([P.cusum_test(rng.standard_normal(200)).p_value < 0.05 for _ in range(300)])
    assert rej < 0.09
