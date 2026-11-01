"""Iteration 3, family N8 (cancel latency / stale-quote pick-off, descriptive): per second t of active BTC 5m
windows and side s, the change of the Binance fair of s over the previous seconds (dF = F_s(t) - F_s(t-L), from
seconds published by t) against (a) the cluster's maker BUY fills on s stamped at t and (b) all bid-hit prints on
s stamped at t (clean prints + the cluster's). If the cluster cancels as fast as the other makers, its share of
the bid hits does not depend on dF; if its bids are slower, its share rises after drops of F_s (it is picked off).
Nothing at or after H.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa: E402
from panel2 import OUT, WALLETS, H, cluster_trades  # noqa: E402

VAL0 = 1792108800


def main():
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[w["end_ts"] <= H]
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    mk = fills[(fills["role"] == "maker") & (fills["side"] == "BUY")]
    act = set(mk["cid"])
    ct = cluster_trades()
    ctx, cw = set(ct["tx"]), set(WALLETS.values())
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[spd["sec"] < H]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    rows = []
    for f in sorted(OUT.glob("taker5m_day_*.parquet")):
        d = int(f.stem.split("_")[-1])
        tk = pd.read_parquet(f, columns=["cid", "ts", "side", "asset", "wallet", "tx"])
        tk = tk[~(tk["tx"].isin(ctx) | tk["wallet"].isin(cw)) & (tk["ts"] < H) & tk["cid"].isin(act)]
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400) & w["cid"].isin(act)]
        groups = {c: g for c, g in tk.groupby("cid", sort=False)}
        mkd = {c: g for c, g in mk[mk["day"] == d].groupby("cid", sort=False)}
        for win in wd.itertuples(index=False):
            t = np.arange(win.start_ts + 5, win.end_ts - 30)
            n = len(t)
            F = {}
            for L in (0, 1, 2, 3, 5):
                fu, _ = fair_up(sp, np.full(n, win.start_ts), np.full(n, win.end_ts), t - L)
                F[L] = fu
            g = groups.get(win.cid)
            m = mkd.get(win.cid)
            for s in ("up", "down"):
                tok = win.up_token if s == "up" else win.down_token
                if g is not None and len(g):
                    is_up = g["asset"].to_numpy() == win.up_token
                    buy = g["side"].astype(str).to_numpy() == "BUY"
                    hit = ((is_up & ~buy) | (~is_up & buy)) if s == "up" else ((~is_up & ~buy) | (is_up & buy))
                    ti = g["ts"].to_numpy()[hit].astype(np.int64) - t[0]
                    ti = ti[(ti >= 0) & (ti < n)]
                    nh = np.bincount(ti, minlength=n)[:n]
                else:
                    nh = np.zeros(n, int)
                if m is not None:
                    mm = m[m["token_id"] == tok]
                    ci = mm["ts"].to_numpy().astype(np.int64) - t[0]
                    ci = ci[(ci >= 0) & (ci < n)]
                    nc = np.bincount(ci, minlength=n)[:n]
                else:
                    nc = np.zeros(n, int)
                sg = 1.0 if s == "up" else -1.0
                rows.append(pd.DataFrame({"day": d, "rel": t - win.start_ts, "nc": nc.astype(np.int16), "nh": nh.astype(np.int16),
                                          **{f"dF{L}": ((F[0] - F[L]) * sg).astype(np.float32) for L in (1, 2, 3, 5)},
                                          "F": (F[0] if s == "up" else 1 - F[0]).astype(np.float32)}))
    a = pd.concat(rows, ignore_index=True)
    a = a[(a["F"] > 0.1) & (a["F"] < 0.9)]
    res = {}
    edges = [-1, -0.06, -0.03, -0.015, -0.005, 0.005, 0.015, 0.03, 0.06, 1]
    for split, part in (("build", a[a["day"] < VAL0]), ("validate", a[a["day"] >= VAL0])):
        r = {}
        for L in (1, 3, 5):
            c = pd.cut(part[f"dF{L}"], edges)
            g = part.groupby(c, observed=True).agg(sec=("nc", "size"), cl=("nc", "sum"), oth=("nh", "sum")).astype(np.int64)
            g["cl_rate_per_100s"] = (100 * g["cl"] / g["sec"]).round(3)
            g["oth_rate_per_100s"] = (100 * g["oth"] / g["sec"]).round(2)
            g["cl_share_of_hits"] = (g["cl"] / (g["cl"] + g["oth"])).round(4)
            r[f"L{L}"] = g.reset_index().astype(str).values.tolist()
        res[split] = r
    for split in res:
        print(split)
        for row in res[split]["L3"]:
            print("  ", row)
    (HERE.parent / "results_iter3_pickoff.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
