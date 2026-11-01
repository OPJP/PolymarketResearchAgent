"""Iteration 3, family N12 (reference feed): does the cluster quote off Binance or off another exchange? Kraken
XBT/USD trades (polyrea.adapters.spot.kraken_trades, cached) for one day; 1-s last-trade series; the same TWAP-60
fair-value model on each feed. For the cluster's maker BUY fills that day: MAD and correlation of the fill price
with each feed's fair at lags 0-5 s (fair from seconds published by ts - L), and the opening side (first fill
<= 10 s after the start) vs sign(spot - strike) on each feed. Descriptive comparison of feeds; nothing is fitted.

python code/kraken3.py DAY0   (DAY0 < H - 86400)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from polyrea.adapters.spot import kraken_trades  # noqa: E402
from features2 import Spot, fair_up  # noqa: E402
from panel2 import OUT, H  # noqa: E402


def main(d0: int):
    assert d0 + 86400 <= H
    t0 = time.time()
    rows, _ = kraken_trades("btc", d0 - 3700, d0 + 86400)
    k = pd.DataFrame(rows, columns=["t", "px"])
    k["sec"] = np.floor(k["t"]).astype(np.int64)
    ks = k.groupby("sec")["px"].last().reset_index()
    print("kraken trades", len(k), "seconds with trades", len(ks), f"{time.time()-t0:.0f}s", flush=True)
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[(spd["sec"] >= d0 - 3700) & (spd["sec"] < d0 + 86400)]
    feeds = {"binance": Spot(spd["sec"].to_numpy(), spd["px"].to_numpy()), "kraken": Spot(ks["sec"].to_numpy(), ks["px"].to_numpy())}
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    mk = fills[(fills["role"] == "maker") & (fills["side"] == "BUY") & (fills["day"] == d0)].merge(w, on="cid")
    up = (mk["token_id"] == mk["up_token"]).to_numpy()
    res = {"day": d0, "fills": int(len(mk)), "kraken_trades": int(len(k)), "kraken_seconds_with_trades": int(len(ks))}
    for name, sp in feeds.items():
        r = {}
        for L in (0, 1, 2, 3, 5):
            fu, _ = fair_up(sp, mk["start_ts"].to_numpy(), mk["end_ts"].to_numpy(), mk["ts"].to_numpy() - L)
            fs = np.where(up, fu, 1 - fu)
            ok = (fs > 0.15) & (fs < 0.85)
            pr = mk["price"].to_numpy()
            r[f"L{L}"] = {"mad": round(float(np.median(np.abs(pr[ok] - fs[ok]))), 4), "corr": round(float(np.corrcoef(pr[ok], fs[ok])[0, 1]), 4),
                          "n": int(ok.sum())}
        # opening side
        first = mk.sort_values("ts").groupby("cid").head(1)
        first = first[first["ts"] - first["start_ts"] <= 10]
        st = first["start_ts"].to_numpy()
        gap = sp.last(first["ts"].to_numpy()) - sp.mean(st - 60, st)
        fup = (first["token_id"] == first["up_token"]).to_numpy()
        r["open_side_acc"] = round(float(np.mean((gap > 0) == fup)), 3)
        r["open_n"] = int(len(first))
        res[name] = r
    # agreement of the two feeds' opening gap sign
    print(json.dumps(res, indent=1))
    (HERE.parent / f"results_iter3_kraken_{d0}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]))
