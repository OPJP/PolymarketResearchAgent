"""Iteration 9 (follow-up of X124: is the wallet's price LEVEL its private value?), BUILD-live, uncensored adds.
For every validated own add (linked_adds_dev: owner == wallet, or the market fingerprint in a burst / odd size; the
ladder_machine rule) and every other add on the same books (placebo), the bid's offset from the others' mid of its
token 100 ms before the add (cents; others_mid_dev, own levels removed), and the others' mid move from then to +2 / +10 /
+30 s. Spearman(offset, future move) for own vs other adds, with a within-book time-shift null (the own adds' offsets
re-paired with the mid moves of the same book at shifted times, +-30..300 s, 500 draws). A positive own-add correlation
above the placebo and the null means its quote level leads the public book (a private value in the price).
Output: results/add_level_info.json"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def main():
    A = pd.read_parquet(OUT / "linked_adds_dev.parquet")
    A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
    A = A[A.kind == "add"]
    M = pd.read_parquet(OUT / "others_mid_dev.parquet").sort_values(["a", "s"])
    mids = {a: (g.s.to_numpy(float), g.mid.to_numpy(float)) for a, g in M.groupby("a")}
    rows = []
    for r in A.itertuples():
        x = mids.get(r.a)
        if x is None:
            continue
        ts, md = x
        j0 = np.searchsorted(ts, r.s - 100, side="right") - 1
        if j0 < 0:
            continue
        tok0 = r.side == "BUY"
        bid = r.p if tok0 else 1 - r.p
        m0 = md[j0] if tok0 else 1 - md[j0]
        rec = {"a": r.a, "s": float(r.s), "own": bool(r.vown), "off": (bid - m0) * 100, "tok0": tok0}
        for h in (2, 10, 30):
            j = np.searchsorted(ts, r.s + h * 1000, side="right") - 1
            mh = md[j] if tok0 else 1 - md[j]
            rec[f"dm{h}"] = (mh - m0) * 100
        rows.append(rec)
    X = pd.DataFrame(rows)
    X = X[np.isfinite(X.off) & (X.off.abs() <= 15)]
    res = {"own_adds": int(X.own.sum()), "other_adds": int((~X.own).sum())}
    rng = np.random.default_rng(8)
    for h in (2, 10, 30):
        o, p = X[X.own], X[~X.own]
        ro = spearmanr(o.off, o[f"dm{h}"])[0]
        rp = spearmanr(p.off, p[f"dm{h}"])[0]
        # null: own offsets re-paired with mid moves of the same book at shifted times
        nul = []
        for _ in range(200):
            dm = []
            for r in o.itertuples():
                ts, md = mids[r.a]
                sh = r.s + rng.choice([-1, 1]) * rng.uniform(30000, 300000)
                j0 = np.searchsorted(ts, sh - 100, side="right") - 1
                j = np.searchsorted(ts, sh + h * 1000, side="right") - 1
                if j0 < 0:
                    dm.append(0.0)
                    continue
                v = (md[j] - md[j0]) * 100
                dm.append(v if r.tok0 else -v)
            nul.append(spearmanr(o.off, dm)[0])
        res[f"h{h}s"] = {"own_spearman": round(float(ro), 4), "other_spearman": round(float(rp), 4),
                         "null_mean": round(float(np.mean(nul)), 4), "null_p95": round(float(np.percentile(nul, 95)), 4),
                         "p_own": round(float(np.mean(np.array(nul) >= ro)), 4),
                         "own_move_by_offset_tercile": {str(k): round(float(v), 3) for k, v in o.groupby(pd.qcut(o.off, 3, duplicates="drop"), observed=True)[f"dm{h}"].mean().items()}}
    res["own_offset_quantiles_c"] = [round(float(q), 2) for q in X[X.own].off.quantile([0.1, 0.25, 0.5, 0.75, 0.9])]
    res["other_offset_quantiles_c"] = [round(float(q), 2) for q in X[~X.own].off.quantile([0.1, 0.25, 0.5, 0.75, 0.9])]
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "add_level_info.json", "w"), indent=1)


if __name__ == "__main__":
    main()
