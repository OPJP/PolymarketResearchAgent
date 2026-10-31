"""The A1 significance gate is a conjunction: Holm(HAC) <= .05 AND raw stationary
bootstrap p < .01 AND deflated Sharpe > .95 (n_trials=500). Under the synthetic
nulls of 01_size.py, how often does a null wallet clear all three (DSR computed
on the pre-selection series only, i.e. without the selected ranking window)?"""
import sys
import numpy as np
sys.path.insert(0, "/home/user/PolymarketResearchAgent"); sys.path.insert(0, __file__.rsplit("/", 1)[0])
from polyrea.stats.significance import stationary_bootstrap_pvalue, deflated_sharpe_ratio  # noqa
from hac_vec import hac_t_rows  # noqa

rng = np.random.default_rng(99)


def ar1(R, n, phi):
    x = np.empty((R, n)); x[:, 0] = rng.standard_normal(R) / np.sqrt(1 - phi ** 2)
    e = rng.standard_normal((R, n))
    for j in range(1, n):
        x[:, j] = phi * x[:, j - 1] + e[:, j]
    return x


DGPS = {
    "iid N n=69": (69, lambda R, n: rng.standard_normal((R, n))),
    "AR1 0.3 n=69": (69, lambda R, n: ar1(R, n, 0.3)),
    "AR1 0.6 n=69": (69, lambda R, n: ar1(R, n, 0.6)),
    "carry n=69": (69, lambda R, n: np.where(rng.random((R, n)) < 0.9, 1.0, -9.0)),
}
ALPHA = 0.05 / 500
REPS = 1_000_000
CAP = 600
for name, (n, gen) in DGPS.items():
    hits = []; done = 0
    while done < REPS:
        X = gen(100_000, n); _, p = hac_t_rows(X); done += 100_000
        hits.extend(X[p < ALPHA])
    k = len(hits); r_hac = k / done
    sub = hits[:CAP]
    boot = np.array([stationary_bootstrap_pvalue(x, n_boot=4000).p_value for x in sub])
    dsr = np.array([deflated_sharpe_ratio(x, n_trials=500) for x in sub])
    dsr_ok = ~(dsr < 0.95)  # repo: nan does not fail (`nan < .95` is False)
    f_b = np.mean(boot < 0.01); f_all = np.mean((boot < 0.01) & dsr_ok)
    r_all = r_hac * f_all
    print(f"{name:14s} P(HAC p<1e-4)={r_hac:.2e} | given that: boot<.01 {f_b:.2f}, boot&DSR {f_all:.3f} (of {len(sub)}) "
          f"=> per-wallet conj rate {r_all:.1e}; FWER(334): HAC-only {1-(1-r_hac)**334:.1%}, HAC+boot {1-(1-r_hac*f_b)**334:.1%}, full gate {1-(1-r_all)**334:.2%}")
