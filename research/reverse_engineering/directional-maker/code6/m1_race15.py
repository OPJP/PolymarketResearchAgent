"""Iteration 6, I2 (X27) venue race on the ladder center: is the input Chainlink itself, or any venue delayed ~2 s?

Same F* / skew construction as code6/m1_center.py (exact-500 adds, BTC 5m, live block). For each venue X (Chainlink
RTDS by value timestamp; Binance futures bookTicker mid; Binance spot, Coinbase, OKX swap, Bybit perp trades by server
time) a 1-s last-price series; fair_X(t - lag) = digital fair with strike = X's own mean over [start-60, start) and the
futures realised vol x 1.4. Regress skew on fair_X - mid: R^2 on live BUILD (< 15:00 UTC), held-out R^2 after.
    python code6/m1_race.py <start_ts> <end_ts>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
SPLIT = 1793458800


def series_1s(pairs, s0, s1):
    """pairs: (ms, px) -> last price per second on [s0, s1)."""
    if not pairs:
        return None
    d = pd.DataFrame(pairs, columns=["s", "px"]).sort_values("s")
    sec = np.arange(s0, s1)
    idx = np.searchsorted(d.s.to_numpy(), (sec + 1) * 1000, side="left") - 1
    v = np.where(idx >= 0, d.px.to_numpy()[np.clip(idx, 0, None)], np.nan)
    return pd.Series(v, index=sec)


def main(a, b):
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet")
    ev = ev[ev.w.str.contains("btc-updown-15m") & (ev.d == 500.0)]
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    s0, s1 = a - 400, b + 60
    V = {}
    V["futures"] = series_1s([(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", s0, s1) if r["r"][0] == "b" and r["r"][2]], s0, s1)
    V["spot"] = series_1s([(r["r"][1], r["r"][3]) for r in iter_dm("dm_bns", s0, s1) if r["r"][0] == "a"], s0, s1)
    V["coinbase"] = series_1s([(r["r"][0], r["r"][1]) for r in iter_dm("dm_cb", s0, s1)], s0, s1)
    V["okx"] = series_1s([(r["r"][1], r["r"][2]) for r in iter_dm("dm_okx", s0, s1) if r["r"][0] == "t"], s0, s1)
    V["bybit"] = series_1s([(r["r"][1], r["r"][2]) for r in iter_dm("dm_byb", s0, s1) if r["r"][0] == "t"], s0, s1)
    cl = {}
    for r in iter_dm("dm_rtds", s0, s1):
        if r["q"] != "crypto_prices_chainlink":
            continue
        try:
            j = json.loads(r["m"])
        except ValueError:
            continue
        for x in (j.get("payload") or {}).get("data", []) or []:
            cl[int(x["timestamp"]) // 1000] = float(x["value"])
    V["chainlink"] = pd.Series(cl).sort_index().reindex(np.arange(s0, s1)).ffill()
    fut = V["futures"]
    # hybrid nowcasts: Chainlink stamped t-k scaled by the futures change since t-k (k = 2, 3)
    for k in (2, 3):
        V[f"hyb{k}_"] = V["chainlink"].shift(k) * fut / fut.shift(k)
    r1 = np.log(fut).diff()
    rows = []
    for w, g in ev.groupby("w"):
        st = int(w.split("-")[-1])
        if st < a or st + 900 > b:
            continue
        K = {k: (v.loc[st - 60:st - 1].mean() if v is not None else np.nan) for k, v in V.items()}
        tw_ = tch[tch.w == w].sort_values("s")
        ts_, bb_, ba_ = tw_.s.to_numpy(), tw_.bb.to_numpy(), tw_.ba.to_numpy()
        gb, ga = g[g.side == 1], g[g.side == 0]
        for t in range(st + 5, st + 870):
            T = t * 1000
            mb = gb[(gb.s > T - 1500) & (gb.s <= T)]
            ma = ga[(ga.s > T - 1500) & (ga.s <= T)]
            if not len(mb) or not len(ma):
                continue
            qu, au = float(mb.p.max()), float(ma.p.min())
            i = np.searchsorted(ts_, T, side="right") - 1
            if au <= qu or i < 0:
                continue
            mid = (bb_[i] + ba_[i]) / 2
            sig = float(r1.loc[t - 300:t - 1].std()) * 1.4
            tau = max(st + 900 - t, 1.0)
            row = {"t": t, "sk": (qu + au) / 2 - mid, "mid": mid}
            for k, v in V.items():
                if v is None or not (K[k] == K[k]):
                    continue
                for lag in (0, 1, 2, 3, 4):
                    px = v.get(t - lag, np.nan)
                    row[f"{k}{lag}"] = norm.cdf(np.log(px / K[k]) / (sig * np.sqrt(tau))) if (px == px and sig > 0) else np.nan
            rows.append(row)
    D = pd.DataFrame(rows)
    tr, te = D[D.t < SPLIT], D[D.t >= SPLIT]
    res = {"seconds": int(len(D)), "race": {}}
    for X in [c for c in D.columns if c not in ("t", "sk", "mid")]:
        a_, b_ = tr[[X, "sk", "mid"]].dropna(), te[[X, "sk", "mid"]].dropna()
        if len(a_) < 100 or len(b_) < 100:
            continue
        xa, ya = (a_[X] - a_.mid).to_numpy(), a_.sk.to_numpy()
        sl, ic = np.polyfit(xa, ya, 1)
        xb, yb = (b_[X] - b_.mid).to_numpy(), b_.sk.to_numpy()
        r2b = 1 - np.sum((yb - ic - sl * xb) ** 2) / np.sum((yb - yb.mean()) ** 2)
        res["race"][X] = [round(float(sl), 3), round(float(np.corrcoef(xa, ya)[0, 1] ** 2), 3), round(float(r2b), 3), int(len(a_)), int(len(b_))]
    (HERE.parent / "results" / f"iter6_m1_race15_{a}_{b}.json").write_text(json.dumps(res, indent=1))
    for k, v in res["race"].items():
        print(k, v)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
