"""Field null again (same resampling as 05), comparing the repo test with an
exactly calibrated reference (iid-Gaussian finite-sample critical value for the
same n and NW94 lags, i.e. the fixed-b-type correction the claim proposes), and
showing which wallets drive the false rejections."""
import pickle, sys
import numpy as np
from scipy import stats, linalg, optimize
HERE = __file__.rsplit("/", 1)[0]
sys.path.insert(0, "/home/user/PolymarketResearchAgent"); sys.path.insert(0, HERE)
from hac_vec import hac_t_rows, nw94_lags  # noqa

D = pickle.load(open(f"{HERE}/series.pkl", "rb")); S = D["series"]
tested = [w for w in D["order"] if w in S and len(S[w]["pre"]) >= 60]
rng = np.random.default_rng(2024)
B = 4000; BLOCK = 10.0; ALPHA = 0.05 / 500
crit = {}


def c_exact(n):
    if n not in crit:
        L = nw94_lags(n)
        w = np.zeros(n); w[0] = 1
        for k in range(1, L + 1):
            w[k] = 1 - k / (L + 1)
        M = np.eye(n) - 1.0 / n
        lam = np.linalg.eigvalsh(M @ linalg.toeplitz(w) @ M); lam = lam[lam > 1e-12]
        R = 60_000
        Q = np.zeros(R)
        for i in range(0, len(lam), 64):
            Q += (rng.standard_normal((R, len(lam[i:i + 64]))) ** 2) @ lam[i:i + 64]
        f = lambda c: np.mean(stats.norm.sf(c * np.sqrt(Q / n))) - ALPHA
        crit[n] = optimize.brentq(f, 2.0, 20.0)
    return crit[n]


rows = []
for w in tested:
    x = S[w]["pre"]; n = len(x); c = x - x.mean()
    idx = np.empty((B, n), np.int64); idx[:, 0] = rng.integers(0, n, B)
    st = rng.random((B, n)) < 1 / BLOCK; jp = rng.integers(0, n, (B, n))
    for j in range(1, n):
        idx[:, j] = np.where(st[:, j], jp[:, j], (idx[:, j - 1] + 1) % n)
    X = c[idx]
    t, p = hac_t_rows(X)
    r_repo = np.mean(p < ALPHA); r_fix = np.mean(t > c_exact(n))
    sd = c.std(); sk = float((c ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    share_neg = np.mean(c < 0)  # most days below the mean = "rare big win" shape; few = "rare big loss" (carry)
    rows.append((w, n, r_repo, r_fix, sk, float(np.mean(x == 0)), float(np.mean(x < 0))))

r_repo = np.array([r[2] for r in rows]); r_fix = np.array([r[3] for r in rows])
sk = np.array([r[4] for r in rows])
print(f"t(n-1)/exact critical value at 1e-4: n=69 {stats.t.isf(ALPHA, 68):.3f}/{c_exact(69):.3f}  n=152 {stats.t.isf(ALPHA,151):.3f}/{c_exact(152):.3f}")
print(f"field-null FWER over 334 (HAC step only): repo {1-np.prod(1-r_repo):.1%} (E#={r_repo.sum():.2f}); exact-calibrated {1-np.prod(1-r_fix):.1%} (E#={r_fix.sum():.2f})")
ok = sk > -1
print(f"excluding {np.sum(~ok)} left-skewed wallets (skew<-1, carry-like): repo {1-np.prod(1-r_repo[ok]):.1%} (E#={r_repo[ok].sum():.2f}); exact {1-np.prod(1-r_fix[ok]):.1%} (E#={r_fix[ok].sum():.2f})")
print("top contributors (repo rate): name n rate_repo rate_exact skew share_zero_days share_neg_days")
for r in sorted(rows, key=lambda r: -r[2])[:12]:
    print(f"  {str(S[r[0]]['name'])[:22]:22s} {r[1]:4d} {r[2]:.3f} {r[3]:.3f} skew={r[4]:6.2f} zero={r[5]:.2f} neg={r[6]:.2f}")
