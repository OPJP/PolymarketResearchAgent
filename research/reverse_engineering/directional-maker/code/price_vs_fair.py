"""Where do the cluster's BTC 5m maker bids sit relative to the spot fair value
and to recent spot moves? (BUILD only.)"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import Spot, fair_up  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker"


def main(lo, hi):
    mk = pd.read_parquet(OUT / f"mk5_{lo}_{hi}.parquet")
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[spd["sec"] < hi]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    t = mk["ts"].to_numpy()
    st, en = mk["start_ts"].to_numpy(), mk["start_ts"].to_numpy() + 300
    sgn = np.where(mk["is_up"] == 1, 1, -1)
    out = {}
    for lag in (0, 1, 2, 5, 10, 30):
        fu, z = fair_up(sp, st, en, t - lag)
        fs = np.where(sgn == 1, fu, 1 - fu)
        d = mk["price"].to_numpy() - fs
        out[lag] = d
        print(f"lag {lag:2d}s price-fair_s q10/25/50/75/90", np.round(np.nanquantile(d, [0.1, 0.25, 0.5, 0.75, 0.9]), 3),
              "corr(price,fair_s)", round(np.corrcoef(mk["price"], np.nan_to_num(fs, nan=0.5))[0, 1], 3))
    fu_end, _ = fair_up(sp, st, en, en)  # proxy of final outcome (diagnostic only)
    # spot moves before the fill, signed by side (bp)
    for k in (1, 2, 3, 5, 10, 30):
        r = np.log(sp.last(t) / sp.last(t - k)) * 1e4 * sgn
        print(f"signed spot return over {k:2d}s before fill: mean {np.nanmean(r):.2f}bp, share>0 {np.mean(r > 0):.3f}, share<0 {np.mean(r < 0):.3f}")
    # after the fill
    for k in (1, 2, 5, 10, 30):
        r = np.log(sp.last(t + k + 1) / sp.last(t + 1)) * 1e4 * sgn
        print(f"signed spot return {k:2d}s AFTER fill: mean {np.nanmean(r):.2f}bp, share>0 {np.mean(r > 0):.3f}")
    # bucket by fair_s at fill: price and win rate
    fu, _ = fair_up(sp, st, en, t)
    fs = np.where(sgn == 1, fu, 1 - fu)
    mk = mk.assign(fair_s=fs, d=mk["price"] - fs)
    mk["fb"] = pd.cut(mk["fair_s"], [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    g = mk.groupby("fb", observed=True).agg(n=("price", "size"), px=("price", "mean"), fair=("fair_s", "mean"), won=("won", "mean"))
    print(g.round(3).to_string())
    mk[["order_hash", "ts", "price", "is_up", "fair_s", "d", "won", "rel", "shares", "wallet", "taker"]].to_parquet(OUT / f"mk5_fair_{lo}_{hi}.parquet", index=False)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
