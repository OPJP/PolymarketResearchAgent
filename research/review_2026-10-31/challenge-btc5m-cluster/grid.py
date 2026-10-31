"""Per-window, per-second point-in-time state used to compute features at arbitrary (window, time) queries.

State at second t uses only prints with block timestamp <= t and Kraken seconds available by t.
"""
import numpy as np, pandas as pd, sys
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.pit import TimeSeries
from polyrea.analysis.updown import SpotIndex

CLS = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
PRE = 180


class Grid:
    def __init__(self, t):
        self.wins = {w.condition_id: w for w in t["windows"]}
        self.by_start = {w.start_ts: w.condition_id for w in t["windows"]}
        self.spot = SpotIndex(TimeSeries.build("spot", zip(t["spot_ev"].tolist(), t["spot_vals"].tolist()), availability_lag=1))
        if "grid_g" in t:
            self.g = t["grid_g"]
            return
        self.g = {}
        for cid, w in self.wins.items():
            taker = t["tapes"].get(cid, [])
            full = t["full_tapes"].get(cid, [])
            cl_tx = {r["transactionHash"] for r in full if (r.get("proxyWallet") or "").lower() in CLS}
            secs = np.arange(w.start_ts - PRE, w.end_ts + 1)
            rows = sorted((int(r["timestamp"]), r["asset"] == w.up_token, r["side"], float(r["size"]), float(r["price"]), r["transactionHash"] in cl_tx) for r in taker if r["asset"] in (w.up_token, w.down_token))
            ts = np.array([x[0] for x in rows], dtype=np.int64)
            upx = np.array([x[4] if x[1] else 1 - x[4] for x in rows])
            sgn = np.array([(1 if x[1] else -1) * (1 if x[2] == "BUY" else -1) * x[3] * x[4] * (0 if x[5] else 1) for x in rows])
            cum = np.cumsum(sgn) if len(sgn) else np.zeros(0)
            k = np.searchsorted(ts, secs, side="right") - 1
            up_last = np.where(k >= 0, upx[np.clip(k, 0, None)] if len(upx) else 0.5, 0.5)
            cflow = np.where(k >= 0, cum[np.clip(k, 0, None)] if len(cum) else 0.0, 0.0)
            sp = self.spot.price_at(secs)
            self.g[cid] = (w.start_ts - PRE, up_last, cflow, sp)

    def feats(self, cid, t, is_up, gap=2, shift_windows=0):
        """Dynamic features oriented to the bought side, for queries in one window (vectorized over t)."""
        w = self.wins[cid]
        if shift_windows:
            c2 = self.by_start.get(w.start_ts + 300 * shift_windows)
            if c2 is None:
                return None
            cid, t = c2, t + 300 * shift_windows
        base, up_last, cflow, sp = self.g[cid]
        side = np.where(is_up, 1.0, -1.0)
        i0 = np.clip(t - gap - base, 0, len(up_last) - 1)
        out = {}
        for k in (5, 20, 60):
            ik = np.clip(i0 - k, 0, None)
            out[f"dside_{k}"] = side * (up_last[i0] - up_last[ik])
            out[f"fx_{k}"] = side * (cflow[i0] - cflow[ik])
        for k in (2, 10, 30):
            ik = np.clip(i0 - k, 0, None)
            out[f"sside_{k}"] = side * np.log(sp[i0] / sp[ik])
        out["up_last_side"] = np.where(is_up, up_last[i0], 1 - up_last[i0])
        return out

DYN = ["dside_5", "dside_20", "dside_60", "fx_5", "fx_20", "fx_60", "sside_2", "sside_10", "sside_30"]
