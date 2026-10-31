"""Point-in-time features per (BTC 5m window, side, 10-s bin) and the cluster's
maker-fill label. Every feature at bin start t uses only data published <= t:
Binance 1-s closes are available one second after the second ends (so the
last usable second is t-1), taker prints with timestamp < t.

Output: .cache/re/directional-maker/panel5_<lo>_<hi>.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker"
H = 1792713600
BIN = 10
REL_LO, REL_HI = -120, 300  # bins covered, relative to window start
TWAP = 60


class Spot:
    def __init__(self, sec: np.ndarray, px: np.ndarray):
        # dense per-second array (forward-filled) from sec[0]
        self.t0 = int(sec[0])
        n = int(sec[-1]) - self.t0 + 1
        arr = np.full(n, np.nan)
        arr[sec.astype(np.int64) - self.t0] = px
        self.px = pd.Series(arr).ffill().to_numpy()
        self.cum = np.concatenate([[0.0], np.cumsum(self.px - self.px[0])])
        lr = np.diff(np.log(self.px), prepend=np.log(self.px[0]))
        self.cr2 = np.concatenate([[0.0], np.cumsum(lr ** 2)])

    def last(self, t):
        """price of the last second fully published at t (second t-1 closes at t)."""
        i = np.asarray(t, dtype=np.int64) - 1 - self.t0
        return self.px[np.clip(i, 0, len(self.px) - 1)]

    def mean(self, a, b):
        """mean of per-second closes for seconds in [a, b)."""
        ia = np.clip(np.asarray(a, dtype=np.int64) - self.t0, 0, len(self.px))
        ib = np.clip(np.asarray(b, dtype=np.int64) - self.t0, 0, len(self.px))
        n = np.maximum(ib - ia, 1)
        return (self.cum[ib] - self.cum[ia]) / n + self.px[0]

    def sigma(self, t, look=1800):
        ib = np.clip(np.asarray(t, dtype=np.int64) - self.t0, 0, len(self.px))
        ia = np.clip(ib - look, 0, len(self.px))
        return np.sqrt(np.maximum((self.cr2[ib] - self.cr2[ia]) / np.maximum(ib - ia, 1), 1e-12))


def fair_up(sp: Spot, start, end, t):
    """P(TWAP_60(end) >= TWAP_60(start)) with spot published by t (Binance proxy for Chainlink)."""
    start, end, t = (np.asarray(x, dtype=np.int64) for x in (start, end, t))
    known = np.minimum(t, start)  # strike TWAP over [start-60, start) uses seconds published by t
    s0 = np.where(t >= start, sp.mean(start - TWAP, start), np.nan)
    st = sp.last(t)
    sig = sp.sigma(t)
    ts = end - TWAP
    before = t < ts
    var_b = np.clip(ts - t, 0, None) + TWAP / 3.0
    r = np.clip(end - t, 0, None).astype(float)
    a_known = sp.mean(ts, np.maximum(t, ts + 1))
    mean_in = ((TWAP - r) * a_known + r * st) / TWAP
    sd_in = (r / TWAP) * np.sqrt(np.maximum(r, 1e-9) / 3.0)
    mean = np.where(before, st, mean_in)
    sdu = np.where(before, np.sqrt(var_b), sd_in)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (mean - s0) / (st * sig * sdu)
    p = stats.norm.cdf(z)
    return np.where(t < start, 0.5, p), np.where(t < start, 0.0, np.log(st / s0)) / np.maximum(sig, 1e-9)


def build(lo: int, hi: int) -> pd.DataFrame:
    hi = min(hi, H)  # development guard: never past H
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[(w["start_ts"] >= lo) & (w["end_ts"] <= hi)].reset_index(drop=True)
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[spd["sec"] < hi]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    tk = pd.read_parquet(OUT / f"taker_5m_{lo}_{hi}.parquet")
    tk = tk[tk["cid"].isin(set(w["cid"])) & (tk["ts"] < hi)]
    mk = pd.read_parquet(OUT / "fills_enriched.parquet")
    mk = mk[(mk["role"] == "maker") & (mk["side"] == "BUY") & (mk["ts"] < hi)]
    return build_panel(w, sp, tk, mk)


def build_panel(w: pd.DataFrame, sp: "Spot", tk: pd.DataFrame, mk: pd.DataFrame) -> pd.DataFrame:
    """w: windows (cid, start_ts, end_ts, up_token, down_token, up_payout); sp: Spot; tk: taker tape rows
    (cid, ts, side, asset, price, size); mk: cluster maker BUY fills (token_id, ts, shares). Labels come from mk only."""
    w = w[w["cid"].isin(set(tk["cid"]))].reset_index(drop=True)  # windows whose tape is available
    groups = {c: g for c, g in tk.groupby("cid")}
    rows = []
    rel = np.arange(REL_LO, REL_HI, BIN)
    for wi, win in enumerate(w.itertuples(index=False)):
        t = win.start_ts + rel
        fu, zsc = fair_up(sp, np.full(len(t), win.start_ts), np.full(len(t), win.end_ts), t)
        base = {"cid": win.cid, "start_ts": win.start_ts, "rel": rel, "t": t, "fair_up": fu, "z_up": zsc,
                "sig": sp.sigma(t) * 1e4, "up_payout": win.up_payout}
        st = sp.last(t)
        rets = {f"r{k}": np.log(st / sp.last(t - k)) * 1e4 for k in (1, 2, 3, 5, 10, 30, 60)}
        # tape: prints before t
        tw = groups[win.cid]
        tts = tw["ts"].to_numpy()
        is_up = (tw["asset"].to_numpy() == win.up_token)
        buy = tw["side"].to_numpy() == "BUY"
        pr = tw["price"].to_numpy()
        up_px = np.where(is_up, pr, 1 - pr)  # implied Up price of each print
        sz = tw["size"].to_numpy()
        # hits on Up bids: taker SELL Up or taker BUY Down ; hits on Down bids: taker SELL Down or taker BUY Up
        hit_up = (is_up & ~buy) | (~is_up & buy)
        order = np.argsort(tts, kind="stable")
        tts, up_px, hit_up, sz = tts[order], up_px[order], hit_up[order], sz[order]
        idx = np.searchsorted(tts, t, side="left")  # prints strictly before t
        last_up = np.where(idx > 0, up_px[np.clip(idx - 1, 0, None)], np.nan)
        cnt = np.arange(1, len(tts) + 1)
        c_hu = np.concatenate([[0], np.cumsum(hit_up)])
        c_hd = np.concatenate([[0], np.cumsum(~hit_up)])
        c_vu = np.concatenate([[0], np.cumsum(sz * hit_up)])
        c_vd = np.concatenate([[0], np.cumsum(sz * ~hit_up)])
        feats = {"last_up": last_up, "n_prints": idx}
        # book proxies from the tape: last implied Up bid (a bid-hit on Up) and last implied Up ask (an ask-lift on Up)
        ih = np.flatnonzero(hit_up)
        il = np.flatnonzero(~hit_up)
        jb = np.searchsorted(tts[ih], t, side="left") - 1
        jl = np.searchsorted(tts[il], t, side="left") - 1
        lb_up = np.where(jb >= 0, up_px[ih][np.clip(jb, 0, None)] if len(ih) else np.nan, np.nan)
        la_up = np.where(jl >= 0, up_px[il][np.clip(jl, 0, None)] if len(il) else np.nan, np.nan)
        age_b = np.where(jb >= 0, t - (tts[ih][np.clip(jb, 0, None)] if len(ih) else 0), 9999)
        age_l = np.where(jl >= 0, t - (tts[il][np.clip(jl, 0, None)] if len(il) else 0), 9999)
        age_any = np.where(idx > 0, t - tts[np.clip(idx - 1, 0, None)] if len(tts) else 9999, 9999)
        for k in (10, 30, 60):
            j = np.searchsorted(tts, t - k, side="left")
            feats[f"hu{k}"] = c_hu[idx] - c_hu[j]
            feats[f"hd{k}"] = c_hd[idx] - c_hd[j]
            feats[f"vu{k}"] = c_vu[idx] - c_vu[j]
            feats[f"vd{k}"] = c_vd[idx] - c_vd[j]
            # tape price change over k
            pj = np.where(j > 0, up_px[np.clip(j - 1, 0, None)], np.nan)
            feats[f"dpx{k}"] = last_up - pj
        # label: cluster maker BUY fills per side in [t, t+BIN)
        mw = mk[(mk["token_id"] == win.up_token) | (mk["token_id"] == win.down_token)]
        lab = {}
        for side, tokn in (("up", win.up_token), ("down", win.down_token)):
            ms = mw[mw["token_id"] == tokn]
            b = ((ms["ts"].to_numpy() - win.start_ts - REL_LO) // BIN).astype(int)
            b = b[(b >= 0) & (b < len(rel))]
            cntb = np.bincount(b, minlength=len(rel))
            lab[side] = cntb
            shb = np.bincount(((ms["ts"].to_numpy() - win.start_ts - REL_LO) // BIN).clip(0, len(rel) - 1).astype(int),
                              weights=ms["shares"].to_numpy(), minlength=len(rel)) if len(ms) else np.zeros(len(rel))
            lab[side + "_sh"] = shb
        for side in ("up", "down"):
            sgn = 1 if side == "up" else -1
            d = dict(base)
            d.update({k: v * sgn for k, v in rets.items()})
            d["side_up"] = 1 if side == "up" else 0
            d["fair_s"] = fu if side == "up" else 1 - fu
            d["z_s"] = zsc * sgn
            d["last_s"] = last_up if side == "up" else 1 - last_up
            d["edge_s"] = d["fair_s"] - d["last_s"]
            # side s: its bid-hits are Up bid-hits for Up, Up ask-lifts (=Down bid-hits) for Down
            d["lb_s"] = lb_up if side == "up" else 1 - la_up
            d["la_s"] = la_up if side == "up" else 1 - lb_up
            d["age_lb_s"] = age_b if side == "up" else age_l
            d["age_la_s"] = age_l if side == "up" else age_b
            d["age_any"] = age_any
            d["edge_lb_s"] = d["fair_s"] - d["lb_s"]
            d["edge_la_s"] = d["fair_s"] - d["la_s"]
            d["n_prints"] = feats["n_prints"]
            for k in (10, 30, 60):
                d[f"hit_s{k}"] = feats[f"hu{k}"] if side == "up" else feats[f"hd{k}"]
                d[f"hit_o{k}"] = feats[f"hd{k}"] if side == "up" else feats[f"hu{k}"]
                d[f"vol_s{k}"] = feats[f"vu{k}"] if side == "up" else feats[f"vd{k}"]
                d[f"vol_o{k}"] = feats[f"vd{k}"] if side == "up" else feats[f"vu{k}"]
                d[f"dpx_s{k}"] = feats[f"dpx{k}"] * sgn
            d["y"] = (lab[side] > 0).astype(int)
            d["y_n"] = lab[side]
            d["y_sh"] = lab[side + "_sh"]
            d["won_s"] = (win.up_payout if side == "up" else 1 - win.up_payout) if win.up_payout is not None else np.nan
            rows.append(pd.DataFrame(d))
        if wi % 500 == 0:
            print("windows", wi, flush=True)
    return pd.concat(rows, ignore_index=True)


if __name__ == "__main__":
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    p = build(lo, hi)
    p.to_parquet(OUT / f"panel5_{lo}_{hi}.parquet", index=False)
    print("panel", p.shape, "pos rate", round(p["y"].mean(), 4))
