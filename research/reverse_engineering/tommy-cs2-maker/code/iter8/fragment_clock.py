"""Iteration 8 (test of Z8 in CS2): a spectator-relay reader would see in-game events in relay fragments, so the feed's
messages inside one map would sit on a fragment grid of fixed (unknown) period P and per-map phase. The information
panel tested exact P = 1, 2, 3 s only. Here: a fine-grid scan, P in [0.8, 8.0] s (step 0.005 s), of the Rayleigh
statistic of within-event differences between feed message times (first signing of each take cluster of the wallet
and of P4e, 500-ms gap, 16-22 Oct CS2), for pairs 20-600 s apart. Null: every cluster time jittered by U(-2, 2) s
(kills any sub-2-s grid), 40 draws of the grid maximum. Output: results/fragment_clock.json
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
H = 1792713600
PER = np.arange(0.8, 8.0001, 0.005)


def rayleigh_max(diffs):
    best = np.zeros(len(PER))
    n = len(diffs)
    if n == 0:
        return best
    for i0 in range(0, len(PER), 120):
        ph = 2 * np.pi * diffs[None, :] / PER[i0:i0 + 120, None]
        best[i0:i0 + 120] = np.abs(np.exp(1j * ph).sum(axis=1)) ** 2 / n
    return best


def pair_diffs(times_by_event, rng=None):
    out = []
    for t in times_by_event:
        t = np.sort(t + (rng.uniform(-2, 2, len(t)) if rng is not None else 0))
        d = t[None, :] - t[:, None]
        d = d[(d >= 20) & (d <= 600)]
        out.append(d)
    return np.concatenate(out) if out else np.array([])


def main():
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["event"])
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted(glob.glob(str(OUT / "calldata_pub" / "*.parquet")))])
    ev = a.drop_duplicates("token_id").set_index(a.drop_duplicates("token_id").token_id.astype(str)).event.to_dict()
    T = pd.concat([a[cols], b]).drop_duplicates(["tx", "idx"])
    T["maker"] = T.maker.str.lower()
    T["token_id"] = T.token_id.astype(str)
    T = T[(T.idx == -1) & (T.side == 0) & (T.sign_ms > 1.79e12) & (T.sign_ms < H * 1000) & T.maker.isin([W, P4E])]
    T["event"] = T.token_id.map(ev)
    T = T[T.event.notna() & T.event.str.startswith("cs2")]
    res = {}
    rng = np.random.default_rng(21)
    for name, sub in (("wallet", T[T.maker == W]), ("p4e", T[T.maker == P4E]), ("both", T)):
        tb = []
        for e, g in sub.groupby("event"):
            s = np.sort(g.sign_ms.to_numpy(float) / 1000)
            c = s[np.concatenate([[True], np.diff(s) > 0.5])]
            if len(c) >= 5:
                tb.append(c)
        d = pair_diffs(tb)
        R = rayleigh_max(d)
        k = int(np.argmax(R))
        nul = [float(rayleigh_max(pair_diffs(tb, rng)).max()) for _ in range(40)]
        top = np.argsort(R)[::-1][:5]
        res[name] = {"events": len(tb), "pairs": int(len(d)), "max_R": round(float(R[k]), 2), "best_P_s": round(float(PER[k]), 3),
                     "top5_P_s": [round(float(PER[i]), 3) for i in top], "top5_R": [round(float(R[i]), 2) for i in top],
                     "null_max_R_p50_p95": [round(float(np.percentile(nul, 50)), 2), round(float(np.percentile(nul, 95)), 2)],
                     "p": round(float(np.mean(np.array(nul) >= R[k])), 3)}
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "fragment_clock.json", "w"), indent=1)


if __name__ == "__main__":
    main()
