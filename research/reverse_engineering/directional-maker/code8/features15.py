"""Iteration 8 (A1 / X69): features2 generalised to BTC 15m windows (bins [0, 900) s; the previous-window proxy
outcome and print count use the previous 15-min window). Otherwise identical to code/features2.py (iteration 2).

Original docstring: point-in-time panel per (BTC 5m window, side, 10-s bin in [0, 300) s).

Changes vs iteration 1 (features.py):
* LEAK FIX: every taker print in a transaction where any cluster wallet traded (as maker or taker)
  is removed from the tape before any feature is computed (brief: "the wallet's own prints, and
  prints in transactions where it was the maker, are never part of any feature"). Iteration 1
  counted those prints (hit_s10 etc. partly counted the cluster's own fills).
* new public path features (window-level side commitment): edge at the first clean print of the
  window, running max / mean / share-positive of the side's edge over the bins so far, fair and z
  at rel = 10 s;
* new cross-window features: Binance-TWAP proxy outcome of the previous window (known at the start),
  |strike move| between consecutive windows, clean print count of the previous window;
* taker-identity features: distinct taker wallets and large prints in the last 60 s (clean tape).
Own-state (reported separately, never in the primary model): cluster shares bought on s / other side
before t in this window.

Every feature at bin start t uses data published <= t: Binance second k is usable from k+1, taker
prints with timestamp < t.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

BIN = 10
WIN = 900
REL = np.arange(0, WIN, BIN)
TWAP = 60


class Spot:
    def __init__(self, sec: np.ndarray, px: np.ndarray):
        self.t0 = int(sec[0])
        n = int(sec[-1]) - self.t0 + 1
        arr = np.full(n, np.nan)
        arr[sec.astype(np.int64) - self.t0] = px
        self.px = pd.Series(arr).ffill().to_numpy()
        self.cum = np.concatenate([[0.0], np.cumsum(self.px - self.px[0])])
        lr = np.diff(np.log(self.px), prepend=np.log(self.px[0]))
        self.cr2 = np.concatenate([[0.0], np.cumsum(lr ** 2)])

    def last(self, t):
        i = np.asarray(t, dtype=np.int64) - 1 - self.t0
        return self.px[np.clip(i, 0, len(self.px) - 1)]

    def mean(self, a, b):
        ia = np.clip(np.asarray(a, dtype=np.int64) - self.t0, 0, len(self.px))
        ib = np.clip(np.asarray(b, dtype=np.int64) - self.t0, 0, len(self.px))
        n = np.maximum(ib - ia, 1)
        return (self.cum[ib] - self.cum[ia]) / n + self.px[0]

    def sigma(self, t, look=1800):
        ib = np.clip(np.asarray(t, dtype=np.int64) - self.t0, 0, len(self.px))
        ia = np.clip(ib - look, 0, len(self.px))
        return np.sqrt(np.maximum((self.cr2[ib] - self.cr2[ia]) / np.maximum(ib - ia, 1), 1e-12))


def fair_up(sp: Spot, start, end, t):
    """P(TWAP_60(end) >= TWAP_60(start)) from Binance seconds published by t (t >= start)."""
    start, end, t = (np.asarray(x, dtype=np.int64) for x in (start, end, t))
    s0 = sp.mean(start - TWAP, start)
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
    return stats.norm.cdf(z), np.log(st / s0) / np.maximum(sig, 1e-9)


def clean_tape(tk: pd.DataFrame, cluster_tx: set, cluster_wallets: set) -> pd.DataFrame:
    bad = tk["tx"].isin(cluster_tx) | tk["wallet"].isin(cluster_wallets)
    return tk[~bad]


def build_panel(w: pd.DataFrame, sp: Spot, tk: pd.DataFrame, mk: pd.DataFrame) -> pd.DataFrame:
    """w: windows sorted by start (cid, start_ts, end_ts, up_token, down_token, up_payout); tk: CLEAN taker tape
    (cid, ts, side, asset, price, size, wallet); mk: cluster maker BUY fills (token_id, ts, shares) for labels and
    own-state only."""
    w = w.sort_values("start_ts").reset_index(drop=True)
    groups = {c: g for c, g in tk.groupby("cid", sort=False)}
    mk_by_tok = {t: g for t, g in mk.groupby("token_id", sort=False)}
    prev_n = {}
    out = []
    for win in w.itertuples(index=False):
        t = win.start_ts + REL
        n = len(t)
        fu, zsc = fair_up(sp, np.full(n, win.start_ts), np.full(n, win.end_ts), t)
        st = sp.last(t)
        rets = {f"r{k}": (np.log(st / sp.last(t - k)) * 1e4).astype(np.float32) for k in (1, 2, 3, 5, 10, 30, 60)}
        sig = sp.sigma(t) * 1e4
        # previous-window proxy outcome (Binance TWAP of [start-60,start) vs TWAP of [start-360,start-300)), known at start
        s_cur = sp.mean(win.start_ts - TWAP, win.start_ts)
        s_prev = sp.mean(win.start_ts - WIN - TWAP, win.start_ts - WIN)
        prev_up = 1.0 if s_cur >= s_prev else 0.0
        strike_move = float(np.log(s_cur / s_prev) / max(sp.sigma(win.start_ts) * np.sqrt(WIN), 1e-9))
        g = groups.get(win.cid)
        if g is None or len(g) == 0:
            g = pd.DataFrame({"ts": np.array([], dtype=np.int64), "asset": [], "side": [], "price": [], "size": [], "wallet": []})
        tts = g["ts"].to_numpy().astype(np.int64)
        order = np.argsort(tts, kind="stable")
        tts = tts[order]
        is_up = (g["asset"].to_numpy() == win.up_token)[order]
        buy = (g["side"].astype(str).to_numpy() == "BUY")[order]
        pr = g["price"].to_numpy().astype(float)[order]
        up_px = np.where(is_up, pr, 1 - pr)
        sz = g["size"].to_numpy().astype(float)[order]
        wal = g["wallet"].to_numpy()[order]
        hit_up = (is_up & ~buy) | (~is_up & buy)
        idx = np.searchsorted(tts, t, side="left")
        last_up = np.where(idx > 0, up_px[np.clip(idx - 1, 0, None)] if len(tts) else np.nan, np.nan)
        c_hu = np.concatenate([[0], np.cumsum(hit_up)])
        c_hd = np.concatenate([[0], np.cumsum(~hit_up)])
        c_vu = np.concatenate([[0], np.cumsum(sz * hit_up)])
        c_vd = np.concatenate([[0], np.cumsum(sz * ~hit_up)])
        c_big = np.concatenate([[0], np.cumsum(sz >= 200)])
        feats = {}
        for k in (10, 30, 60):
            j = np.searchsorted(tts, t - k, side="left")
            feats[f"hu{k}"], feats[f"hd{k}"] = c_hu[idx] - c_hu[j], c_hd[idx] - c_hd[j]
            feats[f"vu{k}"], feats[f"vd{k}"] = c_vu[idx] - c_vu[j], c_vd[idx] - c_vd[j]
            pj = np.where(j > 0, up_px[np.clip(j - 1, 0, None)] if len(tts) else np.nan, np.nan)
            feats[f"dpx{k}"] = last_up - pj
        j60 = np.searchsorted(tts, t - 60, side="left")
        big60 = c_big[idx] - c_big[j60]
        ntak60 = np.array([len(set(wal[a:b])) for a, b in zip(j60, idx)])
        n_in = idx - np.searchsorted(tts, win.start_ts, side="left")  # clean prints since the start
        # first clean print at/after the start: edge of the Up side at that moment (fair from seconds published by it)
        k0 = np.searchsorted(tts, win.start_ts, side="left")
        if k0 < len(tts):
            t1 = int(tts[k0])
            f1, _ = fair_up(sp, np.array([win.start_ts]), np.array([win.end_ts]), np.array([t1]))
            e_open_up = float(f1[0] - up_px[k0])
            open_known = t > t1  # usable once that print is published (strictly before t)
        else:
            e_open_up, open_known = np.nan, np.zeros(n, bool)
        e_open_up = np.where(open_known, e_open_up, np.nan)
        e_up = fu - last_up
        e_up_f = np.where(np.isfinite(e_up), e_up, 0.0)
        cnt = np.arange(1, n + 1)
        emax_up = np.maximum.accumulate(np.where(np.isfinite(e_up), e_up, -9))
        emin_up = np.minimum.accumulate(np.where(np.isfinite(e_up), e_up, 9))
        emean_up = np.cumsum(e_up_f) / cnt
        epos_up = np.cumsum(e_up_f > 0) / cnt
        f10 = np.where(REL >= 10, fu[1], np.nan)
        z10 = np.where(REL >= 10, zsc[1], np.nan)
        # labels and own state
        lab, own = {}, {}
        for s, tok in (("up", win.up_token), ("down", win.down_token)):
            ms = mk_by_tok.get(tok)
            if ms is None:
                lab[s] = np.zeros(n, int)
                own[s] = np.zeros(n)
                continue
            mts = ms["ts"].to_numpy().astype(np.int64)
            b = (mts - win.start_ts) // BIN
            okb = (b >= 0) & (b < n)
            lab[s] = np.bincount(b[okb], minlength=n)[:n]
            o = np.argsort(mts)
            cs = np.concatenate([[0.0], np.cumsum(ms["shares"].to_numpy()[o])])
            own[s] = cs[np.searchsorted(mts[o], t, side="left")]
        pn = prev_n.get(win.start_ts - WIN, np.nan)
        prev_n[win.start_ts] = float(np.sum((tts >= win.start_ts) & (tts < win.end_ts)))
        for s in ("up", "down"):
            sg = 1 if s == "up" else -1
            d = {"cid": win.cid, "start_ts": win.start_ts, "rel": REL, "side_up": int(s == "up"),
                 "sig": sig.astype(np.float32), "fair_s": fu if s == "up" else 1 - fu, "z_s": zsc * sg}
            d.update({k: v * sg for k, v in rets.items()})
            d["last_s"] = last_up if s == "up" else 1 - last_up
            d["edge_s"] = d["fair_s"] - d["last_s"]
            d["n_prints"] = idx
            d["n_in"] = n_in
            for k in (10, 30, 60):
                d[f"hit_s{k}"] = feats[f"hu{k}"] if s == "up" else feats[f"hd{k}"]
                d[f"hit_o{k}"] = feats[f"hd{k}"] if s == "up" else feats[f"hu{k}"]
                d[f"vol_s{k}"] = feats[f"vu{k}"] if s == "up" else feats[f"vd{k}"]
                d[f"vol_o{k}"] = feats[f"vd{k}"] if s == "up" else feats[f"vu{k}"]
                d[f"dpx_s{k}"] = feats[f"dpx{k}"] * sg
            d["big60"] = big60
            d["ntak60"] = ntak60
            d["e_open_s"] = e_open_up * sg
            d["emax_s"] = emax_up if s == "up" else -emin_up
            d["emean_s"] = emean_up * sg
            d["epos_s"] = epos_up if s == "up" else (np.cumsum((e_up_f < 0)) / cnt)
            d["f10_s"] = f10 if s == "up" else 1 - f10
            d["z10_s"] = z10 * sg
            d["prev_same"] = float(prev_up == (1.0 if s == "up" else 0.0))
            d["strike_move_s"] = strike_move * sg
            d["prev_n"] = pn
            d["y"] = (lab[s] > 0).astype(np.int8)
            d["inv_s"] = own[s]
            d["inv_o"] = own["down" if s == "up" else "up"]
            d["won_s"] = (win.up_payout if s == "up" else 1 - win.up_payout) if win.up_payout is not None and np.isfinite(win.up_payout) else np.nan
            df = pd.DataFrame(d)
            out.append(df)
    p = pd.concat(out, ignore_index=True)
    for c in p.columns:
        if p[c].dtype == np.float64:
            p[c] = p[c].astype(np.float32)
    return p
