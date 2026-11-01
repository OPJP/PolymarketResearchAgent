"""Iteration 11 (C4/X75, exploratory): is the engine's volatility a running estimate since a restart? Posture with sigma =
k x sigma_E where sigma_E = sqrt(mean squared Binance 1-s log return since the epoch start), epochs: the weekly restart
(Monday 01:00 UTC), the daily restart (01:00 UTC), plus v300 and v3600 for reference. Best k per day for each estimator;
an estimator whose best k is stable across days is a candidate engine input. Binance stand-in (code9/vol_hist.py
inputs), BUILD + lot; VALIDATE days as daily aggregates.
    python code11/k_since_restart.py
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as RP  # noqa: E402
C = RP.C
KS = (0.25, 0.35, 0.5, 0.7, 0.85, 1.0, 1.2, 1.4, 1.7, 2.0, 2.5, 3.0, 4.0)
base, px = RP.load_spot()
lp = np.log(px)
r = np.diff(lp, prepend=lp[0])
cs = np.concatenate([[0.0], np.cumsum(r * r)])
secs = base + np.arange(len(px))


def since(epoch_starts, s):
    """sqrt(mean r^2 over [epoch start, s]) for second s (array)."""
    e = epoch_starts(s)
    i, j = e - base, s - base
    n = np.maximum(j - i + 1, 1)
    return np.sqrt((cs[j + 1] - cs[np.clip(i, 0, None)]) / n)


def weekly(s):
    d = pd.to_datetime(s, unit="s")
    mon = (d - pd.to_timedelta(d.dayofweek, unit="D")).normalize() + pd.Timedelta(hours=1)
    mon = np.where(mon > d, mon - pd.Timedelta(days=7), mon)
    return (pd.DatetimeIndex(mon).astype("int64") // 10 ** 9).to_numpy()


def daily(s):
    e = (s - 3600) // 86400 * 86400 + 3600
    return e


D = pd.concat([pd.read_parquet(C / f"it9/volhist_{x}.parquet", columns=["b", "is_up", "mid_up", "v300", "v3600", "S", "K", "tau"]) for x in ("build", "study", "validate")])
s = (D.b.to_numpy() - 3).astype(np.int64)
D["sw"] = since(weekly, s)
D["sd"] = since(daily, s)
x = np.log(D.S / D.K).to_numpy()
y = D.is_up.to_numpy() == 1
D["day"] = pd.to_datetime(D.b, unit="s").dt.strftime("%m-%d %a")
out = {}
for est in ("v300", "v3600", "sw", "sd"):
    acc_cols = {}
    for k in KS:
        f = norm.cdf(x / (k * D[est].to_numpy() * np.sqrt(D.tau.to_numpy())))
        acc_cols[k] = ((f > D.mid_up.to_numpy()) == y).astype(float)
    A = pd.DataFrame(acc_cols)
    A["day"] = D.day.to_numpy()
    g = A.groupby("day").mean()
    best = g.idxmax(axis=1)
    pooled = A[list(KS)].mean()
    out[est] = {"best_k_by_day": best.to_dict(), "pooled_best_k": float(pooled.idxmax()), "pooled_acc": round(float(pooled.max()), 4),
                "best_k_log_sd_across_days": round(float(np.std(np.log(best.astype(float)))), 3)}
    print(est, "pooled best", out[est]["pooled_best_k"], out[est]["pooled_acc"], "sd(log best k)", out[est]["best_k_log_sd_across_days"])
    print("   ", " ".join(f"{d[:5]}:{v}" for d, v in best.items()))
(HERE.parent / "results" / "iter11_k_since_restart.json").write_text(json.dumps(out, indent=1))
