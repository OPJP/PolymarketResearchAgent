"""iteration 17, T15 = X208 light (pre-registered in NOTES.md 11:31 UTC): change points of the per-2-h posture-minus-
cheaper margin on BUILD against the weekly Monday 01:00 UTC restart, with a circular day-shift null."""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inform_gate as ig  # noqa: E402

MONDAYS = [1791766800, 1792371600]  # 10-12 01:00, 10-19 01:00 UTC


def opt_partition(x, pen):
    n = len(x)
    cs = np.r_[0.0, np.cumsum(x)]
    cs2 = np.r_[0.0, np.cumsum(x * x)]

    def cost(i, j):  # segment x[i:j]
        m = j - i
        s = cs[j] - cs[i]
        return (cs2[j] - cs2[i]) - s * s / m
    F = np.full(n + 1, np.inf)
    F[0] = -pen
    last = np.zeros(n + 1, int)
    for j in range(1, n + 1):
        best, arg = np.inf, 0
        for i in range(0, j):
            v = F[i] + cost(i, j) + pen
            if v < best:
                best, arg = v, i
        F[j], last[j] = best, arg
    cps = []
    j = n
    while j > 0:
        i = last[j]
        if i > 0:
            cps.append(i)
        j = i
    return sorted(cps)


def main():
    F = ig.build_fills()
    dec = np.abs(F.mid_up - 0.5) > 0.4
    cheap_up = F.mid_up < 0.5
    nd = F[~dec].copy()
    nd["post_ok"] = (nd.post_up == nd.y).astype(float)
    nd["cheap_ok"] = (cheap_up[~dec] == nd.y).astype(float)
    nd["blk"] = (nd.ts // 7200).astype(int)
    g = nd.groupby("blk").agg(n=("post_ok", "size"), post=("post_ok", "mean"), cheap=("cheap_ok", "mean"))
    g = g[g.n >= 30]
    x = (g.post - g.cheap).to_numpy()
    t = (g.index.to_numpy() * 7200).astype(float)
    sig2 = np.var(np.diff(x)) / 2.0
    pen = 2.0 * sig2 * np.log(len(x))
    cps = opt_partition(x, pen)
    cp_t = [float(t[i]) for i in cps]

    def count(evs):
        return int(sum(any(abs(c - e) <= 4 * 3600 for e in evs) for c in cp_t))
    obs = count(MONDAYS)
    null = [count([e + k * 86400 for e in MONDAYS]) for k in range(-13, 14) if k != 0]
    seg_means = []
    bounds = [0] + cps + [len(x)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg_means.append({"from": int(t[a]), "to": int(t[b - 1] + 7200), "blocks": int(b - a), "mean_margin": round(float(x[a:b].mean()), 3)})
    each = [any(abs(c - e) <= 4 * 3600 for c in cp_t) for e in MONDAYS]
    out = {"blocks": int(len(x)), "change_points": len(cps), "cp_times": [int(c) for c in cp_t], "segments": seg_means,
           "obs_near_monday": obs, "null_counts": null, "null_q95": float(np.quantile(null, 0.95)), "each_monday_hit": each,
           "reading_met": bool(obs >= np.quantile(null, 0.95) and all(each))}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter17_cfg_steps.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
