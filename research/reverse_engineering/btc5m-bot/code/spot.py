"""Dense per-second Binance close array + point-in-time fair value helpers.
px(s) = close of kline [s, s+1). Under the brief's rule it is usable from s+2 on."""
import numpy as np, pandas as pd
from scipy.special import ndtr
C = "/home/user/PolymarketResearchAgent/.cache/re/btc5m-bot"


class Spot:
    def __init__(self, path=f"{C}/binance_1s.parquet", frame=None):
        s = pd.read_parquet(path) if frame is None else frame
        self.s0 = int(s.sec.min()); n = int(s.sec.max()) - self.s0 + 1
        px = np.full(n, np.nan); px[s.sec.to_numpy() - self.s0] = s.close.to_numpy()
        px = pd.Series(px).ffill().to_numpy()
        self.px = px
        lr = np.diff(np.log(px), prepend=np.log(px[0]))
        self.cr2 = np.cumsum(lr ** 2)
        self.cpx = np.cumsum(px - px[0])

    def at(self, sec):
        """close of second sec (caller is responsible for the availability lag)."""
        return self.px[np.asarray(sec, dtype=np.int64) - self.s0]

    def sigma(self, sec, lookback=1800):
        i = np.asarray(sec, dtype=np.int64) - self.s0
        return np.sqrt(np.maximum((self.cr2[i] - self.cr2[i - lookback]) / lookback, 1e-14))

    def mean(self, a, b):
        """mean close over seconds [a, b)."""
        a = np.asarray(a, dtype=np.int64) - self.s0; b = np.asarray(b, dtype=np.int64) - self.s0
        return (self.cpx[b - 1] - self.cpx[a - 1]) / (b - a) + self.px[0]

    def fair_up(self, start, end, last_sec, strike="twap", sig_lb=1800):
        """P(Up) using spot up to second last_sec (inclusive). strike: 'twap' = mean over [start-60,start), 'open' = close of start-1."""
        start = np.asarray(start); end = np.asarray(end); last_sec = np.asarray(last_sec)
        if strike == "twap":
            K = self.mean(start - 60, start)
        else:
            K = self.at(start - 1)
        St = self.at(last_sec)
        sig = self.sigma(last_sec, sig_lb)
        tau = np.maximum(end - (last_sec + 1), 1).astype(float)
        z = np.log(St / K) / (sig * np.sqrt(tau))
        return ndtr(z), z
