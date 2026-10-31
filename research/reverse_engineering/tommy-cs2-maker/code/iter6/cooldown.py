"""Iteration 6, X79 (mechanics panel iter5 P5, steps 1-2): the 1.5-s cancel -> re-post cooldown.

10-31 14:50-18:00 development block (BUILD-live), level_events_dev.parquet, own levels by fingerprint with its actual
maker sizes per market (calldata_dev), whole cents. For every own cancel: the interval to the next own add on the same
side; the spike at 1,490-1,530 ms vs neighbouring bins; for cancels followed by an add in the spike: the cancelled
level's age (time since the last own add at that price), the re-post price minus the cancelled price, and whether the
cancel came within 100 ms after a change of the others' best on that side; the same for all other own cancels.
Output: results/cooldown.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["a"] = cd.token_id.astype(str).map(t0map)
    wm = cd[(cd.idx >= 0) & (cd.maker == WALLET) & cd.a.notna()]
    own_sizes = {a: set(np.round(g.shares.to_numpy(float), 2)) | {100.0} for a, g in wm.groupby("a")}
    E = pd.read_parquet(OUT / "level_events_dev.parquet").sort_values(["a", "s"]).reset_index(drop=True)
    E["own"] = [bool(w) and (round(float(z), 2) in own_sizes.get(a, {100.0})) for a, z, w in zip(E.a, E["size"], E.whole)]
    rows, ivs = [], []
    for (a, side), g in E.groupby(["a", "side"]):
        sgn = 1.0 if side == "BUY" else -1.0
        oc = g[g.own & (g.kind == "cancel")]
        oa = g[g.own & (g.kind == "add")]
        add_t, add_p = oa.s.to_numpy(float), oa.p.to_numpy(float)
        # others' best changes (non-own events) on this side: approximate by non-own add / cancel times at the touch
        no = g[~g.own & (g.kind != "cons")]
        no_t = no.s.to_numpy(float)
        for r in oc.itertuples():
            j = np.searchsorted(add_t, r.s, side="right")
            if j >= len(add_t):
                continue
            dt = add_t[j] - r.s
            ivs.append(dt)
            prev_same = np.flatnonzero((add_t < r.s) & (np.abs(add_p - r.p) < 1e-9))
            age = r.s - add_t[prev_same[-1]] if len(prev_same) else np.nan
            k = np.searchsorted(no_t, r.s)
            prior = (k > 0) and (r.s - no_t[k - 1] <= 100)
            rows.append({"dt": dt, "age": age, "repost_minus_cancel_c": round(sgn * (add_p[j] - r.p) * 100, 1),
                         "nonown_change_100ms_before": bool(prior)})
    R = pd.DataFrame(rows)
    iv = np.array(ivs)
    bins = np.arange(1300, 1720, 20)
    hist = np.histogram(iv, bins=bins)[0]
    spike = R[(R.dt >= 1490) & (R.dt < 1530)]
    other = R[(R.dt < 1490) | (R.dt >= 1530)]
    res = {"own_cancels_with_next_add": int(len(R)),
           "interval_hist_1300_1700_by_20ms": dict(zip([int(b) for b in bins[:-1]], [int(h) for h in hist])),
           "spike_n": int(len(spike)),
           "spike": {"age_ms_q": spike.age.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(0).to_dict(),
                     "repost_minus_cancel_c": spike.repost_minus_cancel_c.clip(-5, 5).value_counts(normalize=True).sort_index().round(3).to_dict(),
                     "nonown_change_100ms_before": round(float(spike.nonown_change_100ms_before.mean()), 3)},
           "other": {"age_ms_q": other.age.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(0).to_dict(),
                     "repost_minus_cancel_c": other.repost_minus_cancel_c.clip(-5, 5).value_counts(normalize=True).sort_index().round(3).to_dict(),
                     "nonown_change_100ms_before": round(float(other.nonown_change_100ms_before.mean()), 3)}}
    (RES / "cooldown.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
