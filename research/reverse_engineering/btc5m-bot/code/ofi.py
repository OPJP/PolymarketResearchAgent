"""Iteration 2: Binance spot aggTrades features (order-flow imbalance, ms-resolution price moves).
PIT: for a cell at second s only trades with T < (s - 1) * 1000 ms are used (the same information horizon as the
1-s kline of second s-2, which is usable from s). Orientation: toward Up (callers flip the sign for Down)."""
import os, glob
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
AGG = _ROOT + "/.cache/re/btc5m-bot/aggtrades"
WINS_MS = (250, 500, 1000, 2000, 3000, 5000, 10000)
OFI_FEATS = [f"ofi{w}" for w in WINS_MS] + [f"ofin{w}" for w in WINS_MS] + [f"pm{w}" for w in WINS_MS] + ["ntr1000", "age_tr"]


def load_hours():
    fs = sorted(glob.glob(f"{AGG}/*.parquet"))
    return {int(os.path.basename(f)[:-8]): f for f in fs}


class Agg:
    def __init__(self, df):
        df = df.sort_values("T", kind="stable")
        self.T = df["T"].to_numpy(np.int64); self.p = df.p.to_numpy(np.float64)
        sv = np.where(df.m.to_numpy(), -1.0, 1.0) * df.q.to_numpy(np.float64)  # + = buy-initiated
        self.cs = np.r_[0.0, np.cumsum(sv)]; self.cv = np.r_[0.0, np.cumsum(df.q.to_numpy(np.float64))]
        self.lp = np.log(self.p)

    def feats(self, t_end_ms):
        """features over windows ending at t_end_ms (exclusive); arrays toward Up."""
        t_end_ms = np.asarray(t_end_ms, np.int64)
        i1 = np.searchsorted(self.T, t_end_ms, side="left")  # trades strictly before t_end
        out = {}
        last = np.clip(i1 - 1, 0, None)
        out["age_tr"] = (t_end_ms - self.T[last]) / 1000.0
        for w in WINS_MS:
            i0 = np.searchsorted(self.T, t_end_ms - w, side="left")
            sv = self.cs[i1] - self.cs[i0]; vv = self.cv[i1] - self.cv[i0]
            out[f"ofi{w}"] = sv
            with np.errstate(invalid="ignore", divide="ignore"):
                out[f"ofin{w}"] = np.where(vv > 0, sv / vv, 0.0)
            prev = np.clip(i0 - 1, 0, None)
            out[f"pm{w}"] = (self.lp[last] - self.lp[prev]) * 1e4
            if w == 1000:
                out["ntr1000"] = (i1 - i0).astype(float)
        return out


def add_ofi(df, sec_col="s", lag_s=1.0, prefix=""):
    """Adds OFI features (toward Up) for rows with integer second `sec_col`, horizon end = (s - lag_s) seconds.
    Rows whose hour has no aggTrades file get NaN."""
    hours = load_hours()
    s = df[sec_col].to_numpy(np.int64)
    res = {k: np.full(len(df), np.nan) for k in OFI_FEATS}
    hr = (s - 12) // 3600 * 3600  # hour of the horizon (windows up to 10 s back stay inside the hour except at its start)
    for h0 in np.unique(hr):
        if h0 not in hours:
            continue
        m = (hr == h0) & ((s - 1) // 3600 * 3600 == h0)  # whole look-back inside one sampled hour
        a = Agg(pd.read_parquet(hours[h0]))
        f = a.feats(((s[m] - lag_s) * 1000).astype(np.int64))
        for k in OFI_FEATS:
            res[k][m] = f[k]
    for k in OFI_FEATS:
        df[prefix + k] = res[k].astype(np.float32)
    return df
