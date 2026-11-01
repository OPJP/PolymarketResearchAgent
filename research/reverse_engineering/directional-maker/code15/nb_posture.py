"""iteration 15, T1b (post hoc after T1, reported as such): the relative-value posture on the non-BTC families.
Rule: buy s iff F_s > p_s, F = Phi(ln(S/K) / (k sigma300 sqrt(tau))) on Binance spot (S at T-3, K as in nb_side), sigma300
= the symbol's 300-s realised 1-s log-return sd; p_s = the market price of s proxied by the fill price (the cluster's own
quote; a public version needs the last clean print). Grid k 0.5-2.0 reported per fold; choice on VALIDATE only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE))
from nb_side import Spot, C, RES
a = pd.read_parquet(C / "it15_nb_side.parquet")
a = a[a.rule_ok.notna()].reset_index(drop=True)
sp = Spot(); sig = np.full(len(a), np.nan)
for sym, g in a.groupby("sym"):
    t = g.timestamp.to_numpy(np.int64) - 3
    grid = t[:, None] + np.arange(-300, 1)[None, :]
    v = np.log(sp.close_at(sym, grid.ravel()).reshape(grid.shape))
    d = np.diff(v, axis=1)
    with np.errstate(invalid="ignore"):
        sig[g.index] = np.nanstd(d, axis=1)
a["sig"] = sig
tau = np.maximum(a.st + a.L - a.timestamp, 1).to_numpy(float)
z = np.log(a.S / a.K).to_numpy(float)
ps = a.price.to_numpy(float)
up = a.up.to_numpy(float)
fg = a.fam.str.replace(r"^(eth|sol|xrp|bnb|doge)-(5m|15m)$", r"alt-\2", regex=True).str.replace(r"^\w+-4h$", "4h", regex=True).str.replace(r"^\w+-hourly$", "hourly", regex=True).str.replace(r"^\w+-daily$", "daily", regex=True)
fd = np.where(a.fold.str.startswith("STUDY"), "STUDY", a.fold)
out = {}
for k in (0.5, 0.7, 1.0, 1.4, 2.0, 3.0):
    Fu = norm.cdf(z / (k * a.sig.to_numpy(float) * np.sqrt(tau)))
    Fs = np.where(up == 1, Fu, 1 - Fu)
    ok = (Fs > ps).astype(float); ok[~np.isfinite(Fs)] = np.nan
    d = pd.DataFrame({"fg": np.where(a.btc_core, a.fam, fg), "fold": fd, "ph": a.phase, "ok": ok, "itm": a.rule_ok, "mk": a.mktfav_ok})
    g = d.groupby(["fg", "fold"]).agg(n=("ok", "size"), post=("ok", "mean"), itm=("itm", "mean"), mkt=("mk", "mean")).round(3)
    out[f"k{k}"] = g.reset_index().to_dict("records")
    if k in (1.0, 1.4):
        print("k", k); print(g.unstack("fold")["post"].to_string())
    gg = d[~a.btc_core.to_numpy()].groupby("fold").agg(n=("ok", "size"), post=("ok", "mean"), itm=("itm", "mean"), mkt=("mk", "mean")).round(3)
    print("k", k, "non-BTC pooled:", gg.to_dict("index"))
(RES / "iter15_nb_posture.json").write_text(json.dumps(out, indent=1, default=float))
