"""Field null: for each of the 334 tested wallets, impose mean zero on its real
pre-selection series and resample it with a stationary bootstrap (mean block 10
days, keeping its own marginal distribution and short-range dependence). Rate at
which the repo HAC test rejects at the Holm first-step level 0.05/500, and the
same for the full A1 significance gate (HAC + bootstrap p<.01 + DSR>.95), with DSR
on [null pre series + the wallet's actual 30-day ranking window]."""
import pickle, sys
import numpy as np
HERE = __file__.rsplit("/", 1)[0]
sys.path.insert(0, "/home/user/PolymarketResearchAgent"); sys.path.insert(0, HERE)
from polyrea.stats.significance import stationary_bootstrap_pvalue, deflated_sharpe_ratio  # noqa
from hac_vec import hac_t_rows  # noqa

D = pickle.load(open(f"{HERE}/series.pkl", "rb")); S = D["series"]
tested = [w for w in D["order"] if w in S and len(S[w]["pre"]) >= 60]
rng = np.random.default_rng(2024)
B = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
BLOCK = 10.0
ALPHA = 0.05 / 500

acf1 = []; skew = []
rate_hac = []; rate_full = []; rate_pre = []; flagged_total = 0
for w in tested:
    x = S[w]["pre"]; n = len(x); c = x - x.mean()
    e = c; acf1.append(float(e[1:] @ e[:-1] / (e @ e)) if e @ e > 0 else 0.0)
    sd = c.std(); skew.append(float((c ** 3).mean() / sd ** 3) if sd > 0 else 0.0)
    idx = np.empty((B, n), np.int64); idx[:, 0] = rng.integers(0, n, B)
    st = rng.random((B, n)) < 1 / BLOCK; jp = rng.integers(0, n, (B, n))
    for j in range(1, n):
        idx[:, j] = np.where(st[:, j], jp[:, j], (idx[:, j - 1] + 1) % n)
    X = c[idx]
    _, p = hac_t_rows(X)
    hit = np.flatnonzero(p < ALPHA)
    flagged_total += len(hit)
    rate_hac.append(len(hit) / B)
    win = S[w]["full"][-30:]
    full_ok = pre_ok = 0
    for i in hit[:50]:  # cap per wallet
        bp = stationary_bootstrap_pvalue(X[i], n_boot=4000).p_value
        if bp >= 0.01:
            continue
        d_pre = deflated_sharpe_ratio(X[i], n_trials=500)
        d_full = deflated_sharpe_ratio(np.concatenate([X[i], win]), n_trials=500)
        pre_ok += not (d_pre < 0.95); full_ok += not (d_full < 0.95)
    m = min(len(hit), 50)
    rate_pre.append(rate_hac[-1] * (pre_ok / m if m else 0.0))
    rate_full.append(rate_hac[-1] * (full_ok / m if m else 0.0))

rh, rp, rf = map(np.array, (rate_hac, rate_pre, rate_full))
acf1 = np.array(acf1); skew = np.array(skew)
print(f"wallets={len(tested)} B={B} block={BLOCK} flagged={flagged_total}")
print(f"real pre-series lag-1 autocorr: median {np.median(acf1):.2f}, IQR [{np.percentile(acf1,25):.2f},{np.percentile(acf1,75):.2f}], share>0.3 {np.mean(acf1>0.3):.2f}, share>0.6 {np.mean(acf1>0.6):.2f}")
print(f"real pre-series skewness: median {np.median(skew):.2f}, share < -2 {np.mean(skew<-2):.2f}, share > 2 {np.mean(skew>2):.2f}")
print(f"per-wallet HAC size at 1e-4: median {np.median(rh):.1e}, mean {rh.mean():.2e} ({rh.mean()/ALPHA:.1f}x), max {rh.max():.1e}")
print(f"expected # false rejections over 334 nulls / FWER: HAC-only {rh.sum():.3f} / {1-np.prod(1-rh):.1%};"
      f" full gate DSR(pre only) {rp.sum():.3f} / {1-np.prod(1-rp):.1%}; full gate DSR(pre+actual window) {rf.sum():.3f} / {1-np.prod(1-rf):.1%}")
