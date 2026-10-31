"""H3 maker match: project-style directional-maker match test (score = corrected-strike fair of the side, using spot
L s old, minus the passive fill price; lag scan on FIT; TEST AUC vs spot-clock-shift null, 200 draws), plus the same
test with score = 2-s signed spot return (spot-reactive quoting), for passive BUY fills."""
import json, numpy as np, pandas as pd
from scipy import stats
from common import *
from polyrea.analysis.updown import SpotIndex, auc
from polyrea.pit import TimeSeries
d, G = load()
ev = np.concatenate([d["fit"]["spot_ev"], d["test"]["spot_ev"]]); vals = np.concatenate([d["fit"]["spot_vals"], d["test"]["spot_vals"]])
o = np.argsort(ev, kind="stable")
SPOT = SpotIndex(TimeSeries.build("spot", zip(ev[o].tolist(), vals[o].tolist()), availability_lag=1))
SCALE = 1.2
def fair(spot, start, end, t_dec, scale=1.0, twap=60):
    start, end, t_dec = (np.asarray(x, dtype=np.int64) for x in (start, end, t_dec))
    s0 = spot.mean_between(start - twap, start, start)        # Kraken TWAP over [start-60, start), known at start
    st = spot.price_at(t_dec); sig = spot.sigma_at(t_dec) * scale
    tw = end - twap; before = t_dec < tw
    var_before = (tw - t_dec).clip(min=0) + twap / 3.0
    r = (end - t_dec).clip(min=0).astype(float)
    a_known = spot.mean_between(tw, t_dec, t_dec); a_known = np.where(np.isnan(a_known), st, a_known)
    mean_in = ((twap - r) * a_known + r * st) / twap
    sd_in = (r / twap) * np.sqrt(np.maximum(r, 1e-9) / 3.0)
    mean = np.where(before, st, mean_in); sdu = np.where(before, np.sqrt(var_before), sd_in)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (mean - s0) / (st * sig * sdu)
    p = stats.norm.cdf(z)
    p = np.where(t_dec < start, 0.5, p)
    p = np.where(t_dec >= end, np.where(mean >= s0, 1.0, 0.0), p)
    return p


def mframe(per):
    P = d[per]["maker_prints"]; return P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True)
Pf, Pt = mframe("fit"), mframe("test")
def s_fair(P, L, sh=0):
    fu = fair(SPOT, P.start_ts.to_numpy() + sh, P.end_ts.to_numpy() + sh, P.ts.to_numpy() - L + sh, SCALE)
    return np.where(P.is_up.to_numpy(), fu, 1 - fu) - P.price.to_numpy()
def s_ret(P, L, sh=0, k=2):
    t = P.ts.to_numpy() - L + sh
    r = np.log(SPOT.price_at(t) / SPOT.price_at(t - k))
    return np.where(P.is_up.to_numpy(), r, -r)
out = {}
for nm, fn in (("fair_minus_price", s_fair), ("spot_return_2s", s_ret)):
    out[nm] = {}
    for n, w in W.items():
        yf = (Pf.wallet == w).to_numpy().astype(int); yt = (Pt.wallet == w).to_numpy().astype(int)
        scan = {L: auc(fn(Pf, L), yf) for L in (0, 1, 2, 3, 5)}
        L = max(scan, key=scan.get); a = auc(fn(Pt, L), yt)
        rng = np.random.default_rng(11); null = []
        for _ in range(200):
            sh = int(rng.integers(3600, 6 * 3600)) * int(rng.choice([-1, 1]))
            null.append(auc(fn(Pt, L, sh), yt))
        null = np.array([x for x in null if np.isfinite(x)])
        out[nm][n] = {"lag_scan_fit": scan, "L": L, "test_auc": a, "null_mean": float(null.mean()), "null_max": float(null.max()), "perm_p": float((1 + (null >= a).sum()) / (1 + len(null)))}
        print(nm, n, json.dumps(out[nm][n], default=float), flush=True)
json.dump(out, open("h3_maker_match.json", "w"), indent=1, default=float)
