"""Iteration 3, family N4: Binance order-flow features per panel row (bin start t = start_ts + rel), from
seconds <= t-1 (a second is published one second after it ends). Signed features are multiplied by the
side sign (+1 Up, -1 Down).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FLOW = ["ofi1", "ofi3", "ofi5", "ofi10", "ofi30", "ofin5", "ofin30", "ofi_win", "svol5", "svol30", "ntr5", "rng5"]


class Flow:
    def __init__(self, df: pd.DataFrame):
        df = df.sort_values("sec")
        self.t0 = int(df["sec"].iloc[0])
        n = int(df["sec"].iloc[-1]) - self.t0 + 1
        i = df["sec"].to_numpy().astype(np.int64) - self.t0
        vol = np.zeros(n)
        tbv = np.zeros(n)
        ntr = np.zeros(n)
        hi = np.full(n, np.nan)
        lo = np.full(n, np.nan)
        vol[i], tbv[i], ntr[i] = df["vol"].to_numpy(), df["tbv"].to_numpy(), df["ntr"].to_numpy()
        hi[i], lo[i] = df["hi"].to_numpy(), df["lo"].to_numpy()
        self.hi = pd.Series(hi).ffill().to_numpy()
        self.lo = pd.Series(lo).ffill().to_numpy()
        self.c_vol = np.concatenate([[0.0], np.cumsum(vol)])
        self.c_ofi = np.concatenate([[0.0], np.cumsum(2 * tbv - vol)])
        self.c_ntr = np.concatenate([[0.0], np.cumsum(ntr)])
        self.n = n

    def _w(self, c, t, k):
        b = np.clip(t - self.t0, 0, self.n)  # seconds < t  -> indices [.., t-1]
        a = np.clip(t - k - self.t0, 0, self.n)
        return c[b] - c[a]

    def features(self, t: np.ndarray, start: np.ndarray, sign: np.ndarray) -> pd.DataFrame:
        t = np.asarray(t, dtype=np.int64)
        out = {}
        for k in (1, 3, 5, 10, 30):
            out[f"ofi{k}"] = self._w(self.c_ofi, t, k) * sign
        for k in (5, 30):
            v = self._w(self.c_vol, t, k)
            out[f"ofin{k}"] = np.where(v > 0, self._w(self.c_ofi, t, k) / np.maximum(v, 1e-9), 0.0) * sign
        out["ofi_win"] = (self.c_ofi[np.clip(t - self.t0, 0, self.n)] - self.c_ofi[np.clip(np.asarray(start) - self.t0, 0, self.n)]) * sign
        out["svol5"] = self._w(self.c_vol, t, 5)
        out["svol30"] = self._w(self.c_vol, t, 30)
        out["ntr5"] = self._w(self.c_ntr, t, 5)
        idx = np.clip(t - 1 - self.t0, 0, self.n - 1)
        hh = np.max(np.stack([self.hi[np.clip(idx - j, 0, None)] for j in range(5)]), axis=0)
        ll = np.min(np.stack([self.lo[np.clip(idx - j, 0, None)] for j in range(5)]), axis=0)
        out["rng5"] = (hh - ll) / ll * 1e4
        return pd.DataFrame({k: np.asarray(v, dtype=np.float32) for k, v in out.items()})
