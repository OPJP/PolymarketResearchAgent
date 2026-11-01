"""Iteration 3: point-in-time features from other perpetual venues (OKX BTC-USDT-SWAP, Bybit BTCUSDT) and a
three-venue composite (Binance USD-M futures, OKX, Bybit) for every cell. PIT: trades with T < (s - 1) * 1000 ms only.
Directional features are oriented toward the cell's outcome. Cells outside a venue's archive coverage get NaN.
Writes .cache/re/btc5m-bot/cells_ven/<day0>.parquet (same row order as cells/<day0>.parquet).
Usage: python venue_cells.py"""
import os, sys, glob
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import numpy as np, pandas as pd
from ofi import Agg
C = _ROOT + "/.cache/re/btc5m-bot"
VENUES = ("okx", "bybit")
VWIN = (500, 1000, 2000, 3000, 5000, 10000)
VEN_FEATS = [f"{v}_{k}" for v in ("O", "B") for k in [f"pm{w}" for w in VWIN] + ["ofin1000", "ofin3000", "age_tr", "ntr1000"]] + \
            [f"C_pm{w}" for w in (1000, 2000, 3000, 5000)] + [f"C_mx{w}" for w in (1000, 2000, 3000)]


def venue_frame(venue: str, day0: int, ven_dir: str):
    """trades covering UTC day day0 (OKX daily files are UTC+8 days: use the files of day0-1 .. day0+1)."""
    parts = [pd.read_parquet(f"{ven_dir}/{venue}/{d}.parquet") for d in (day0 - 86400, day0, day0 + 86400) if os.path.exists(f"{ven_dir}/{venue}/{d}.parquet")]
    if not parts:
        return None
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def feats_for(agg: Agg, t_end: np.ndarray, sg: np.ndarray, prefix: str) -> dict:
    f = agg.feats(t_end)
    cov = (t_end - 15000 >= agg.T[0]) & (t_end <= agg.T[-1])
    out = {}
    for w in VWIN:
        out[f"{prefix}_pm{w}"] = np.where(cov, sg * f[f"pm{w}"], np.nan).astype(np.float32)
    for k in ("ofin1000", "ofin3000"):
        out[f"{prefix}_{k}"] = np.where(cov, sg * f[k], np.nan).astype(np.float32)
    for k in ("age_tr", "ntr1000"):
        out[f"{prefix}_{k}"] = np.where(cov, f[k], np.nan).astype(np.float32)
    return out


def ven_feats(c: pd.DataFrame, aggs: dict, fut_pm: dict) -> pd.DataFrame:
    """c needs start_ts, rel, is_up; aggs = {'O': Agg|None, 'B': Agg|None}; fut_pm = oriented Binance futures moves
    {1000: arr, 2000: arr, 3000: arr, 5000: arr} (from fut_cells, same rows)."""
    s = c.start_ts.to_numpy(np.int64) + c.rel.to_numpy(np.int64)
    sg = np.where(c.is_up.to_numpy(), 1.0, -1.0)
    t_end = (s - 1) * 1000
    out = {}
    for p, a in aggs.items():
        if a is None:
            for k in [f"{p}_{x}" for x in [f"pm{w}" for w in VWIN] + ["ofin1000", "ofin3000", "age_tr", "ntr1000"]]:
                out[k] = np.full(len(c), np.nan, np.float32)
        else:
            out.update(feats_for(a, t_end, sg, p))
    for w in (1000, 2000, 3000, 5000):
        st = np.stack([fut_pm[w], out[f"O_pm{w}"], out[f"B_pm{w}"]], axis=1).astype(float)
        out[f"C_pm{w}"] = np.nanmean(st, axis=1).astype(np.float32)
        if w <= 3000:
            ab = np.where(np.isfinite(st), np.abs(st), -1.0); j = ab.argmax(1)
            out[f"C_mx{w}"] = st[np.arange(len(st)), j].astype(np.float32)
    return pd.DataFrame(out)


if __name__ == "__main__":
    os.makedirs(f"{C}/cells_ven", exist_ok=True)
    for fp_ in sorted(glob.glob(f"{C}/cells/*.parquet")):
        d0 = int(os.path.basename(fp_)[:-8])
        out = f"{C}/cells_ven/{d0}.parquet"
        if os.path.exists(out) or not os.path.exists(f"{C}/cells_fut/{d0}.parquet"):
            continue
        c = pd.read_parquet(fp_, columns=["start_ts", "rel", "is_up"])
        F = pd.read_parquet(f"{C}/cells_fut/{d0}.parquet", columns=[f"F_pm{w}" for w in (1000, 2000, 3000, 5000)])
        aggs = {}
        for p, v in (("O", "okx"), ("B", "bybit")):
            vf = venue_frame(v, d0, f"{C}/venues")
            aggs[p] = Agg(vf) if vf is not None else None
        Vf = ven_feats(c, aggs, {w: F[f"F_pm{w}"].to_numpy() for w in (1000, 2000, 3000, 5000)})
        Vf.to_parquet(out, index=False)
        print(d0, len(Vf), "nan O", round(float(np.isnan(Vf.O_pm1000).mean()), 3), "nan B", round(float(np.isnan(Vf.B_pm1000).mean()), 3), flush=True)
