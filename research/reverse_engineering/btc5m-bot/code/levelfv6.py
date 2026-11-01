"""Iteration 6 (X21 / X13: a calibrated LEVEL fair value). For each live development taker match (live6_events.parquet) and
for placebo instants: FV_Up = P(settlement TWAP > strike), with
  strike K = mean of the Chainlink RTDS 1-s BTC values over [start - 60, start)            (window k's priceToBeat)
  S = Binance USD-M BTC last trade at m - 100 ms x Chainlink basis (median Chainlink / Binance 1-s ratio, last 60 s)
  before the last minute: TWAP_end ~ N(S, sigma^2 (tau - 40)); in the last minute: w A + (1 - w) S with A the observed
  partial Chainlink average and variance (1 - w)^2 sigma^2 tau / 3
  sigma = k x realized 1-s log vol of Binance USD-M BTC over the previous 300 s; k chosen at PLACEBO instants to minimise
  the median |FV - Polymarket mid| (calibration first, as the panel asked).
Side rule: buy the outcome with the larger FV_o - ask_o (asks from the shared book 100 ms before). Reports calibration,
side accuracy (quiet / moving), and the distribution of x = (FV_o - ask_o) / (p (1 - p)) for the bought outcome against
placebo instants. Usage: python levelfv6.py START END"""
import os, sys, glob, json
import numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6
C = L.C


