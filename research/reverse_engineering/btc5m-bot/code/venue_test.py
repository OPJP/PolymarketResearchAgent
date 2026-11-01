"""Iteration 3: do other perpetual venues (OKX swap, Bybit perp) explain the bot's side when Binance (futures and spot)
is flat? VALIDATE one-sided seconds (val_side_it3.parquet) inside each venue's archive coverage. PIT windows end at
(s-1)*1000 ms; [s-1, s) and later are non-PIT diagnostics. Also: lead of each venue over Binance futures (1-s returns)."""
import os, sys, glob, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600


def pxfun(df):
    df = df.sort_values("T", kind="stable"); T = df["T"].to_numpy(np.int64); lp = np.log(df.p.to_numpy())
    return (lambda t: np.where(np.searchsorted(T, t, side="left") > 0, lp[np.clip(np.searchsorted(T, t, side="left") - 1, 0, None)], np.nan)), T.min(), T.max()


S = pd.read_parquet(f"{C}/val_side_it3.parquet"); S["s"] = (S.start_ts + S.rel).astype(np.int64)
bot = np.where(S.truth_up == 1, 1.0, -1.0)
fut = pd.concat([pd.read_parquet(f"{C}/fut/{d}.parquet") for d in range(V0, V1, 86400)], ignore_index=True)
fpx, _, _ = pxfun(fut)
s_ms = S.s.to_numpy(np.int64) * 1000
bf_past = (fpx(s_ms - 1000) - fpx(s_ms - 4000)) * 1e4
flat = (np.abs(bf_past) < 0.3) & (np.abs(S.r3.to_numpy()) < 0.01)
res = {}
for venue in ("okx", "bybit"):
    fs = sorted(glob.glob(f"{C}/venues/{venue}/*.parquet"))
    if not fs:
        continue
    vdf = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    vpx, t0, t1 = pxfun(vdf)
    cov = (s_ms - 20000 >= t0) & (s_ms + 20000 <= t1)
    r = {"n_seconds_covered": int(cov.sum()), "trades": int(len(vdf))}
    for nm, a, b in [("[s-4,s-1)", -4000, -1000), ("[s-3,s-2)", -3000, -2000), ("[s-2,s-1)", -2000, -1000), ("[s-1,s)_nonPIT", -1000, 0), ("[s,s+2)_future", 0, 2000)]:
        mv = (vpx(s_ms + b) - vpx(s_ms + a)) * 1e4
        for sub, mask in [("all", cov), ("binance_flat", cov & flat)]:
            k = mask & np.isfinite(mv) & (np.abs(mv) > 1e-9)
            r[f"{sub}:{nm}"] = (round(float((np.sign(mv[k]) == bot[k]).mean()), 4), round(float(k.sum() / max(mask.sum(), 1)), 3), int(mask.sum()))
    # venue move vs Binance move over the PIT 3 s in the flat subset: how often does the venue move when Binance is flat?
    mv3 = (vpx(s_ms - 1000) - vpx(s_ms - 4000)) * 1e4
    k = cov & flat
    r["binance_flat:venue_|3s|>=0.5bp_share"] = round(float((np.abs(mv3[k]) >= 0.5).mean()), 4)
    kk = k & (np.abs(mv3) >= 0.5)
    r["binance_flat:venue_|3s|>=0.5bp_agree"] = round(float((np.sign(mv3[kk]) == bot[kk]).mean()), 4) if kk.any() else None
    # lead-lag of 1-s returns: venue second t vs Binance futures second t+k, on a common grid inside coverage
    g = np.arange(max(t0, V0 * 1000) // 1000 + 30, min(t1, V1 * 1000) // 1000 - 30, dtype=np.int64)
    vr = np.diff(vpx(g * 1000)); br = np.diff(fpx(g * 1000))
    ok = np.isfinite(vr) & np.isfinite(br)
    r["corr_venue_t_binfut_t+k"] = {k: round(float(np.corrcoef(vr[ok][max(0, -k):len(vr[ok]) - max(0, k)], br[ok][max(0, k):len(br[ok]) - max(0, -k)])[0, 1]), 4) for k in (-2, -1, 0, 1, 2)}
    res[venue] = r
json.dump(res, open(f"{R}/results_venues_iter3.json", "w"), indent=1)
for v, r in res.items():
    print(v); [print("  ", k, x) for k, x in r.items()]
