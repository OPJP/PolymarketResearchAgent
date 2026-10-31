"""Iteration 6, panel iter5 assumptions Q2 (X36): whose are the exact-500/100 adds? Salt counter vs adds.

Each wallet's salt is a sequential order counter (B1). Between two of its filled orders, salt2 - salt1 = the number of
orders it signed in all markets. Piecewise-linear interpolation of salt(t) between filled orders gives signatures per
60-s bin for each wallet. Exact-size adds (+500, +100) in the recorded BTC 5m/15m books (own raw recorder) per bin are
compared with the summed signatures of the three wallets: bins with more adds than signatures prove foreign orders;
the regression slope/intercept says how much of the stream the cluster can own. Development live block only.
    python code6/q2_salt.py <start_ts> <end_ts>
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache" / "re" / "directional-maker"
RES = HERE.parent / "results"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def main(a, b):
    F = pd.read_parquet(C / "it6" / f"confirmed_{a}_{b}.parquet")
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
    cd = cd[cd.maker.str.lower().isin(CL)].copy()
    cd["wallet"] = cd.maker.str.lower().map(CL)
    cd["tx"] = cd.tx.str.lower()
    x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
    ms = x.groupby("h").s.min()
    cd["ms"] = cd.tx.map(ms)
    cd = cd.dropna(subset=["ms"])
    cd["salt"] = pd.to_numeric(cd.salt, errors="coerce")
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet")
    adds = ev[(ev.d == 500.0) | (ev.d == 100.0)]
    t0, t1 = int(cd.ms.min()) // 60000 * 60000, int(cd.ms.max()) // 60000 * 60000
    grid = np.arange(t0, t1 + 60000, 60000)
    sig = np.zeros(len(grid) - 1)
    per = {}
    for w, g in cd.sort_values("ms").groupby("wallet"):
        g = g.drop_duplicates("salt").sort_values("ms")
        g = g[g.salt.diff().fillna(1) > 0]  # monotone part (restarts dropped)
        s_t = np.interp(grid, g.ms.to_numpy(), g.salt.to_numpy(), left=np.nan, right=np.nan)
        d = np.diff(s_t)
        per[w] = d
        sig += np.nan_to_num(d)
    valid = np.all([~np.isnan(v) for v in per.values()], axis=0)
    cnt = np.histogram(adds.s.to_numpy(), bins=grid)[0].astype(float)
    cnt5 = np.histogram(adds[adds.d == 500.0].s.to_numpy(), bins=grid)[0].astype(float)
    m = valid & (sig > 0)
    X, Y = sig[m], cnt[m]
    slope, icpt = np.polyfit(X, Y, 1) if m.sum() > 3 else (np.nan, np.nan)
    r2 = float(np.corrcoef(X, Y)[0, 1] ** 2) if m.sum() > 3 else np.nan
    out = {"period": [a, b], "bins_60s": int(m.sum()), "signatures_per_s_3wallets_median": round(float(np.median(X) / 60), 2),
           "per_wallet_sig_per_s_median": {w: round(float(np.nanmedian(v) / 60), 2) for w, v in per.items()},
           "exact_500_100_adds_per_s_recorded_books_median": round(float(np.median(Y) / 60), 2),
           "exact_500_adds_per_s_median": round(float(np.median(cnt5[m]) / 60), 2),
           "share_bins_adds_gt_signatures": round(float((Y > X).mean()), 3),
           "adds_over_signatures_ratio_q": pd.Series(Y / X).quantile([.1, .5, .9]).round(3).to_dict(),
           "ols_adds_on_signatures": {"slope": round(float(slope), 3), "intercept_per_min": round(float(icpt), 1), "r2": round(r2, 3)},
           "confirmed_orders_share_of_exact_adds": round(float(len(F[F.S.isin([500.0, 100.0])]) / max(len(adds), 1)), 4)}
    (RES / f"iter6_q2_salt_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
