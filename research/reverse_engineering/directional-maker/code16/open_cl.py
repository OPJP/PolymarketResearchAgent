"""iteration 16, X182 = information panel I15-2 part (a): the alt 5m/15m opening fills (< 20 s; ETH, SOL, XRP) scored with
the settlement-grade per-symbol Chainlink value at T - 2 (crypto-price endpoint, fetched by code16/fetch_alt_cl.py)
against the true strike (Gamma priceToBeat = mean CL[st - 61, st - 2]), vs the Binance stand-in (S(T - 3) against the
Binance TWAP-60 stand-in); in the money and the public posture (k 0.7 x the symbol's Binance sigma300, against the last
clean taker print stamped <= T - 2). Per fold, on the subset where the two references disagree, and per VALIDATE half.
    python open_cl.py"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code15"))
from nb_side import Spot, C  # noqa: E402

SYM = {"ETHUSDT": "ETH", "SOLUSDT": "SOL", "XRPUSDT": "XRP"}
cl = pd.read_parquet(C / "cl" / "alt_open.parquet")
cl = cl[cl.open.notna()]
clv = {(s, int(t)): float(v) for s, t, v in zip(cl.sym, cl.tau, cl.open)}
a = pd.concat([pd.read_parquet(C / "it15_nb_public_lot.parquet"), pd.read_parquet(C / "it15_nb_public_build.parquet")],
              ignore_index=True)
a = a[a.fam.str.match(r"^(eth|sol|xrp)-(5m|15m)$") & (a.timestamp - a.st < 20) & a.sym.isin(list(SYM))].reset_index(drop=True)
a["fold2"] = np.where(a.fold.str.startswith("STUDY"), "STUDY", np.where(a.fold == "VALIDATE", "VALIDATE", "BUILD"))
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402
raw = fetch_windows(sorted(set(a.slug)))
Kt = {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None:
            Kt[m["slug"]] = float(v)
a["Kt"] = a.slug.map(Kt)
a["CL"] = [clv.get((SYM[s], int(t) - 2), np.nan) for s, t in zip(a.sym, a.timestamp)]
out = {"fills": int(len(a)), "with_cl": int(a.CL.notna().sum())}
# verification: priceToBeat vs mean CL[st-61, st-2] on the verification windows
ver = []
for (s, st), g in a.groupby(["sym", "st"]):
    vals = [clv.get((SYM[s], t)) for t in range(int(st) - 61, int(st) - 1)]
    if sum(v is not None for v in vals) >= 55:
        k = Kt.get(g.slug.iloc[0])
        ver.append((s, int(st), float(np.mean([v for v in vals if v is not None])), k))
out["verification"] = [{"sym": s, "st": st, "mean_cl": round(m_, 6), "priceToBeat": k, "diff": round(m_ - k, 6) if k else None} for s, st, m_, k in ver]
sp = Spot()
sig = np.full(len(a), np.nan)
for sym, g in a.groupby("sym"):
    t = g.timestamp.to_numpy(np.int64) - 3
    grid = t[:, None] + np.arange(-300, 1)[None, :]
    v = np.log(sp.close_at(sym, grid.ravel()).reshape(grid.shape))
    with np.errstate(invalid="ignore"):
        sig[g.index] = np.nanstd(np.diff(v, axis=1), axis=1)
tau = np.maximum(a.st + a.L - a.timestamp, 1).to_numpy(float)
up = a.up.to_numpy(float)
y = up == 1
ps = a.p_pub.to_numpy(float)
pred = {}
for nm, S, K in (("binance_standin", a.S.to_numpy(float), a.K.to_numpy(float)), ("chainlink_true", a.CL.to_numpy(float), a.Kt.to_numpy(float))):
    z = np.log(S / K)
    Fu = norm.cdf(z / (0.7 * sig * np.sqrt(tau)))
    Fs = np.where(up == 1, Fu, 1 - Fu)
    pred[f"post_{nm}"] = np.where(np.isfinite(Fs) & np.isfinite(ps), (Fs > ps).astype(float), np.nan)
    pred[f"itm_{nm}"] = np.where(np.isfinite(z) & (z != 0), ((z > 0) == y).astype(float), np.nan)
ok = np.isfinite(a.CL.to_numpy(float)) & np.isfinite(a.Kt.to_numpy(float)) & np.isfinite(pred["post_binance_standin"])
zb = np.log(a.S / a.K).to_numpy(float)
zc = np.log(a.CL / a.Kt).to_numpy(float)
dis = ok & ((zb > 0) != (zc > 0))
for f_ in ("BUILD", "STUDY", "VALIDATE"):
    m = ok & (a.fold2 == f_).to_numpy()
    r = {"n": int(m.sum()), "disagree_n": int((m & dis).sum()), "disagree_share": round(float((m & dis).sum() / max(1, m.sum())), 3)}
    for k_, p in pred.items():
        mm = m & np.isfinite(p)
        r[k_] = round(float(p[mm].mean()), 3) if mm.sum() else None
        md = mm & dis
        r[k_ + "_on_disagree"] = round(float(p[md].mean()), 3) if md.sum() else None
    out[f_] = r
mv = ok & (a.fold2 == "VALIDATE").to_numpy()
if mv.sum():
    med = np.median(a.st[mv])
    for lab, mh in (("first", mv & (a.st < med).to_numpy()), ("second", mv & (a.st >= med).to_numpy())):
        out[f"VALIDATE_half_{lab}"] = {k_: (round(float(p[mh & np.isfinite(p)].mean()), 3) if (mh & np.isfinite(p)).sum() else None) for k_, p in pred.items()} | {"n": int(mh.sum())}
print(json.dumps(out, indent=1))
(HERE.parent / "results/iter16_open_cl.json").write_text(json.dumps(out, indent=1))
