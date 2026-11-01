"""iteration 16, T5 (information panel I15-2, the cheap part): the alt 5m/15m opening fills (< 20 s) scored with the
Binance reference S(T - 3) against the TRUE strike (Gamma priceToBeat, a listing-time field set at the window start)
instead of the Binance TWAP-60 stand-in, with the public posture (k 0.7 x sigma300 against the last clean taker print
stamped <= T - 2) and the in-the-money rule; per fold (BUILD sample days, STUDY, VALIDATE aggregate, after T0), on the
subset where the two strikes disagree on the in-the-money side, and by VALIDATE half (window start). Opening PnL per $
by agreement with true settlement from Gamma (development units only).
Pre-registered reading (09:07 UTC): the true-strike version beats the stand-in by >= 0.03 on every fold -> the opening
bid reads the published strike.
    python open_strike.py"""
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

a = pd.concat([pd.read_parquet(C / "it15_nb_public_lot.parquet"), pd.read_parquet(C / "it15_nb_public_build.parquet")],
              ignore_index=True)
a = a[a.fam.str.match(r"^(eth|sol|xrp|bnb|doge)-(5m|15m)$") & (a.timestamp - a.st < 20)].reset_index(drop=True)
a["fold2"] = np.where(a.fold.str.startswith("STUDY"), "STUDY", np.where(a.fold.str.startswith("BUILD") | a.fold.str.match(r"^\d"), "BUILD", a.fold))
print("opening alt fills", len(a), a.fold2.value_counts().to_dict(), flush=True)
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402
raw = fetch_windows(sorted(set(a.slug)))
Kt, win = {}, {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None:
            Kt[m["slug"]] = float(v)
    try:
        op = json.loads(m["outcomePrices"]) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices")
        outs = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else m.get("outcomes")
        if op and outs and m.get("closed"):
            win[m["slug"]] = outs[int(np.argmax([float(x) for x in op]))]
    except Exception:  # noqa: BLE001
        pass
a["Kt"] = a.slug.map(Kt)
print("with true strike", int(a.Kt.notna().sum()), flush=True)
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
y = up == 1  # the cluster bought Up
ps = a.p_pub.to_numpy(float)
res = {}
pred = {}
for nm, K in (("standin", a.K.to_numpy(float)), ("true", a.Kt.to_numpy(float))):
    z = np.log(a.S.to_numpy(float) / K)
    Fu = norm.cdf(z / (0.7 * sig * np.sqrt(tau)))
    Fs = np.where(up == 1, Fu, 1 - Fu)
    pred[f"post_{nm}"] = np.where(np.isfinite(Fs) & np.isfinite(ps), (Fs > ps), np.nan)  # correct = the bought outcome's fair > its price
    pred[f"itm_{nm}"] = np.where(np.isfinite(z) & (z != 0), ((z > 0) == y), np.nan)
ok_all = np.isfinite(a.Kt.to_numpy(float)) & np.isfinite(pred["post_standin"].astype(float))
dis = ok_all & ((np.log(a.S / a.K) > 0) != (np.log(a.S / a.Kt) > 0)).to_numpy()
a["won"] = [(win.get(s) == o) if s in win else np.nan for s, o in zip(a.slug, a.outcome)]
a["pnl"] = np.where(a.won.astype(float) == 1, a["size"] * (1 - a.price), -a["size"] * a.price)
for f_ in ("BUILD", "STUDY", "VALIDATE", "dev_after_T0"):
    m = ok_all & (a.fold2 == f_).to_numpy()
    r = {"n": int(m.sum()), "disagree_n": int((m & dis).sum())}
    for k_, p in pred.items():
        pp = p.astype(float)
        mm = m & np.isfinite(pp)
        r[k_] = round(float(pp[mm].mean()), 3) if mm.sum() else None
        md = mm & dis
        r[k_ + "_on_disagree"] = round(float(pp[md].mean()), 3) if md.sum() else None
    r["strike_diff_bp_median_abs"] = round(float(np.nanmedian(np.abs(a.K / a.Kt - 1)[m]) * 1e4), 2) if m.sum() else None
    # PnL by agreement with the true-strike posture (Gamma settlement)
    pt = pred["post_true"].astype(float)
    for lab, mm in (("agree_true", m & (pt == 1)), ("against_true", m & (pt == 0))):
        cst = (a["size"] * a.price)[mm & a.won.notna().to_numpy()].sum()
        r[f"pnl_per_usd_{lab}"] = round(float(a.pnl[mm & a.won.notna().to_numpy()].sum() / cst), 4) if cst > 0 else None
    res[f_] = r
# VALIDATE halves by window start (aggregate)
mv = ok_all & (a.fold2 == "VALIDATE").to_numpy()
med = np.median(a.st[mv])
for lab, mh in (("first", mv & (a.st < med).to_numpy()), ("second", mv & (a.st >= med).to_numpy())):
    res[f"VALIDATE_half_{lab}"] = {k_: round(float(p.astype(float)[mh & np.isfinite(p.astype(float))].mean()), 3) for k_, p in pred.items()} | {"n": int(mh.sum())}
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter16_open_strike.json").write_text(json.dumps(res, indent=1))
