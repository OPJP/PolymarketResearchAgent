"""Repeat the synthetic check over seeds: (a) spot-blind H0 wallets that prefer expensive
prints -> false positives; (b) spot-USING H1 wallets with a cheap-price preference -> missed."""
import pickle
from pathlib import Path
import numpy as np
from polyrea.analysis.updown import SpotIndex, score_prints, match_test

D = pickle.load(open(Path(__file__).parent / "data" / "btc5m.pkl", "rb"))
spot = SpotIndex(D["spot_ts"])
fitp, testp = D["fit"]["prints"], D["test"]["prints"]
pr_f, pr_t = fitp["price"].to_numpy(), testp["price"].to_numpy()
print("share of TEST prices on a 1-cent grid:", np.mean(np.abs(pr_t * 100 - np.round(pr_t * 100)) < 1e-6).round(4))
s2f = np.nan_to_num(score_prints(fitp, spot, 2), nan=-1); s2t = np.nan_to_num(score_prints(testp, spot, 2), nan=-1)

def go(label, pf, pt, seeds=(1, 2, 3, 4, 5), n_perm=100):
    res = []
    for sd in seeds:
        rng = np.random.default_rng(sd)
        f = fitp.assign(wallet=np.where(rng.random(len(fitp)) < pf, "0xsyn", fitp["wallet"]))
        t = testp.assign(wallet=np.where(rng.random(len(testp)) < pt, "0xsyn", testp["wallet"]))
        mt = match_test(f, t, "0xsyn", spot, n_perm=n_perm, seed=sd)
        res.append((round(mt["test"]["auc"], 3), round(mt["test"]["auc_null_mean"], 3), round(mt["test"]["auc_perm_p"], 3)))
    print(f"{label:45s} (AUC, null mean, perm p) per seed: {res}")

go("H0 spot-blind, prefers expensive 0.06*p^3", 0.06 * pr_f**3, 0.06 * pr_t**3)
go("H0 spot-blind, prefers expensive 0.06*p^1", 0.06 * pr_f, 0.06 * pr_t)
for b in (3.0, 6.0):
    go(f"H1 spot-using: (1-p)^3 * exp({b}*edge@2s)", 0.03 * (1 - pr_f) ** 3 * np.exp(b * s2f), 0.03 * (1 - pr_t) ** 3 * np.exp(b * s2t))
