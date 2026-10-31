import pickle, sys, time
import numpy as np
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.analysis.updown import SpotIndex, match_test, score_prints, auc, fair_up_vectorized
D = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/verify-lookahead-0/"
d = pickle.load(open(D + "data.pkl", "rb"))
spot = SpotIndex(d["spot_ts"])
fitp, tp = d["fit_prints"], d["test_prints"]
W = "0xc53375ff94e96100f2b30a4b5775db35218d69a9"
t0 = time.time()
mt = match_test(fitp, tp, W, spot, n_perm=200, seed=7)
t = mt["test"]
print("match_test reproduced: lat", mt["chosen_latency_s"], "theta", round(mt["theta"], 4), "AUC", round(t["auc"], 4),
      "null mean", round(t["auc_null_mean"], 4), "p95", round(t["auc_null_p95"], 4), "perm p", round(t["auc_perm_p"], 4),
      "MW p", t["mannwhitney_p"], f"({time.time()-t0:.0f}s)")

lat = mt["chosen_latency_s"]; theta = mt["theta"]
y = (tp["wallet"] == W).to_numpy().astype(int)
s_real = score_prints(tp, spot, lat)
print("real: finite share", np.isfinite(s_real).mean())
# regenerate the exact shifts used by match_test (same rng sequence)
rng = np.random.default_rng(7)
shifts = [int(rng.integers(3600, 6 * 3600)) * int(rng.choice([-1, 1])) for _ in range(200)]
fin, aucs, sds, above, stale_s0, stale_st, aucneg = [], [], [], [], [], [], []
price = tp["price"].to_numpy()
ts = tp["ts"].to_numpy(); st_ = tp["start_ts"].to_numpy()
ev = spot.ev; av = spot.av
def staleness(tq):
    i = spot._idx_available(tq)
    return np.where(i >= 0, tq - av[np.clip(i, 0, None)], np.inf)
for sh in shifts:
    sp = score_prints(tp, spot, lat, shift=sh)
    ok = np.isfinite(sp)
    fin.append(ok.mean())
    aucs.append(auc(sp, y))
    sds.append(np.nanstd(sp))
    above.append((sp[ok] > theta).mean())
    inwin = ok & (ts - lat >= st_)  # decision in window -> S0 used
    s0_stale = staleness(st_ + sh)[inwin] > 5
    st_stale = staleness(ts - lat + sh)[inwin] > 5
    stale_s0.append(s0_stale.mean() if inwin.any() else np.nan)
    stale_st.append(st_stale.mean() if inwin.any() else np.nan)
    aucneg.append(auc(-price[ok], y[ok]))
fin = np.array(fin); aucs = np.array(aucs); stale_s0 = np.array(stale_s0); aucneg = np.array(aucneg)
print("null finite share: median %.3f min %.3f max %.3f" % (np.median(fin), fin.min(), fin.max()))
inwin_real = np.isfinite(s_real) & (ts - lat >= st_)
print("real in-window S0 stale>5s share:", (staleness(st_)[inwin_real] > 5).mean(), " St stale>5s:", (staleness(ts-lat)[inwin_real] > 5).mean())
print("null in-window S0 stale>5s: median %.3f max %.3f; St stale>5s median %.3f max %.3f" % (np.nanmedian(stale_s0), np.nanmax(stale_s0), np.nanmedian(stale_st), np.nanmax(stale_st)))
print("score sd: real %.3f, null median %.3f" % (np.nanstd(s_real), np.median(sds)))
print("share > theta: real %.3f, null median %.3f" % ((s_real[np.isfinite(s_real)] > theta).mean(), np.median(above)))
print("AUC(-price) all prints: %.4f" % auc(-price, y))
print("null AUC mean %.4f; AUC(-price) on same subset mean %.4f; corr(null AUC, AUC(-price) subset) %.3f" % (np.nanmean(aucs), np.nanmean(aucneg), np.corrcoef(aucs, aucneg)[0, 1]))
print("corr(null AUC, finite share) %.3f" % np.corrcoef(aucs, fin)[0, 1])
# null AUC when shift lands mostly in-coverage
hi = fin > 0.7
print("shifts with finite share>0.7:", hi.sum(), "their null AUC mean", np.nanmean(aucs[hi]) if hi.any() else None)
# real-score correlation with price
ok = np.isfinite(s_real)
print("corr(real score, price) %.3f; corr(null score, price) median below" % np.corrcoef(s_real[ok], price[ok])[0,1])
cs = []
for sh in shifts[:30]:
    sp = score_prints(tp, spot, lat, shift=sh); o = np.isfinite(sp)
    cs.append(np.corrcoef(sp[o], price[o])[0,1])
print("corr(null score, price) median over 30 shifts %.3f" % np.median(cs))
np.save(D + "shifts.npy", np.array(shifts))
