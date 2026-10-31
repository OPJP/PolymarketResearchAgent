"""Precise null size of S.stationary_bootstrap_pvalue at alpha=0.01 exactly as the screen calls it
(n_boot=4000, default block n^(1/3)), and where the anti-conservatism comes from: the bootstrap
variance of the mean vs the true sampling variance."""
import math

import numpy as np
from scipy import stats

import common  # noqa: F401
from polyrea.stats import significance as S

rng = np.random.default_rng(7)
for n in (60, 69, 123, 250):
    reps = 1500
    ps, ratios = [], []
    for i in range(reps):
        x = rng.standard_normal(n)
        ps.append(S.stationary_bootstrap_pvalue(x, n_boot=4000, seed=i).p_value)
    ps = np.array(ps)
    r = np.mean(ps < 0.01)
    se = math.sqrt(r * (1 - r) / reps)
    print(f"iid N(0,1) n={n:4d}: P(p_boot < 0.01) = {r:.4f} +- {se:.4f}   P(p_boot<0.05) = {np.mean(ps < 0.05):.4f}")

# variance ratio for one sample, many bootstrap draws (repo's own index generator)
def boot_means(a, n_boot, seed):
    n = len(a)
    rng = np.random.default_rng(seed)
    mb = max(2.0, n ** (1 / 3))
    pn = 1 / mb
    idx = np.empty((n_boot, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, n_boot)
    starts = rng.random((n_boot, n)) < pn
    jumps = rng.integers(0, n, (n_boot, n))
    for j in range(1, n):
        idx[:, j] = np.where(starts[:, j], jumps[:, j], (idx[:, j - 1] + 1) % n)
    return (a - a.mean())[idx].mean(1)

vr = []
q99 = []
for i in range(300):
    x = rng.standard_normal(69)
    bm = boot_means(x, 4000, i)
    vr.append(bm.var() / (x.var(ddof=1) / 69))
    q99.append(np.quantile(bm, 0.99) / (x.std(ddof=1) / math.sqrt(69)))
print(f"n=69 iid: mean Var*(boot mean) / (s^2/n) = {np.mean(vr):.3f}; mean bootstrap 99% quantile in SE units = {np.mean(q99):.3f} "
      f"(t_68 0.99 quantile = {stats.t.ppf(0.99, 68):.3f})")
