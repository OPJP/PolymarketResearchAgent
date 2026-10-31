"""Issue: the spot-clock-shift permutation null in match_test does not keep marginals.

(a) Spot is only loaded for the 24 sampled 2-hour blocks (+30 min lookback), so a
    shift of 1-6 h moves most decision times into gaps: sigma_at -> NaN, the print's
    score is NaN and silently dropped. Each null AUC is computed on a different,
    small subset of prints.
(b) Even where spot exists, the shifted fair value is unrelated to the market price,
    so score' = fair' - price carries the raw price signal (-price) that the real
    score (fair - price, fair tracks price) mostly cancels. The null AUC therefore
    is centred on AUC(-price), not 0.5.
"""
import pickle, sys
from pathlib import Path
import numpy as np
from polyrea.analysis.updown import SpotIndex, score_prints, auc, match_test, decision_metrics

D = pickle.load(open(Path(__file__).parent / "data" / "btc5m.pkl", "rb"))
spot = SpotIndex(D["spot_ts"])
fitp, testp = D["fit"]["prints"], D["test"]["prints"]
W = sys.argv[1] if len(sys.argv) > 1 else "0xc53375ff94e96100f2b30a4b5775db35218d69a9"

mt = match_test(fitp, testp, W, spot, n_perm=200, seed=7)
print("reproduced match_test:", "lat", mt["chosen_latency_s"], "theta", mt["theta"], "test AUC", round(mt["test"]["auc"], 4),
      "null mean", round(mt["test"]["auc_null_mean"], 4), "p95", round(mt["test"]["auc_null_p95"], 4), "perm p", round(mt["test"]["auc_perm_p"], 4),
      "MW p", mt["test"]["mannwhitney_p"])
lat, theta = mt["chosen_latency_s"], mt["theta"]
y = (testp["wallet"] == W).to_numpy().astype(int)
s_real = score_prints(testp, spot, lat)
print(f"real scores finite: {np.isfinite(s_real).mean():.3f} of {len(s_real)} prints; real score sd {np.nanstd(s_real):.3f}; share > theta {np.mean(s_real[np.isfinite(s_real)] > theta):.4f}")
price = testp["price"].to_numpy()
print(f"AUC of (-price) alone for this wallet on TEST: {auc(-price, y):.4f}")

# replicate the null's shifts exactly (same RNG sequence as match_test)
rng = np.random.default_rng(7)
fin, aucs, aucs_negprice_same_subset, sds, above = [], [], [], [], []
for _ in range(200):
    sh = int(rng.integers(3600, 6 * 3600)) * int(rng.choice([-1, 1]))
    sp = score_prints(testp, spot, lat, shift=sh)
    ok = np.isfinite(sp)
    fin.append(ok.mean()); aucs.append(auc(sp, y)); aucs_negprice_same_subset.append(auc(-price[ok], y[ok]))
    sds.append(np.std(sp[ok])); above.append(np.mean(sp[ok] > theta))
fin, aucs, ap = np.array(fin), np.array(aucs), np.array(aucs_negprice_same_subset)
print(f"null: share of prints with a finite shifted score: median {np.median(fin):.3f}, min {fin.min():.3f}, max {fin.max():.3f}; shifts with <25% finite: {(fin<0.25).sum()}/200")
print(f"null: mean AUC {np.nanmean(aucs):.4f}; mean AUC(-price) on the same finite subsets {np.nanmean(ap):.4f}; corr(null AUC, AUC(-price) subset) {np.corrcoef(aucs[np.isfinite(aucs)], ap[np.isfinite(aucs)])[0,1]:.3f}")
print(f"null: score sd median {np.median(sds):.3f} (real {np.nanstd(s_real):.3f}); share > theta median {np.median(above):.4f} (real {np.mean(s_real[np.isfinite(s_real)] > theta):.4f})")
