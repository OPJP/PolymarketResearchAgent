"""Iteration 3: point-in-time Binance USD-M futures features for every cell (window, outcome, second).

PIT: for the cell at second s only futures trades with T < (s - 1) * 1000 ms are used (the same information time
as the spot kline of second s-2). Directional features are oriented toward the cell's outcome (+ = favourable).
New "faster fair value": futures price rescaled by the pre-window basis (spot 60-s TWAP strike / futures 60-s TWAP),
z and fv as in cells.py but from futures; gaps vs the last implied ask / last price.
Writes .cache/re/btc5m-bot/cells_fut/<day0>.parquet (same row order as cells/<day0>.parquet).
Usage: python fut_cells.py            (all days that have a cells file and a futures file)"""
import os, sys, glob
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import numpy as np, pandas as pd
from scipy.special import ndtr
from ofi import Agg, OFI_FEATS
C = _ROOT + "/.cache/re/btc5m-bot"
FUT_FEATS = (["F_" + k for k in OFI_FEATS] + ["F_basis3", "F_since", "F_z", "F_fv", "F_dz", "F_gap_ask", "F_gap_m"])
DIRECTIONAL = [k for k in OFI_FEATS if k.startswith(("ofi", "ofin", "pm"))]


class FutPx:
    """last-trade log price strictly before t (ms)."""
    def __init__(self, a: Agg):
        self.a = a

    def lp(self, t_ms):
        i = np.searchsorted(self.a.T, np.asarray(t_ms, np.int64), side="left") - 1
        return np.where(i >= 0, self.a.lp[np.clip(i, 0, None)], np.nan)


def spot_strike(start_ts: np.ndarray, spot: pd.DataFrame) -> np.ndarray:
    """mean Binance 1-s close over [start-60, start) (the TWAP strike of cells.py)."""
    sec = spot.sec.to_numpy(np.int64); px = spot.close.to_numpy(float)
    cs = np.r_[0.0, np.cumsum(px)]
    i0 = np.searchsorted(sec, start_ts - 60); i1 = np.searchsorted(sec, start_ts)
    return (cs[i1] - cs[i0]) / np.maximum(i1 - i0, 1)


def fut_feats(c: pd.DataFrame, agg: Agg, spot: pd.DataFrame) -> pd.DataFrame:
    """c needs: start_ts, rel, is_up, age_last, ask_o, m_last, sig, tau, r3, z."""
    s = (c.start_ts.to_numpy(np.int64) + c.rel.to_numpy(np.int64))
    sg = np.where(c.is_up.to_numpy(), 1.0, -1.0)
    t_end = (s - 1) * 1000
    f = agg.feats(t_end)
    out = {}
    for k in OFI_FEATS:
        v = np.asarray(f[k], float)
        out["F_" + k] = (sg * v if k in DIRECTIONAL else v).astype(np.float32)
    out["F_basis3"] = (out["F_pm3000"] - c.r3.to_numpy()).astype(np.float32)
    fp = FutPx(agg)
    lp_now = fp.lp(t_end)
    age = c.age_last.to_numpy(float)
    t_last = np.where(np.isfinite(age), (s - np.nan_to_num(age, nan=0.0) - 1) * 1000, np.nan)
    lp_last = np.where(np.isfinite(t_last), fp.lp(np.nan_to_num(t_last, nan=0).astype(np.int64)), np.nan)
    out["F_since"] = (sg * (lp_now - lp_last) * 1e4).astype(np.float32)
    # futures fair value: pre-window basis-adjusted futures price vs the spot TWAP strike
    st = c.start_ts.to_numpy(np.int64)
    ust, inv = np.unique(st, return_inverse=True)
    grid = ust[:, None] - 60 + np.arange(60)[None, :]           # seconds start-60 .. start-1
    lpf = fp.lp(((grid + 1) * 1000).ravel()).reshape(grid.shape)  # last futures trade before the end of each second
    kf = np.log(np.nanmean(np.exp(lpf), axis=1))
    ks = np.log(spot_strike(ust, spot))
    sigma = c.sig.to_numpy(float) / 1e5
    tau = np.maximum(c.tau.to_numpy(float), 1.0)
    zf_up = (lp_now - kf[inv]) / (sigma * np.sqrt(tau))          # = ln(F_adj / K_spot) / (sig sqrt(tau)), F_adj = F * K_spot/K_fut
    zf_up = np.where(c.rel.to_numpy() >= 1, zf_up, np.nan)
    out["F_z"] = (sg * zf_up).astype(np.float32)
    out["F_fv"] = ndtr(out["F_z"].astype(float)).astype(np.float32)
    out["F_dz"] = (out["F_z"] - c.z.to_numpy()).astype(np.float32)
    out["F_gap_ask"] = (out["F_fv"] - c.ask_o.to_numpy()).astype(np.float32)
    out["F_gap_m"] = (out["F_fv"] - c.m_last.to_numpy()).astype(np.float32)
    _ = ks  # strike in spot terms (kept for clarity; z uses the basis-adjusted futures level)
    return pd.DataFrame(out)


def load_agg(day0: int, fut_dir: str) -> Agg:
    parts = [pd.read_parquet(f"{fut_dir}/{d}.parquet") for d in (day0 - 86400, day0) if os.path.exists(f"{fut_dir}/{d}.parquet")]
    return Agg(pd.concat(parts, ignore_index=True))


if __name__ == "__main__":
    os.makedirs(f"{C}/cells_fut", exist_ok=True)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    for fp_ in sorted(glob.glob(f"{C}/cells/*.parquet")):
        d0 = int(os.path.basename(fp_)[:-8])
        out = f"{C}/cells_fut/{d0}.parquet"
        if os.path.exists(out) or not os.path.exists(f"{C}/fut/{d0}.parquet"):
            continue
        c = pd.read_parquet(fp_, columns=["start_ts", "rel", "is_up", "age_last", "ask_o", "m_last", "sig", "tau", "r3", "z"])
        F = fut_feats(c, load_agg(d0, f"{C}/fut"), spot)
        F.to_parquet(out, index=False)
        print(d0, len(F), "nan F_z", round(float(np.isnan(F.F_z).mean()), 3), "nan F_pm1000", round(float(np.isnan(F.F_pm1000).mean()), 3), flush=True)
