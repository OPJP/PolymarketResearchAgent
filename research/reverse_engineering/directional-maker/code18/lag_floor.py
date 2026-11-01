"""iteration 18, T13 = X217 (mechanics panel P3, light form; pre-registered in NOTES.md 13:17 UTC 11-01): which feed's moves
does the at-touch post side follow, and with what lag floor? Posts: at-touch 500/1000 schedule adds 0.10-0.90 of BTC 5m /
15m windows (it14_qu_rebuilt tables; server ms; sd 1 = Up bid = +1). Feeds (each venue's own stamps, development
recordings dm_* / dx_* / dy_rtds): Binance USD-M bookTicker mid, Binance spot aggTrade, OKX swap ticker mid, Bybit linear
best mid, Coinbase ticker mid, Hyperliquid bbo mid, Deribit index, Bitstamp trades, Chainlink publish (value at publish ms).
Events = $1 bricks (the value moved >= $1 from the last brick level), signed. For each post: lag to the last same-sign
brick and to the last opposite-sign brick. Report per feed: the share of posts with a same-sign brick in (0, 300] ms vs an
opposite-sign one, the 5-ms histogram mode of the same-sign lag in (0, 500] ms, and the share inside [mode - 15, mode + 15]
ms against the opposite-sign share in the same band (ratio). Signature (panel): one feed with >= 30% of posts inside a
30-ms band and <= 10% for the control."""
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
BLOCKS = {"1101_0700_1200": (1793516400, 1793534400, ["it14_qu_rebuilt_1793516400_1793524500.parquet", "it14_qu_rebuilt_1793524500_1793534400.parquet"])}


def points(feed, a, b):
    out = []
    for h in range(a - a % 3600, b, 3600):
        try:
            for r in live.iter_live(feed, max(h, a - 5), min(h + 3600, b + 5)):
                if feed == "dy_rtds":
                    if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
                        out.append((int(r["P"]), float(r["v"])))
                    continue
                x = r.get("r")
                if not x:
                    continue
                try:
                    if feed == "dm_bnf" and x[0] == "b":
                        out.append((int(x[1]), 0.5 * (x[3] + x[5])))
                    elif feed == "dm_bns" and x[0] == "a":
                        out.append((int(x[1]), float(x[3])))
                    elif feed == "dm_okx" and x[0] == "k":
                        out.append((int(x[1]), 0.5 * (x[3] + x[4])))
                    elif feed == "dm_byb" and x[0] == "b":
                        out.append((int(x[1]), 0.5 * (x[2] + x[3])))
                    elif feed == "dm_cb" and x[4] and x[5]:
                        out.append((int(x[0]), 0.5 * (x[4] + x[5])))
                    elif feed == "dm_hl" and x[0] == "b":
                        out.append((int(x[1]), 0.5 * (x[2] + x[3])))
                    elif feed == "dx_drb" and x[0] == "i":
                        out.append((int(x[1]), float(x[2])))
                    elif feed == "dx_bst":
                        out.append((int(x[0]) // 1000, float(x[1])))
                except (TypeError, IndexError, ValueError):
                    continue
        except (zlib.error, EOFError, OSError):
            continue
    out.sort()
    return out


def bricks(pts, step=1.0):
    ts, sg = [], []
    if not pts:
        return np.array([], np.int64), np.array([])
    lvl = pts[0][1]
    for t, v in pts:
        d = v - lvl
        if abs(d) >= step:
            ts.append(t)
            sg.append(1.0 if d > 0 else -1.0)
            lvl = v
    return np.array(ts, np.int64), np.array(sg)


def main():
    out = {}
    for name, (a, b, files) in BLOCKS.items():
        q = pd.concat([pd.read_parquet(C / f) for f in files], ignore_index=True)
        q = q[(q.s >= a * 1000) & (q.s < b * 1000) & (q.p >= 0.10) & (q.p <= 0.90) & q.dz.isin([500.0, 1000.0])].sort_values("s")
        t = q.s.to_numpy(np.int64)
        sg = np.where(q.sd == 1, 1.0, -1.0)
        rec = {"posts": int(len(q))}
        for feed in ("dm_bnf", "dm_bns", "dm_okx", "dm_byb", "dm_cb", "dm_hl", "dx_drb", "dx_bst", "dy_rtds"):
            pts = points(feed, a, b)
            bt, bs = bricks(pts)
            if len(bt) < 50:
                rec[feed] = {"bricks": int(len(bt)), "note": "too few events"}
                continue
            lag_same = np.full(len(t), np.nan)
            lag_opp = np.full(len(t), np.nan)
            up_t, dn_t = bt[bs > 0], bt[bs < 0]
            for k, (tk, s_) in enumerate(zip(t, sg)):
                same, opp = (up_t, dn_t) if s_ > 0 else (dn_t, up_t)
                i = np.searchsorted(same, tk, side="right") - 1
                j = np.searchsorted(opp, tk, side="right") - 1
                if i >= 0:
                    lag_same[k] = tk - same[i]
                if j >= 0:
                    lag_opp[k] = tk - opp[j]
            ins = (lag_same > 0) & (lag_same <= 300)
            ino = (lag_opp > 0) & (lag_opp <= 300)
            h, edges = np.histogram(lag_same[(lag_same > 0) & (lag_same <= 500)], bins=np.arange(0, 505, 5))
            mode = float(edges[int(np.argmax(h))] + 2.5) if h.sum() else np.nan
            band_s = (lag_same >= mode - 15) & (lag_same <= mode + 15)
            band_o = (lag_opp >= mode - 15) & (lag_opp <= mode + 15)
            rec[feed] = {"bricks": int(len(bt)), "share_same_0_300ms": round(float(ins.mean()), 3), "share_opp_0_300ms": round(float(ino.mean()), 3),
                         "mode_ms": mode, "share_same_in_mode_band": round(float(band_s.mean()), 3), "share_opp_in_mode_band": round(float(band_o.mean()), 3),
                         "p10_same_lag_ms_in_0_500": float(np.nanpercentile(lag_same[(lag_same > 0) & (lag_same <= 500)], 10)) if np.any((lag_same > 0) & (lag_same <= 500)) else None}
            print(feed, rec[feed], flush=True)
        out[name] = rec
    best = max(((f, v) for f, v in out["1101_0700_1200"].items() if isinstance(v, dict) and "share_same_in_mode_band" in v),
               key=lambda kv: kv[1]["share_same_in_mode_band"] - kv[1]["share_opp_in_mode_band"])
    out["best_feed"] = best[0]
    out["signature_met"] = bool(best[1]["share_same_in_mode_band"] >= 0.30 and best[1]["share_opp_in_mode_band"] <= 0.10)
    (HERE.parent / "results" / "iter18_lag_floor.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"best": out["best_feed"], "sig": out["signature_met"]}))


if __name__ == "__main__":
    main()
