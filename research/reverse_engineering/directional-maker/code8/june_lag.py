"""Iteration 8 (A5 / X73): June 12 decision times. Cross-correlation of the cluster's signing ms (filled maker BUY
orders, BTC 5m, real ms timestamps in June) with Binance futures and spot 50-ms absolute moves, against random times in
the same hours, and the same for other makers' and takers' signing ms (sanity). Profile m_k = mean |ln px(S+50k) -
ln px(S+50(k-1))| x 1e4 (bp per 50 ms), k = -40..+40, relative to random times.
    python code8/june_lag.py 2026-06-12
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
J = ROOT / ".cache/re/directional-maker/june"
OUT = ROOT / "research/reverse_engineering/directional-maker/results"
K = np.arange(-40, 41)


def series(kind, d):
    s = pd.read_parquet(J / f"{kind}50_{d}.parquet")
    b0, b1 = int(s.b50.min()), int(s.b50.max())
    grid = np.arange(b0, b1 + 1)
    px = np.full(len(grid), np.nan)
    px[(s.b50.to_numpy() - b0)] = s.px.to_numpy()
    px = pd.Series(px).ffill().bfill().to_numpy()
    lr = np.r_[0.0, np.abs(np.diff(np.log(px)))] * 1e4
    return b0, lr


def profile(b0, lr, ms):
    b = (np.asarray(ms, dtype=np.int64) // 50) - b0
    b = b[(b > 60) & (b < len(lr) - 60)]
    M = lr[b[:, None] + K[None, :]]
    return M.mean(axis=0), len(b)


def main(d):
    o = pd.read_parquet(J / f"orders_{d}.parquet")
    o = o[(o.sign_ms > 0) & o.slug.str.contains("btc-updown", na=False)]
    groups = {"cluster_maker": o[(o.cl == True) & (o.role == "maker")].sign_ms,
              "other_maker": o[(o.cl == False) & (o.role == "maker")].sign_ms,
              "taker_nonclusters": o[(o.cl == False) & (o.role == "taker")].sign_ms}
    rng = np.random.default_rng(8)
    res = {}
    for kind in ("fut", "spot"):
        b0, lr = series(kind, d)
        allms = groups["cluster_maker"].to_numpy(np.int64)
        lo, hi = allms.min(), allms.max()
        rnd = rng.integers(lo, hi, 200000)
        base, _ = profile(b0, lr, rnd)
        res[kind] = {"random_mean_bp_per_50ms": round(float(base.mean()), 4)}
        for g, ms in groups.items():
            pr, n = profile(b0, lr, ms)
            rel = pr / base
            # peak before signing (k < 0) and after (k > 0)
            pre = rel[K < 0]
            post = rel[K > 0]
            res[kind][g] = {"n": int(n), "rel_profile_k-20..+20": [round(float(v), 2) for v in rel[(K >= -20) & (K <= 20)]],
                            "peak_pre_k": int(K[K < 0][np.argmax(pre)]), "peak_pre_rel": round(float(pre.max()), 2),
                            "peak_post_k": int(K[K > 0][np.argmax(post)]), "peak_post_rel": round(float(post.max()), 2),
                            "rel_at_0": round(float(rel[K == 0][0]), 2)}
    (OUT / f"iter8_june_lag_{d}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
