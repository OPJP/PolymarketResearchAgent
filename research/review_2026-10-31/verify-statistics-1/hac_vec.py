"""Vectorized copy of polyrea.stats.significance.hac_t_test (rows = replications)."""
import math
import numpy as np
from scipy import stats


def nw94_lags(n):
    return max(1, int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0))))


def hac_t_rows(X, lags=None, bandwidth=None):
    """t statistics and one-sided p (t(n-1) reference) per row.
    lags: integer L with Bartlett weights 1-k/(L+1) (the repo's convention).
    bandwidth: continuous Andrews S_T with weights 1-k/S_T for k<S_T (overrides lags)."""
    X = np.asarray(X, float)
    R, n = X.shape
    m = X.mean(1)
    e = X - m[:, None]
    s = np.einsum("ij,ij->i", e, e) / n
    if bandwidth is not None:
        kmax = min(n - 1, int(math.ceil(bandwidth)) - 1)
        ws = [(k, 1 - k / bandwidth) for k in range(1, kmax + 1) if 1 - k / bandwidth > 0]
    else:
        L = nw94_lags(n) if lags is None else lags
        ws = [(k, 1.0 - k / (L + 1.0)) for k in range(1, min(L, n - 1) + 1)]
    for k, w in ws:
        s = s + 2.0 * w * np.einsum("ij,ij->i", e[:, k:], e[:, :-k]) / n
    se = np.sqrt(np.maximum(s, 1e-300) / n)
    t = m / se
    p = stats.t.sf(t, df=n - 1)
    return t, p
