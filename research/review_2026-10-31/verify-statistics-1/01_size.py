"""Size of the repo's HAC t-test at Holm-level alphas under several true-null DGPs.
First validates the vectorized implementation against polyrea's hac_t_test."""
import sys, time
import numpy as np
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from polyrea.stats.significance import hac_t_test, newey_west_lags  # noqa
from hac_vec import hac_t_rows, nw94_lags  # noqa

rng = np.random.default_rng(12345)

# --- validation against the repo function
Xv = rng.standard_normal((300, 69)).cumsum(1) * 0.01 + rng.standard_normal((300, 69))
tv, pv = hac_t_rows(Xv)
ref = np.array([[hac_t_test(x).statistic, hac_t_test(x).p_value] for x in Xv])
print("validation max|dt|=%.2e max|dp|=%.2e lags(69)=%d lags(448)=%d" % (
    np.max(np.abs(tv - ref[:, 0])), np.max(np.abs(pv - ref[:, 1])), newey_west_lags(69), newey_west_lags(448)))


def ar1(R, n, phi):
    x = np.empty((R, n))
    x[:, 0] = rng.standard_normal(R) / np.sqrt(1 - phi ** 2)
    eps = rng.standard_normal((R, n))
    for j in range(1, n):
        x[:, j] = phi * x[:, j - 1] + eps[:, j]
    return x


DGPS = {
    "iid N n=69": (69, lambda R, n: rng.standard_normal((R, n))),
    "AR1 0.3 n=69": (69, lambda R, n: ar1(R, n, 0.3)),
    "AR1 0.6 n=69": (69, lambda R, n: ar1(R, n, 0.6)),
    "carry(+1 .9/-9 .1) n=69": (69, lambda R, n: np.where(rng.random((R, n)) < 0.9, 1.0, -9.0)),
    "iid N n=448": (448, lambda R, n: rng.standard_normal((R, n))),
    "iid t3 n=69": (69, lambda R, n: rng.standard_t(3, (R, n))),
}
ALPHAS = [0.05 / 500, 0.05 / 334, 1e-3, 0.01, 0.05]
REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
CH = 100_000
print(f"reps={REPS}")
print("%-26s" % "DGP" + "".join("%13s" % f"a={a:.2e}" for a in ALPHAS) + "   FWER(334 nulls, Holm m=500)  FWER(alpha=.05/334)")
for name, (n, gen) in DGPS.items():
    t0 = time.time()
    cnt = np.zeros(len(ALPHAS))
    done = 0
    ch = CH if n < 200 else 25_000
    while done < REPS:
        R = min(ch, REPS - done)
        _, p = hac_t_rows(gen(R, n))
        cnt += np.array([(p < a).sum() for a in ALPHAS])
        done += R
    rate = cnt / REPS
    fw500 = 1 - (1 - rate[0]) ** 334
    fw334 = 1 - (1 - rate[1]) ** 334
    print("%-26s" % name + "".join("%13s" % f"{r:.2e}({r/a:.1f}x)" for r, a in zip(rate, ALPHAS))
          + f"   {fw500:6.1%} (events={int(cnt[0])})   {fw334:6.1%}   [{time.time()-t0:.0f}s]")
