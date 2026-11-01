"""iteration 18, X218 readout (written before the data exists; run after 11-02 14:50 UTC): the cluster's behaviour in the
BTC 5m windows that start at 14:30 UTC (09:30 New York after the DST change; treatment) and 13:30 UTC (the old slot;
placebo) on 11-02, from the full-depth dm_clob_raw of code18/open_rec.py, dm_bnf, and the cluster's activity (data-api,
development units only). Per window: cluster-size adds (62 / 125 / 250 / 500 / 1000 / 2000) per outcome in [W - 60, W + 300)
by 10-s bin with their price minus the outcome's mid; the first add on the cheaper outcome after W and the first 3-sigma
0.5-s futures jump after W; the ladder centre per 10-s bin (best cluster-size Up bid and Down bid); the cluster's BUY fills
in the window and their cheap share. T5 readings in NOTES.md.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code18/open_read.py 1793629800 1793626200
"""
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code14"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from lagged_quote import fut_mid, live  # noqa: E402
import indicators as ind  # noqa: E402

SIZES = {62.0, 125.0, 250.0, 500.0, 1000.0, 2000.0}
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def adds(W):
    slug = f"btc-updown-5m-{W}"
    book, out, mids = None, [], []
    for h in range((W - 60) - (W - 60) % 3600, W + 300, 3600):
        try:
            for r in live.iter_live("dm_clob_raw", max(h, W - 60), min(h + 3600, W + 300)):
                if r.get("w") != slug:
                    continue
                if r.get("k") == "bk":
                    book = {1: {round(p, 3): z for p, z in r.get("b", [])}, 0: {round(p, 3): z for p, z in r.get("o", [])}}
                elif r.get("k") == "pc" and book is not None:
                    for row in r["c"]:
                        sd, p, z = row[0], round(row[1], 3), row[2]
                        if sd >= 2:
                            continue
                        old = book[sd].get(p, 0.0)
                        book[sd][p] = z
                        mm = (row[3] + row[4]) / 2
                        mids.append((r["s"], mm))
                        dz = round(z - old, 2)
                        if dz in SIZES:
                            # sd 1 = Up bid at p; sd 0 = Up ask at p = Down bid at 1 - p
                            out.append((r["s"], "up" if sd == 1 else "down", p if sd == 1 else round(1 - p, 3), dz, mm))
        except (zlib.error, EOFError, OSError):
            continue
    return pd.DataFrame(out, columns=["s", "outcome", "bid", "dz", "mid_up"]), pd.DataFrame(mids, columns=["s", "mid_up"])


def fills(W):
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    rows = []
    for ad, nm in CLUSTER.items():
        try:
            recs, _src, _cov = pm.activity(ad, W - 60, W + 400, types=("TRADE",))
            for a in recs:
                if a.get("type") == "TRADE" and a.get("side") == "BUY" and str(a.get("slug", "")) == f"btc-updown-5m-{W}":
                    rows.append((nm, int(a["timestamp"]), float(a["price"]), int(a.get("outcomeIndex", -1))))
        except Exception as ex:  # noqa: BLE001
            rows.append((nm, -1, np.nan, -1))
            print("activity error", nm, repr(ex)[:120])
    return pd.DataFrame(rows, columns=["w", "t", "price", "oi"])


def one(W):
    A, Mi = adds(W)
    rec = {"window": pd.Timestamp(W, unit="s").strftime("%m-%d %H:%M"), "adds": int(len(A))}
    if len(A):
        A["rel"] = (A.s // 1000 - W)
        A["bin"] = (A.rel // 10 * 10).astype(int)
        A["mid_o"] = np.where(A.outcome == "up", A.mid_up, 1 - A.mid_up)
        A["cheap"] = A.mid_o < 0.5
        g = A.groupby(["bin", "outcome"]).agg(n=("dz", "size"), px_minus_mid=("bid", "mean"))
        rec["adds_by_bin"] = {f"{b}_{o}": {"n": int(v.n), "bid_mean": round(float(v.px_minus_mid), 3)} for (b, o), v in g.iterrows()}
        after = A[A.rel >= 0]
        fc = after[after.cheap]
        rec["first_cheap_add_after_open_s"] = float((fc.s.min() / 1000 - W)) if len(fc) else None
        rec["cheap_share_of_adds_0_60s"] = round(float(after[after.rel < 60].cheap.mean()), 3) if (after.rel < 60).any() else None
        rec["cheap_share_of_adds_60_300s"] = round(float(after[after.rel >= 60].cheap.mean()), 3) if (after.rel >= 60).any() else None
        cen = []
        for b, gb in A.groupby("bin"):
            bu = gb[gb.outcome == "up"].bid.max()
            bd = gb[gb.outcome == "down"].bid.max()
            if np.isfinite(bu) and np.isfinite(bd):
                cen.append((int(b), round(float((bu + 1 - bd) / 2), 3), round(float(gb.mid_up.median()), 3)))
        rec["centre_vs_mid_by_bin"] = cen
    E, M = fut_mid(W - 600, W + 300)
    if len(E):
        tg = ind.grid(W - 300, W + 300, 0.1)
        mid = ind.asof(tg, np.asarray(E, float) / 1000.0, np.asarray(M, float))
        jt, js = ind.jumps(tg, mid, horizon=5, k=3.0, refractory_s=0.5)
        jt = np.asarray(jt)
        rec["first_3sigma_futures_jump_after_open_s"] = float(jt[jt >= W][0] - W) if np.any(jt >= W) else None
    F = fills(W)
    F = F[F.t > 0]
    if len(F):
        rec["cluster_buy_fills"] = int(len(F))
        rec["cluster_cheap_share"] = round(float((F.price < 0.5).mean()), 3)
        rec["per_wallet"] = F.groupby("w").size().to_dict()
    return rec


def main():
    out = {}
    for W in map(int, sys.argv[1:]):
        out[str(W)] = one(W)
    p = HERE.parent / "results" / f"iter18_open_read_{'_'.join(sys.argv[1:])}.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("adds_by_bin", "centre_vs_mid_by_bin")} for k, v in out.items()}, indent=1, default=str))


if __name__ == "__main__":
    main()
