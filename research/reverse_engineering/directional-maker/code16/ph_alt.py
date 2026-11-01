"""iteration 16, X185 extension (post hoc, same frozen rules as ph_long.py): the alt 5m/15m later fills; was: the long families (hourly,
daily, 4h) scored against the CLOB prices-history mid. For every later cluster BUY fill (>= 20 s after the open) on
STUDY and VALIDATE (aggregate): mid_s = the last fidelity-1 prices-history point of the bought token stamped <= T - 1.
Side: posture = 1[F_s > mid_s] with F = the Binance digital (S(T - 3) vs the family's strike from it15_nb_side, sigma =
1.0 x the symbol's 300-s Binance vol); market favourite (mid_s > 0.5); cheaper token. Price: within a tick of mid_s -
0.01, mid_s, mid_s - 0.02 (ticks of 0.01).
    python ph_long.py"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code15"))
from nb_side import Spot, C  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

a = pd.read_parquet(C / "it15_nb_side.parquet")
a = a[a.fam.str.match(r"^(eth|sol|xrp|bnb|doge)-(5m|15m)$") & (a.fold.str.startswith("STUDY") | (a.fold == "VALIDATE")) & (a.timestamp - a.st >= 20)].reset_index(drop=True)
keys = a.groupby(["conditionId", "asset"]).agg(st=("st", "first"), L=("L", "first")).reset_index()
pm = PolymarketData()
t0 = time.time()


def get(row):
    cid, tok, st, L = row
    try:
        pts, _ = pm.price_history(str(tok), int(st) - 600, int(st + L) + 60, fidelity_minutes=1)
    except Exception:  # noqa: BLE001
        return tok, None
    return tok, pts


hist = {}
with ThreadPoolExecutor(3) as ex:
    for i, (tok, pts) in enumerate(ex.map(get, keys[["conditionId", "asset", "st", "L"]].itertuples(index=False, name=None))):
        hist[str(tok)] = pts
        if i % 200 == 0:
            print("histories", i, len(keys), round(time.time() - t0), "s", flush=True)
mid = np.full(len(a), np.nan)
for tok, g in a.groupby(a.asset.astype(str)):
    pts = hist.get(tok)
    if not pts:
        continue
    pts = sorted(pts)
    ts = np.array([p[0] for p in pts], np.int64)
    pv = np.array([p[1] for p in pts], float)
    k = np.searchsorted(ts, g.timestamp.to_numpy(np.int64) - 1, side="right") - 1
    ok = (k >= 0) & (g.timestamp.to_numpy(np.int64) - ts[np.clip(k, 0, None)] <= 600)
    mid[g.index] = np.where(ok, pv[np.clip(k, 0, None)], np.nan)
a["mid_s"] = mid
sp = Spot()
sig = np.full(len(a), np.nan)
for sym, g in a.groupby("sym"):
    t = g.timestamp.to_numpy(np.int64) - 3
    grid = t[:, None] + np.arange(-300, 1)[None, :]
    v = np.log(sp.close_at(sym, grid.ravel()).reshape(grid.shape))
    with np.errstate(invalid="ignore"):
        sig[g.index] = np.nanstd(np.diff(v, axis=1), axis=1)
tau = np.maximum(a.st + a.L - a.timestamp, 1).to_numpy(float)
z = np.log(a.S / a.K).to_numpy(float)
Fu = norm.cdf(z / (sig * np.sqrt(tau)))
Fs = np.where(a.up == 1, Fu, 1 - Fu)
ms = a.mid_s.to_numpy(float)
pr = a.price.to_numpy(float)
fg = np.where(a.fam.str.endswith("-5m"), "alt-5m", "alt-15m")
fold = np.where(a.fold.str.startswith("STUDY"), "STUDY", "VALIDATE")
ok = np.isfinite(ms) & np.isfinite(Fs)
rules = {"posture_mid_k1.0": (Fs > ms), "market_favourite_mid": (ms > 0.5), "cheaper_mid": (ms < 0.5)}
prices = {"mid_m1": ms - 0.01, "mid": ms, "mid_m2": ms - 0.02}
out = {"fills": int(len(a)), "with_mid": int(np.isfinite(ms).sum()), "tokens": int(len(keys))}
for f_ in ("STUDY", "VALIDATE"):
    for g_ in ("alt-5m", "alt-15m", "all"):
        m = ok & (fold == f_) & ((fg == g_) if g_ != "all" else True)
        if not m.any():
            continue
        r = {"n": int(m.sum())}
        for nm, p in rules.items():
            r[nm] = round(float(p[m].mean()), 3)  # the bought outcome satisfies the rule = the rule picks the bought side
        for nm, q in prices.items():
            r["price_" + nm] = round(float((np.abs(np.round(q[m], 2) - pr[m]) <= 0.0101).mean()), 3)
        r["fill_minus_mid_median"] = round(float(np.median(pr[m] - ms[m])), 4)
        out[f"{f_}_{g_}"] = r
print(json.dumps(out, indent=1))
(HERE.parent / "results/iter16_ph_alt.json").write_text(json.dumps(out, indent=1))
