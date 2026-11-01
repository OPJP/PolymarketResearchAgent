"""X154 add-on (iteration 11): do synchronous non-own adds on the SAME book land at the wallet's level? (uncensored level
agreement, BUILD-live 10-31 14:50-18:00, level_events_dev + the iteration-7 validated own label).

For each validated own add (price p, side, asset a, server time s) with no consumption on that book in the 300 ms before:
  sync      = a non-own ADD on the same asset and side within +-40 ms (excluding the add itself);
  sync_1c   = such an add priced within 1c of p (same side);
  diff      = the |price - p| of the nearest synchronous non-own add, in cents.
Null: the same statistics with the wallet's add (asset, side, p) moved to s + delta, |delta| uniform in [200, 1000] ms
(2,000 draws). A shared value predicts sync_1c >> null and small diffs; own models predict sync_1c at the null given sync.
Output: results/sameprice_sync.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
C = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def main():
    E = pd.read_parquet(C / "level_events_dev.parquet")
    LA = pd.read_parquet(C / "linked_adds_dev.parquet", columns=["a", "s", "side", "p", "d", "z", "F_mkt", "in_burst"])
    LA["own"] = LA.F_mkt & (LA.in_burst | (LA.d.round(2) != 100.0))
    E = E.merge(LA[["a", "s", "side", "p", "d", "z", "own"]].drop_duplicates(["a", "s", "side", "p", "d", "z"]),
                on=["a", "s", "side", "p", "d", "z"], how="left")
    E["own"] = E.own.fillna(False).astype(bool)
    own = E[(E.kind == "add") & E.own]
    oth = E[(E.kind == "add") & ~E.own]
    cons = {a: np.sort(g.s.to_numpy(float)) for a, g in E[E.kind == "cons"].groupby("a")}
    idx = {(a, sd): (g.s.to_numpy(float), g.p.to_numpy(float)) for (a, sd), g in oth.sort_values("s").groupby(["a", "side"])}

    def stat(a, sd, t, p):
        v = idx.get((a, sd))
        if v is None:
            return False, False, np.nan
        ts, ps = v
        lo, hi = np.searchsorted(ts, t - 40), np.searchsorted(ts, t + 40, side="right")
        if hi <= lo:
            return False, False, np.nan
        d = np.abs(ps[lo:hi] - p) * 100
        return True, bool((d <= 1.0 + 1e-6).any()), float(d.min())

    def ok(a, t):
        c = cons.get(a)
        if c is None:
            return True
        j = np.searchsorted(c, t)
        return not (j > 0 and c[j - 1] >= t - 300)

    R = []
    for r in own.itertuples():
        t = float(r.s)
        if not ok(r.a, t):
            continue
        R.append((r.a, r.side, t, float(r.p)) + stat(r.a, r.side, t, float(r.p)))
    R = pd.DataFrame(R, columns=["a", "side", "t", "p", "sync", "sync1c", "diff"])
    rng = np.random.default_rng(23)
    nul = []
    for _ in range(2000):
        x = R.iloc[rng.integers(0, len(R))]
        t = x.t + rng.choice([-1, 1]) * rng.uniform(200, 1000)
        if not ok(x.a, t):
            continue
        nul.append(stat(x.a, x.side, t, x.p))
    N = pd.DataFrame(nul, columns=["sync", "sync1c", "diff"])
    out = {"own_adds": int(len(R)),
           "real": {"sync": round(float(R.sync.mean()), 3), "sync_1c": round(float(R.sync1c.mean()), 3),
                    "sync_1c_given_sync": round(float(R[R.sync].sync1c.mean()), 3) if R.sync.any() else None,
                    "diff_c_median_given_sync": round(float(R[R.sync]["diff"].median()), 2) if R.sync.any() else None},
           "null_near_shift": {"sync": round(float(N.sync.mean()), 3), "sync_1c": round(float(N.sync1c.mean()), 3),
                               "sync_1c_given_sync": round(float(N[N.sync].sync1c.mean()), 3) if N.sync.any() else None,
                               "diff_c_median_given_sync": round(float(N[N.sync]["diff"].median()), 2) if N.sync.any() else None}}
    (RES / "sameprice_sync.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
