"""Exact finite-sample p-values of the HAC t statistic under an iid Gaussian null
(what the t(n-1) reference is supposed to approximate; fixed-b theory approximates
the same thing). Under iid N, t = Z / sqrt(Q/n) with Z ~ N(0,1) independent of
Q = sum_k lam_k chi2_1, lam = eig(M W M), M = centering, W = Bartlett weights.
P(t > c) = E_Q[ Phi_bar(c sqrt(Q/n)) ], estimated by Monte Carlo over Q.
Then: does the Holm/A1 outcome under NW94 and Schwert lags change once the
reference distribution is exact?"""
import json, math, pickle, sys
import numpy as np
from scipy import stats, linalg
HERE = __file__.rsplit("/", 1)[0]
sys.path.insert(0, "/home/user/PolymarketResearchAgent"); sys.path.insert(0, HERE)
from polyrea.stats.significance import holm_bonferroni  # noqa
from hac_vec import hac_t_rows  # noqa

rng = np.random.default_rng(7)
D = pickle.load(open(f"{HERE}/series.pkl", "rb")); S = D["series"]; order = D["order"]
LR = pickle.load(open(f"{HERE}/lag_rules.pkl", "rb"))
a1 = json.load(open("/home/user/PolymarketResearchAgent/research/stage_a/stage_a1.json"))
rows = {r["wallet"]: r for r in a1["wallets"]}
other_ok = {w: all("Holm" in rs for rs in rows[w]["stage_a1_reasons"]) for w in order}
base_pass = set(a1["evidence"]["derived"]["a1_pass"])
_cache = {}


def q_draws(n, L, R):
    key = (n, L)
    if key not in _cache:
        w = np.zeros(n); w[0] = 1.0
        for k in range(1, min(L, n - 1) + 1):
            w[k] = 1.0 - k / (L + 1.0)
        W = linalg.toeplitz(w)
        M = np.eye(n) - 1.0 / n
        lam = np.linalg.eigvalsh(M @ W @ M)
        lam = lam[lam > 1e-12]
        Q = np.zeros(R)
        for i in range(0, len(lam), 64):
            Q += (rng.standard_normal((R, len(lam[i:i + 64]))) ** 2) @ lam[i:i + 64]
        _cache[key] = Q
    return _cache[key]


def exact_p(t, n, L, R=400_000):
    Q = q_draws(n, L, R)
    return float(np.mean(stats.norm.sf(t * np.sqrt(Q / n))))


# sanity check against brute-force simulation at moderate tail
n, L = 69, 3
X = rng.standard_normal((400_000, n)); tt, _ = hac_t_rows(X, lags=L)
c = stats.t.isf(1e-3, n - 1)
print(f"check n=69 L=3: brute P(t>t68_.001)={np.mean(tt > c):.2e}  exact-MC={exact_p(c, n, L):.2e}")
for a in [1e-4, 1.5e-4]:
    c = stats.t.isf(a, n - 1)
    print(f"  nominal {a:.1e}: exact size of t(68) ref = {exact_p(c, n, L):.2e}")
for L in [10]:
    c = stats.t.isf(1e-4, n - 1)
    print(f"  Schwert L=10, n=69: exact size of t(68) ref at 1e-4 = {exact_p(c, 69, L):.2e}")

rules = {"NW94 [repo]": lambda n: max(1, int(4 * (n / 100) ** (2 / 9))),
         "Schwert": lambda n: max(1, int(12 * (n / 100) ** 0.25))}
tested = [w for w in order if w in S and len(S[w]["pre"]) >= 60]
for rname, Lf in rules.items():
    key = [k for k in LR if k.startswith(rname.split(" ")[0])][0]
    p_nom = LR[key][0]
    p_ex = {}
    for w in tested:
        x = S[w]["pre"]; n = len(x); L = Lf(n)
        if p_nom[w] < 2e-3:  # only these can be near Holm thresholds
            t = float(hac_t_rows(x[None, :], lags=L)[0][0])
            p_ex[w] = exact_p(t, n, L, R=400_000 if n < 400 else 100_000)
        else:
            p_ex[w] = p_nom[w]
    holm = dict(zip(order, holm_bonferroni([p_ex.get(w, 1.0) for w in order])))
    passed = {w for w in tested if other_ok[w] and holm[w] <= 0.05}
    print(f"\n{rname}: exact-iid-calibrated A1 passes {len(passed)}; lost {sorted(S[w]['name'] for w in base_pass - passed)}; new {sorted(S[w]['name'] for w in passed - base_pass)}")
    for w in sorted([w for w in tested if p_nom[w] < 2e-3 and (other_ok[w] or w in base_pass)], key=lambda w: p_ex[w]):
        print(f"   {str(S[w]['name'])[:20]:20s} n={len(S[w]['pre']):4d} L={Lf(len(S[w]['pre'])):2d} p_t(n-1)={p_nom[w]:.2e} p_exact={p_ex[w]:.2e} holm={holm[w]:.3f} {'PASS' if w in passed else ''}")
