"""B3 at ms resolution (STUDY day 2026-10-26): which Binance time best explains the limit price of filled maker BUY
orders? Fair value (features2 TWAP-60 model) with the ms aggTrades price at match time (taker signing ms) minus k."""
import glob, sys
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, "research/reverse_engineering/directional-maker/code")
from features2 import Spot, TWAP  # noqa
C = ".cache/re/directional-maker/"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
D0, D1 = 1792972800, 1793059200
agg = pd.read_parquet(C + "agg_2026-10-26.parquet", columns=["ms", "px"])
ms, px = agg.ms.to_numpy(), agg.px.to_numpy()
px_at = lambda t: px[np.clip(np.searchsorted(ms, t, side="right") - 1, 0, len(px) - 1)]
s1 = pd.read_parquet(C + "exam/spot_btc_1s.parquet")
sp = Spot(s1.sec.to_numpy(), s1.px.to_numpy())
win = pd.read_parquet(C + "exam/windows_5m.parquet")
up = set(win.up_token)
info = {**{t: (s, e) for t, s, e in zip(win.up_token, win.start_ts, win.end_ts)},
        **{t: (s, e) for t, s, e in zip(win.down_token, win.start_ts, win.end_ts)}}
def fair_ms(start, end, t, st):
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
    mk = mk[(mk.m > D0) & (mk.m < D1)]
    mk["lim"] = mk.maker_amount / mk.taker_amount
    se = np.array([info[t] for t in mk.token_id]); mk["start"], mk["end"] = se[:, 0], se[:, 1]
    mk["isup"] = mk.token_id.isin(up)
    return mk[(mk.m >= mk.start) & (mk.m < mk.end - 1)]
groups = {"cluster": lambda d: d[d.maker.isin(W)], "others": lambda d: d[~d.maker.isin(W)]}
res = {}
for name, pat in (("cluster", "study_*.parquet"), ("others", "pub1026_*.parquet")):
    g = groups[name](load(pat))
    out = {"n": len(g)}
    for k in (-0.5, 0, 0.25, 0.5, 1, 1.5, 2, 3, 5, 10):
        t = g.m.to_numpy() - k
        f = fair_ms(g.start.to_numpy(), g.end.to_numpy(), t, px_at((t * 1000).astype(np.int64)))
        fs = np.where(g.isup, f, 1 - f)
        mid = (fs > 0.1) & (fs < 0.9)
        out[f"k{k}"] = (round(float(np.corrcoef(g.lim[mid], fs[mid])[0, 1]), 4), round(float(np.median(np.abs(g.lim - fs)[mid])), 4))
    res[name] = out
    print(name, out)
