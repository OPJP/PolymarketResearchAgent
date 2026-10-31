"""Recompute the A1 Holm step under alternative HAC bandwidth rules on the exact
cached series. Checks the current rule reproduces stage_a1.json first."""
import json, math, pickle, sys
import numpy as np
from scipy import stats
HERE = __file__.rsplit("/", 1)[0]
sys.path.insert(0, "/home/user/PolymarketResearchAgent"); sys.path.insert(0, HERE)
from polyrea.stats.significance import hac_t_test, holm_bonferroni  # noqa
from hac_vec import hac_t_rows  # noqa

D = pickle.load(open(f"{HERE}/series.pkl", "rb"))
S = D["series"]; order = D["order"]
a1 = json.load(open("/home/user/PolymarketResearchAgent/research/stage_a/stage_a1.json"))
rows = {r["wallet"]: r for r in a1["wallets"]}


def andrews_ar1_bw(x):
    e = x - x.mean()
    rho = float(e[1:] @ e[:-1] / (e[:-1] @ e[:-1]))
    rho = min(max(rho, -0.97), 0.97)
    a1_ = 4 * rho ** 2 / ((1 - rho) ** 2 * (1 + rho) ** 2)
    return 1.1447 * (a1_ * len(x)) ** (1 / 3)  # Bartlett S_T, weights 1 - j/S_T


def nw_auto_bw(x):
    """Newey-West (1994) data-driven Bartlett bandwidth (as in R sandwich::bwNeweyWest)."""
    n = len(x); e = x - x.mean()
    L = int(math.floor(4 * (n / 100) ** (2 / 9)))
    g = [float(e[j:] @ e[: n - j]) / n for j in range(L + 1)]
    s0 = g[0] + 2 * sum(g[1:]); s1 = 2 * sum(j * g[j] for j in range(1, L + 1))
    gam = 1.1447 * ((s1 / s0) ** 2) ** (1 / 3) if s0 > 0 else 0.0
    return max(1.0, gam * n ** (1 / 3))


RULES = {
    "NW94 4(n/100)^(2/9) [repo]": lambda x: dict(lags=None),
    "Stock-Watson 0.75 n^(1/3)": lambda x: dict(lags=max(1, int(math.floor(0.75 * len(x) ** (1 / 3))))),
    "Schwert 12(n/100)^(1/4)": lambda x: dict(lags=max(1, int(math.floor(12 * (len(x) / 100) ** 0.25)))),
    "Andrews AR(1) plug-in": lambda x: dict(bandwidth=andrews_ar1_bw(x)),
    "NW94 data-driven auto": lambda x: dict(bandwidth=nw_auto_bw(x)),
}

tested = [w for w in order if w in S and len(S[w]["pre"]) >= 60]
print("tested wallets:", len(tested), " Holm family size m =", len(order))
other_ok = {w: all("Holm" in rs for rs in rows[w]["stage_a1_reasons"]) for w in order}
base_pass = set(a1["evidence"]["derived"]["a1_pass"])

out = {}
for rname, f in RULES.items():
    p = {}
    for w in tested:
        x = S[w]["pre"]
        kw = f(x)
        if kw.get("lags", 1) is None:
            p[w] = hac_t_test(x).p_value
        else:
            p[w] = float(hac_t_rows(x[None, :], **kw)[1][0])
    pv = [p.get(w, 1.0) for w in order]
    holm = dict(zip(order, holm_bonferroni(pv)))
    passed = {w for w in order if other_ok[w] and w in p and holm[w] <= 0.05}
    out[rname] = (p, holm, passed)
    if "repo" in rname:
        dif = max(abs(p[w] - rows[w]["metrics"]["p_pre"]) / max(rows[w]["metrics"]["p_pre"], 1e-300) for w in tested)
        print(f"repo rule reproduces recorded p_pre: max rel diff {dif:.1e}; A1 pass set identical: {passed == base_pass}")
    lost = sorted(S[w]["name"] for w in base_pass - passed)
    new = sorted(S[w]["name"] for w in passed - base_pass)
    print(f"{rname:30s} A1 passes {len(passed):2d}  lost {lost}  new {new}")

names = {S[w]["name"]: w for w in S}
print()
print("per-wallet p_pre / Holm under each rule (A1 passers + Holm-only failures):")
focus = sorted(base_pass | {w for w in order if other_ok[w] and w in tested}, key=lambda w: rows[w]["metrics"]["p_pre"])
print("%-20s %4s" % ("wallet", "n") + "".join("%27s" % r.split(" ")[0] for r in RULES))
for w in focus:
    line = "%-20s %4d" % (str(S[w]["name"])[:20], len(S[w]["pre"]))
    for rname in RULES:
        p, holm, passed = out[rname]
        line += "%27s" % f"{p[w]:.2e}/{holm[w]:.3f}{'*' if w in passed else ' '}"
    print(line)
print("(* = passes A1 under that rule)")
for nm in ["GoodFallen", "LonnieHawkinss"]:
    x = S[names[nm]]["pre"]
    e = x - x.mean()
    ac = [float(e[k:] @ e[:-k] / (e @ e)) for k in range(1, 13)]
    print(nm, "n=", len(x), "acf1..12:", np.round(ac, 2).tolist(),
          "Schwert lags", int(12 * (len(x) / 100) ** 0.25), "Andrews S_T %.2f NWauto S_T %.2f" % (andrews_ar1_bw(x), nw_auto_bw(x)))
pickle.dump({k: (v[0], v[1], sorted(v[2])) for k, v in out.items()}, open(f"{HERE}/lag_rules.pkl", "wb"))
