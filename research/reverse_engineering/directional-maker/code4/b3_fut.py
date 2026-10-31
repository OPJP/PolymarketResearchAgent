"""A3/B3: does a Binance USD-M futures reference explain the limit prices better than spot (10-26, ms clock)?"""
import glob, sys
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, "research/reverse_engineering/directional-maker/code")
from features2 import Spot, TWAP  # noqa
C = ".cache/re/directional-maker/"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
D0, D1 = 1792972800, 1793059200
def ms_series(path):
    a = pd.read_parquet(C + path, columns=["ms", "px"]).sort_values("ms", kind="stable")
    return a.ms.to_numpy(), a.px.to_numpy()
def spot_from(ms, px):
    sec = ms // 1000
    last = pd.Series(px).groupby(sec).last()
    return Spot(last.index.to_numpy() + 1, last.to_numpy())  # second k's close published at k+1 (Spot.last(t) uses t-1)
REF = {}
for nm, p in (("spot", "agg_2026-10-26.parquet"), ("fut", "aggfut_2026-10-26.parquet")):
    ms, px = ms_series(p)
    REF[nm] = (ms, px, spot_from(ms, px))
win = pd.read_parquet(C + "exam/windows_5m.parquet")
up = set(win.up_token)
info = {**{t: (s, e) for t, s, e in zip(win.up_token, win.start_ts, win.end_ts)},
        **{t: (s, e) for t, s, e in zip(win.down_token, win.start_ts, win.end_ts)}}
def fair(ref, start, end, t):
    ms, px, sp = REF[ref]
    st = px[np.clip(np.searchsorted(ms, (t * 1000).astype(np.int64), side="right") - 1, 0, len(px) - 1)]
    ti = np.floor(t).astype(np.int64)
    s0 = sp.mean(start - TWAP, start); sig = sp.sigma(ti); ts = end - TWAP
    before = t < ts
    var_b = np.clip(ts - t, 0, None) + TWAP / 3.0
    r = np.clip(end - t, 0, None)
    a_known = sp.mean(ts, np.maximum(ti, ts + 1))
    mean = np.where(before, st, ((TWAP - r) * a_known + r * st) / TWAP)
    sdu = np.where(before, np.sqrt(var_b), (r / TWAP) * np.sqrt(np.maximum(r, 1e-9) / 3.0))
    return stats.norm.cdf((mean - s0) / (st * sig * sdu))
def load(pattern):
    d = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(C + "calldata/" + pattern))], ignore_index=True)
    tk = d[d.role == "taker"].set_index("tx")
    mk = d[(d.role == "maker") & (d.oside == 0) & d.token_id.isin(info.keys())].copy()
    mk["m"] = mk.tx.map(tk.sign_ms) / 1000.0
    mk["lim"] = mk.maker_amount / mk.taker_amount
    se = np.array([info[t] for t in mk.token_id]); mk["start"], mk["end"] = se[:, 0], se[:, 1]
    mk["isup"] = mk.token_id.isin(up)
    return mk[(mk.m >= mk.start) & (mk.m < mk.end - 1) & (mk.start >= D0 + 120) & (mk.end <= D1)]
for name, pat, sel in (("cluster", "study_*.parquet", lambda d: d[d.maker.isin(W)]), ("others", "pub1026_*.parquet", lambda d: d[~d.maker.isin(W)])):
    g = sel(load(pat))
    line = {"n": len(g)}
    for ref in ("spot", "fut"):
        for k in (-2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2):
            t = g.m.to_numpy() - k
            f = fair(ref, g.start.to_numpy(), g.end.to_numpy(), t)
            fs = np.where(g.isup, f, 1 - f)
            mid = (fs > 0.1) & (fs < 0.9)
            line[f"{ref}{k}"] = round(float(np.corrcoef(g.lim[mid], fs[mid])[0, 1]), 4)
    print(name, line)
