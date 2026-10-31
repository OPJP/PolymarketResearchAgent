"""Iteration 11 (X87 step 1 / X98 step 1): venue-pair lead-lag on the exchange stamps, 10-31 14:55-17:55 (btc5m_venues2; Deribit
from btc5m_xfam 17:45-18:00 only). Microprice of each series on a 10-ms grid (last value), signed 10-ms changes; cross-correlation
corr(dX(t), dY(t + L)) for L = -300..+300 ms in 10-ms steps (L > 0: Y follows X), and the directional excess of 'Y moves the same
way within L' after big X moves (>= 0.2 bp in 10 ms). Combined with the cluster's per-venue kernel peaks (kernel7: Binance USD-M
[m - 300, m - 250), OKX [m - 350, m - 300), Bybit [m - 400, m - 350)), it tells whether OKX / Bybit stamps LEAD Binance's for the
same moves (then the bot's reaction to Binance explains all kernels) or the bot reacts to each venue with a venue-specific lag.
Usage: python xcorr11.py OUT_JSON"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
from lag7 import micro_series

A, B = 1793458500, 1793469300


def grid_of(S, key, g):
    T, p, sc = S[key]
    i = np.searchsorted(T, g, "right") - 1
    v = p[np.clip(i, 0, None)].astype(float); v[i < 0] = np.nan
    return np.log(v) * 1e4 / sc


def xc(dx, dy, lags):
    out = {}
    for Lg in lags:
        k = Lg // 10
        if k >= 0:
            a, b = dx[:len(dx) - k], dy[k:]
        else:
            a, b = dx[-k:], dy[:len(dy) + k]
        m = np.isfinite(a) & np.isfinite(b)
        out[int(Lg)] = float(np.corrcoef(a[m], b[m])[0, 1]) if m.sum() > 100 else None
    return out


def main(out):
    res = {}
    S = micro_series("btc5m_venues2", A, B)
    g = np.arange((A + 60) * 1000, (B - 10) * 1000, 10, dtype=np.int64)
    keys = [k for k in (("bf", "BTC"), ("ok", "BTC"), ("by", "BTC"), ("bs", "BTC"), ("bf", "ETH"), ("ok", "ETH")) if k in S]
    G = {k: grid_of(S, k, g) for k in keys}
    D = {k: np.r_[np.nan, np.diff(v)] for k, v in G.items()}
    lags = np.arange(-300, 310, 10)
    ref = ("bf", "BTC")
    for k in keys:
        if k == ref:
            continue
        c = xc(D[ref], D[k], lags)
        best = max((v, l) for l, v in c.items() if v is not None)
        res[f"{ref[0]}{ref[1]} -> {k[0]}{k[1]}"] = {"peak_lag_ms": best[1], "peak_corr": round(best[0], 4),
                                                   "corr_at": {l: (round(v, 4) if v is not None else None) for l, v in c.items() if l % 50 == 0}}
    # big Binance moves: P(other venue moved the same way within [0, L]) minus within [-L, 0)
    big = np.where(np.abs(D[ref]) >= 0.2)[0]
    res["big_bf_moves"] = int(len(big))
    for k in keys:
        if k == ref:
            continue
        row = {}
        for Lms in (20, 50, 100, 200):
            n = Lms // 10
            fw = []; bw = []
            for i in big:
                if i - n < 1 or i + n >= len(g):
                    continue
                sgn = np.sign(D[ref][i])
                fw.append(np.sign(G[k][i + n] - G[k][i]) == sgn); bw.append(np.sign(G[k][i] - G[k][i - n]) == sgn)
            row[f"after_{Lms}"] = round(float(np.mean(fw)), 4); row[f"before_{Lms}"] = round(float(np.mean(bw)), 4)
        res[f"same-way share around big bf moves: {k[0]}{k[1]}"] = row
    # Deribit (xfam, 17:45-18:00 development part)
    try:
        a2, b2 = 1793468760, 1793469300
        rows = []
        for r in L.recs("btc5m_xfam", a2 - 30, b2):
            if r.get("v") == "db" and r.get("y") == "BTC" and r.get("b") and r.get("a") and r.get("E"):
                rows.append((r["E"], r["b"], r.get("B") or 0, r["a"], r.get("A") or 0))
        x = np.array(sorted(rows), float)
        mic = (x[:, 1] * x[:, 4] + x[:, 3] * x[:, 2]) / np.maximum(x[:, 2] + x[:, 4], 1e-12)
        g2 = np.arange(a2 * 1000, b2 * 1000, 10, dtype=np.int64)
        i = np.searchsorted(x[:, 0].astype(np.int64), g2, "right") - 1
        db = np.log(mic[np.clip(i, 0, None)]) * 1e4; db[i < 0] = np.nan
        bfg = grid_of(S, ref, g2)
        c = xc(np.r_[np.nan, np.diff(bfg)], np.r_[np.nan, np.diff(db)], lags)
        best = max((v, l) for l, v in c.items() if v is not None)
        res["bfBTC -> deribit BTC perp (17:46-17:55)"] = {"peak_lag_ms": best[1], "peak_corr": round(best[0], 4),
                                                         "corr_at": {l: (round(v, 4) if v is not None else None) for l, v in c.items() if l % 50 == 0}}
    except Exception as e:
        res["deribit_error"] = repr(e)[:200]
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1)[:5000])


if __name__ == "__main__":
    main(sys.argv[1])
