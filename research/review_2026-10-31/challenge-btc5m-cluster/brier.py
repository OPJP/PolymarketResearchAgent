"""Brier of the market (last implied Up price, tape up to t-2 s) vs public spot models at fixed times in each window.
Models: K = recorded Kraken model (strike = Kraken at start); C = strike from Chainlink priceToBeat mapped to Kraken
via the basis observed on the PREVIOUS window (finalPrice_prev - Kraken 60 s TWAP of prev window, known at start);
sigma variants scaled by s fitted on FIT."""
import sys, pickle, json
import numpy as np, pandas as pd
from scipy import stats
from common import *
from polyrea.analysis.updown import fair_up_vectorized

d, G = load()
ptb = pickle.load(open("ptb.pkl", "rb"))
REL = np.array([10, 30, 60, 90, 120, 150, 180, 210, 240, 255, 270, 285])
def rows(per, lat=2):
    g = G[per]; out = []
    for cid, w in g.wins.items():
        if w.up_payout is None: continue
        t = w.start_ts + REL
        base, up_last, _, _ = g.g[cid]
        mkt = up_last[np.clip(t - lat - base, 0, len(up_last) - 1)]
        fk = fair_up_vectorized(g.spot, np.full(len(t), w.start_ts), np.full(len(t), w.end_ts), t - lat, 60)
        # chainlink-anchored strike: previous window's basis
        prev = g.by_start.get(w.start_ts - 300)
        strike_k = np.nan
        if prev is not None and ptb.get(prev, {}).get("final") and ptb.get(cid, {}).get("ptb"):
            kt = g.spot.mean_between(np.array([w.start_ts - 60]), np.array([w.start_ts]), np.array([w.start_ts]))[0]
            basis = ptb[prev]["final"] - kt
            strike_k = ptb[cid]["ptb"] - basis
        st = g.spot.price_at(t - lat); sig = g.spot.sigma_at(t - lat)
        for i, r in enumerate(REL):
            out.append({"cid": cid, "rel": int(r), "y": w.up_payout, "mkt": mkt[i], "fk": fk[i], "st": st[i], "sig": sig[i], "s0k": g.spot.price_at(np.array([w.start_ts]))[0], "strike_c": strike_k, "end": w.end_ts, "t": int(t[i] - lat), "start": w.start_ts})
    return pd.DataFrame(out)

def model(df, g, strike_col, scale):
    # same math as fair_up_vectorized but with a chosen strike and sigma scale
    tw = df.end - 60; tdec = df.t
    before = tdec < tw
    var_before = (tw - tdec).clip(lower=0) + 20.0
    r = (df.end - tdec).clip(lower=0).astype(float)
    a_known = np.array([g.spot.mean_between(np.array([a]), np.array([b]), np.array([b]))[0] if b > a else np.nan for a, b in zip(tw, tdec)])
    a_known = np.where(np.isnan(a_known), df.st, a_known)
    mean_in = ((60 - r) * a_known + r * df.st) / 60
    sd_in = (r / 60) * np.sqrt(np.maximum(r, 1e-9) / 3.0)
    mean = np.where(before, df.st, mean_in); sdu = np.where(before, np.sqrt(var_before), sd_in)
    z = (mean - df[strike_col]) / (df.st * df.sig * scale * sdu)
    return stats.norm.cdf(z)

res = {}
F, T = rows("fit"), rows("test")
for nm, D, g in (("fit", F, G["fit"]), ("test", T, G["test"])):
    D["fk_chk"] = model(D, g, "s0k", 1.0)
    D["fc1"] = model(D, g, "strike_c", 1.0)
    for s in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2):
        D[f"fk_s{s}"] = model(D, g, "s0k", s); D[f"fc_s{s}"] = model(D, g, "strike_c", s)
ok = lambda D: D[["mkt", "fk", "fc1"]].notna().all(axis=1) & D.strike_c.notna()
brier = lambda p, y: float(np.mean((p - y) ** 2))
# fit sigma scale on FIT for each strike type
Fo = F[ok(F)]; To = T[ok(T)]
best_k = min((0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2), key=lambda s: brier(Fo[f"fk_s{s}"], Fo.y))
best_c = min((0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2), key=lambda s: brier(Fo[f"fc_s{s}"], Fo.y))
res["sigma_scale_fit"] = {"kraken_strike": best_k, "chainlink_strike": best_c}
for nm, D in (("fit", Fo), ("test", To)):
    res[nm] = {"n": len(D), "market": brier(D.mkt, D.y), "kraken_model_recorded": brier(D.fk, D.y), "check_reimpl": brier(D.fk_chk, D.y),
               "kraken_model_sigma_fit": brier(D[f"fk_s{best_k}"], D.y), "chainlink_strike_model": brier(D.fc1, D.y), "chainlink_strike_sigma_fit": brier(D[f"fc_s{best_c}"], D.y),
               "by_rel": {int(r): {"market": brier(g.mkt, g.y), "kraken": brier(g.fk, g.y), "chainlink_fit": brier(g[f"fc_s{best_c}"], g.y)} for r, g in D.groupby("rel")}}
    res[nm]["abs_strike_diff_usd_median"] = float(np.median(np.abs(D.strike_c - D.s0k)))
print(json.dumps(res, indent=1, default=float))
json.dump(res, open("brier.json", "w"), indent=1, default=float)
pd.to_pickle({"fit": F, "test": T}, "brier_rows.pkl")
