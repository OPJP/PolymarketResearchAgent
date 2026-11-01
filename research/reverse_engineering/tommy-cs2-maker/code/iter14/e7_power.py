"""E7 power statement (min_detectable_share): plant cross-event synchrony into the out-of-fold BUILD misses used by
e2_residuals.py and rerun residual_clustering (delta 2 s, 300 null draws), three times per share s.
Planting: a share s of the unexplained orders is moved (keeping the count) to within U(0, 0.5) s of a randomly chosen
unexplained order of ANOTHER event (a common driver at second scale). Detected = p <= 0.01 and ratio >= 1.5.
Output: results/e7_power.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import indicators as ind  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def main():
    b = pd.read_parquet(OUT / "iter14_oof_bins.parquet")
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "cid", "event", "gs_ts", "role"])
    o = o[(o.role == "maker") & (o.sign_ms / 1000 < 1792540800)].copy()
    o["s"] = o.sign_ms / 1000
    o["bin_start"] = (o.gs_ts + 30 * np.floor((o.s - o.gs_ts) / 30)).astype(np.int64)
    key = b.set_index(["cid", "start"])["p_full"]
    o["p"] = key.reindex(pd.MultiIndex.from_arrays([o.cid, o.bin_start])).to_numpy()
    o = o[np.isfinite(o.p) & ((o.s - o.gs_ts) >= 600)]
    un = o[o.p < o.p.median()].reset_index(drop=True)
    ts0, ev = un.s.to_numpy(), un.event.to_numpy()
    rng = np.random.default_rng(1)
    out = {"orders": int(len(un)), "events": int(len(set(ev)))}
    found = None
    for s in (0.01, 0.02, 0.05, 0.10, 0.20):
        runs = []
        for rep in range(3):
            ts = ts0.copy()
            k = rng.choice(len(ts), int(round(s * len(ts))), replace=False)
            for i in k:
                for _ in range(20):
                    j = rng.integers(len(ts))
                    if ev[j] != ev[i]:
                        ts[i] = ts0[j] + rng.uniform(0, 0.5)
                        break
            r = ind.residual_clustering(ts, ev, delta_s=2.0, n_null=300, seed=rep, top=3)
            runs.append({"ratio": round(float(r["ratio"]), 3), "p": float(r["p"]), "detected": bool(r["p"] <= 0.01 and r["ratio"] >= 1.5)})
        out[f"s_{s}"] = runs
        print(s, runs, flush=True)
        if found is None and all(x["detected"] for x in runs):
            found = s
    out["min_detectable_share"] = found
    (RES / "e7_power.json").write_text(json.dumps(out, indent=1))
    print(out["min_detectable_share"])


if __name__ == "__main__":
    main()