def main(a, b):
    ev = pd.read_parquet(C + "/live6_events.parquet")
    tok, books, trades = L.load_books(a, b)
    T, p = live6.series(sorted(glob.glob(f"{live6.P}/rest6_bnf_BTCUSDT_*.parquet")))
    cl = live6.chainlink(a - 600, b)
    CT, CP = cl
    # 1-s Binance closes for the basis and realized vol
    sec = (T // 1000).astype(np.int64)
    last = pd.Series(p).groupby(sec).last()
    s_idx = last.index.to_numpy(np.int64); s_px = last.to_numpy(float)
    full = pd.Series(s_px, index=s_idx).reindex(np.arange(s_idx[0], s_idx[-1] + 1)).ffill()
    lr = np.log(full).diff()
    cls = pd.Series(CP, index=(CT // 1000).astype(np.int64))
    cls = cls[~cls.index.duplicated()]

    def state(t_ms, start, is_up_token):
        t = t_ms / 1000.0
        i = int(t) - 1
        if i - 300 < full.index[0] or i > full.index[-1]:
            return None
        Sb = last_px = np.interp(t_ms - 100, T, p) if False else p[max(np.searchsorted(T, t_ms - 100) - 1, 0)]
        win = np.arange(i - 60, i)
        c = cls.reindex(win).to_numpy(); bnc = full.reindex(win).to_numpy()
        ok = np.isfinite(c) & np.isfinite(bnc)
        if ok.sum() < 20:
            return None
        basis = np.median(c[ok] / bnc[ok])
        S = Sb * basis
        kv = cls.reindex(np.arange(start - 60, start)).to_numpy()
        if np.isfinite(kv).sum() < 30:
            return None
        K = np.nanmean(kv)
        vol = np.nanstd(lr.reindex(np.arange(i - 300, i)).to_numpy())
        end = start + 300
        tau = end - t
        if tau <= 0:
            return None
        if tau > 60:
            mean, var_t = S, max(tau - 40.0, 1.0)
            wobs = 0.0
        else:
            w = (t - (end - 60)) / 60.0
            obs = cls.reindex(np.arange(end - 60, int(t) - 1)).to_numpy()
            A = np.nanmean(obs) if np.isfinite(obs).any() else S
            mean = w * A + (1 - w) * S
            var_t = max((1 - w) ** 2 * tau / 3.0, 0.05)
            wobs = w
        return mean, K, vol, var_t, wobs

    def mid_ask(up_token, t_ms):
        arr = books.get(up_token)
        if arr is None:
            return (np.nan,) * 3
        j = np.searchsorted(arr[:, 0], t_ms, side="left") - 1
        if j < 0:
            return (np.nan,) * 3
        bb, ba = arr[j, 2], arr[j, 3]
        return (bb + ba) / 2, ba, 1 - bb  # Up mid, Up ask, Down ask

    rng = np.random.default_rng(9)
    rows = []
    for kind in ("match", "placebo"):
        for r in ev.itertuples():
            t_ms = r.m if kind == "match" else int(r.m + rng.choice([-1, 1]) * rng.uniform(5000, 60000))
            if t_ms / 1000 < r.start + 2 or t_ms / 1000 > r.start + 298:
                continue
            st = state(t_ms, r.start, True)
            if st is None:
                continue
            md, au, ad = mid_ask(r.up_token, t_ms - 100)
            rows.append((kind, r.m, r.is_up, bool(r.quiet_trades8), r.start, t_ms, *st, md, au, ad))
    D = pd.DataFrame(rows, columns=["kind", "m", "is_up", "quiet", "start", "t", "mean", "K", "vol", "var_t", "wobs", "mid", "ask_up", "ask_dn"])
    D = D[np.isfinite(D.mid) & np.isfinite(D.ask_up) & np.isfinite(D.ask_dn) & (D.vol > 0)]
    res = {"rows_match": int((D.kind == "match").sum()), "rows_placebo": int((D.kind == "placebo").sum())}

    def fv(df, k):
        z = np.log(df["mean"] / df.K) / (k * df.vol * np.sqrt(df.var_t))
        return norm.cdf(z)
    P0 = D[D.kind == "placebo"]
    best = None
    for k in (0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.3, 1.6, 2.0, 3.0):
        e = np.median(np.abs(fv(P0, k) - P0.mid))
        if best is None or e < best[1]:
            best = (k, e)
    k = best[0]
    res["calibration"] = {"k": k, "median_abs_fv_minus_mid_placebo": round(float(best[1]), 4)}
    D["fv_up"] = fv(D, k)
    D["x_up"] = D.fv_up - D.ask_up; D["x_dn"] = (1 - D.fv_up) - D.ask_dn
    M = D[D.kind == "match"].copy()
    M["pred_up"] = M.x_up > M.x_dn
    ok = M.pred_up == M.is_up
    res["side_acc_all"] = round(float(ok.mean()), 4)
    res["side_acc_quiet"] = round(float(ok[M.quiet].mean()), 4) if M.quiet.any() else None
    res["side_acc_moving"] = round(float(ok[~M.quiet].mean()), 4) if (~M.quiet).any() else None
    res["side_acc_last_minute"] = round(float(ok[M.wobs > 0].mean()), 4) if (M.wobs > 0).any() else None
    pb = np.where(M.is_up, M.ask_up, M.ask_dn)
    xb = np.where(M.is_up, M.x_up, M.x_dn) / np.maximum(pb * (1 - pb), 0.05)
    xo = np.where(M.is_up, M.x_dn, M.x_up)
    res["x_bought_norm_q"] = {str(q): round(float(np.quantile(xb, q)), 3) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
    res["share_bought_below_fv"] = round(float((np.where(M.is_up, M.x_up, M.x_dn) > 0).mean()), 4)
    P = D[D.kind == "placebo"]
    xp = np.maximum(P.x_up, P.x_dn) / np.maximum(np.where(P.x_up > P.x_dn, P.ask_up * (1 - P.ask_up), P.ask_dn * (1 - P.ask_dn)), 0.05)
    res["placebo_best_x_norm_q"] = {str(q): round(float(np.quantile(xp, q)), 3) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
    for thr in (0.0, 0.035, 0.07):
        res[f"share_x_bought_gt_{thr}"] = round(float((xb > thr).mean()), 4)
        res[f"placebo_share_best_x_gt_{thr}"] = round(float((xp > thr).mean()), 4)
    return res


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    res = main(a, b)
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_levelfv_iter6.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))
