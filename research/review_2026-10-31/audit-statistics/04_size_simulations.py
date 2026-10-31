"""Null rejection rates of the repo's HAC t-test (vectorised re-implementation, verified equal
to S.hac_t_test on a sample) and of the stationary bootstrap, at the alphas that the screen
actually uses: 0.05 (persistence), 0.01 (bootstrap), and ~1.5e-4 / 1e-4 (what Holm over
334/500 wallets demands of the best wallet)."""
import math

import numpy as np
from scipy import stats

import common  # noqa: F401
from polyrea.stats import significance as S

rng = np.random.default_rng(42)


def gen(kind, reps, n, rng):
    if kind == "iid normal":
        return rng.standard_normal((reps, n))
    if kind.startswith("AR1"):
        phi = float(kind.split("=")[1])
        e = rng.standard_normal((reps, n))
        x = np.empty_like(e)
        x[:, 0] = e[:, 0] / math.sqrt(1 - phi**2)
        for j in range(1, n):
            x[:, j] = phi * x[:, j - 1] + e[:, j]
        return x
    if kind == "neg-skew 0.9/+1,-9":  # carry: small gains, rare large losses, mean 0
        return np.where(rng.random((reps, n)) < 0.1, -9.0, 1.0)
    if kind == "pos-skew 0.9/-1,+9":
        return np.where(rng.random((reps, n)) < 0.1, 9.0, -1.0)
    if kind == "t3 heavy tails":
        return rng.standard_t(3, (reps, n))
    raise ValueError(kind)


def hac_p(X):
    n = X.shape[1]
    L = S.newey_west_lags(n)
    e = X - X.mean(1, keepdims=True)
    s = (e * e).sum(1) / n
    for k in range(1, min(L, n - 1) + 1):
        s += 2 * (1 - k / (L + 1)) * (e[:, k:] * e[:, :-k]).sum(1) / n
    se = np.sqrt(np.maximum(s, 1e-300) / n)
    t = X.mean(1) / se
    return stats.t.sf(t, df=n - 1)


# sanity: vectorised == repo
X = gen("AR1=0.3", 5, 69, rng)
assert np.allclose(hac_p(X), [S.hac_t_test(x).p_value for x in X])

alphas = [0.05, 0.01, 1e-3, 1.5e-4]
print("HAC one-sided t-test, null mean 0, rejection rate (reps=200000)")
print(f"{'DGP':22s} {'n':>4s} " + " ".join(f"{a:>9.1e}" for a in alphas))
for kind in ["iid normal", "AR1=0.3", "AR1=0.6", "neg-skew 0.9/+1,-9", "pos-skew 0.9/-1,+9", "t3 heavy tails"]:
    for n in (69, 123, 448):
        reps = 200000 if n < 400 else 60000
        P = np.concatenate([hac_p(gen(kind, 20000, n, rng)) for _ in range(reps // 20000)])
        print(f"{kind:22s} {n:4d} " + " ".join(f"{np.mean(P < a):9.2e}" for a in alphas))

print("\nStationary bootstrap (repo function, n_boot=1000), null rejection rate at 0.01 and 0.05, reps=400")
for kind in ["iid normal", "AR1=0.3", "AR1=0.6", "neg-skew 0.9/+1,-9"]:
    for n in (69, 123):
        X = gen(kind, 400, n, rng)
        p = np.array([S.stationary_bootstrap_pvalue(x, n_boot=1000, seed=i).p_value for i, x in enumerate(X)])
        print(f"  {kind:22s} n={n:4d} rej@0.01={np.mean(p < 0.01):.3f} rej@0.05={np.mean(p < 0.05):.3f}  (mean block {max(2, n ** (1/3)):.1f})")
