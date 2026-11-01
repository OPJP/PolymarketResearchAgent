"""Iteration 8 (A5 / X73): which Binance market triggers the June signing? At the cluster's signing ms S (filled maker
orders, BTC Up/Down, June) and at random times, the absolute log move of spot and of futures over a pre-window
[S - 450, S - 50] ms (the measured reaction window) in bp; the rate ratio (signing vs random) in four cells:
spot moved / futures moved (|move| >= thr bp), and the latency of the last move: ms from the last 50-ms bin with a
move >= 0.5 bp to S, by market.
    python code8/june_trig.py 2026-06-12
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from june_lag import series, J, OUT  # noqa: E402


def main(d):
    o = pd.read_parquet(J / f"orders_{d}.parquet")
    o = o[(o.sign_ms > 0) & o.slug.str.contains("btc-updown", na=False)]
    S = {"cluster_maker": o[(o.cl == True) & (o.role == "maker")].sign_ms.to_numpy(np.int64),
         "other_maker": o[(o.cl == False) & (o.role == "maker")].sign_ms.to_numpy(np.int64),
         "taker": o[(o.cl == False) & (o.role == "taker")].sign_ms.to_numpy(np.int64)}
    rng = np.random.default_rng(8)
    lo, hi = S["cluster_maker"].min(), S["cluster_maker"].max()
    S["random"] = rng.integers(lo, hi, 100000)
    ser = {k: series(k, d) for k in ("fut", "spot")}
    def mv(kind, ms, a_ms, b_ms):
        b0, lr = ser[kind]
        b = ms // 50 - b0
        ok = (b > 100) & (b < len(lr) - 100)
        out = np.full(len(ms), np.nan)
        ka, kb = -(a_ms // 50), -(b_ms // 50)
        idx = b[ok][:, None] + np.arange(ka, kb + 1)[None, :]
        out[ok] = lr[idx].sum(axis=1)
        return out
    res = {}
    for thr in (0.5, 1.0, 2.0):
        cell = {}
        for g, ms in S.items():
            sp = mv("spot", ms, 450, 50)
            fu = mv("fut", ms, 450, 50)
            ok = ~np.isnan(sp) & ~np.isnan(fu)
            sp, fu = sp[ok] >= thr, fu[ok] >= thr
            cell[g] = {"spot_only": float((sp & ~fu).mean()), "fut_only": float((fu & ~sp).mean()), "both": float((sp & fu).mean()),
                       "none": float((~sp & ~fu).mean()), "n": int(ok.sum())}
        rr = {g: {c: round(cell[g][c] / max(cell["random"][c], 1e-9), 2) for c in ("spot_only", "fut_only", "both", "none")}
              for g in S if g != "random"}
        res[f"thr_{thr}bp"] = {"random_rates": {c: round(v, 4) for c, v in cell["random"].items()}, "rate_ratio_vs_random": rr}
    # latency of the last move >= 0.5 bp (per 50-ms bin) before S, within 2 s
    lat = {}
    for kind in ("fut", "spot"):
        b0, lr = ser[kind]
        for g in ("cluster_maker", "other_maker", "taker", "random"):
            ms = S[g]
            b = ms // 50 - b0
            b = b[(b > 100) & (b < len(lr) - 100)]
            W = lr[b[:, None] + np.arange(-40, 0)[None, :]] >= 0.5   # bins k=-40..-1
            has = W.any(axis=1)
            last = 40 - np.argmax(W[:, ::-1], axis=1)  # bins before S of the latest move
            v = last[has] * 50
            lat.setdefault(kind, {})[g] = {"share_with_move_2s": round(float(has.mean()), 3),
                                           "ms_since_last_move_q": np.quantile(v, [.1, .25, .5, .75]).round(0).tolist() if len(v) else None}
    res["latency_last_move"] = lat
    (OUT / f"iter8_june_trig_{d}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
