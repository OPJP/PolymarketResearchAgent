"""Iteration 14, X127 (information P3, per-venue knee map) and X126 / X136 step 'locked share' (the time-locked share at the corrected
clock with spot BTC included). Univariate, no fit. Units: operator FIRST legs (dcfit14_pred: rank 0) of 10-17..22 with capture
match ms m0. For each venue on its own exchange clock (spot book: receive - 131; spot trades, Binance USD-M BTC / ETH, OKX swap: trade
ms; Bybit BTC 100-ms book bins: bin end), agreement of the sign of the last-value change over [m0 - c - 250, m0 - c) with the side,
c = 400 .. 100 ms (full coverage, 0 -> 1/2; and on covered), fit days and score days apart; knee by a two-segment fit.
Locked share: P(spot microprice net move toward o >= 0.1 bp over the knee band [m0 - 320, m0 - 230)) and P(spot mid price-level
change toward o in the band), against placebo bands at m0 - 3000 and m0 - 5000. Usage: python knee14.py FRAME_DIR HF_DIR"""
import os, sys, json, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
FIT = {"2026-10-17", "2026-10-18", "2026-10-19"}
CS = list(range(400, 90, -10))


def at(T, X, t):
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def two_seg(cs, a):
    cs, a = np.asarray(cs, float), np.asarray(a, float); best = None
    for k in cs[2:-2]:
        Z = np.column_stack([np.ones_like(cs), np.where(cs >= k, cs - k, 0.0), np.where(cs < k, cs - k, 0.0)])
        b, *_ = np.linalg.lstsq(Z, a, rcond=None); sse = float(((Z @ b - a) ** 2).sum())
        if best is None or sse < best[1]:
            best = (float(k), sse, b)
    return {"knee_c": best[0], "level": round(float(best[2][0]), 4), "slope_before_per_10ms": round(float(-10 * best[2][1]), 4), "slope_after_per_10ms": round(float(-10 * best[2][2]), 4)}


def main():
    D, A = sys.argv[1], sys.argv[2]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m0", "rank", "day"])
    P = P[P["rank"] == 0].reset_index(drop=True)
    y = np.where(P.up.to_numpy() == 1, 1, -1)
    sig = {}  # venue -> {c: change}
    lock = {k: np.zeros(len(P)) for k in ("mic_band", "mic_pl3", "mic_pl5", "mid_band", "mid_pl3", "mid_pl5")}
    venues = ("spot_book", "spot_trade", "usdm_btc", "usdm_eth", "okx_btc", "bybit_btc")
    for v in venues:
        sig[v] = {c: np.full(len(P), np.nan) for c in CS}
    for day in sorted(P.day.unique()):
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
        ii = np.where(P.day.to_numpy() == day)[0]; m0 = P.m0.to_numpy(np.int64)[ii]
        series = {}
        for nm, fn in (("usdm_btc", f"{C}/fut/{d0}.parquet"), ("usdm_eth", f"{C}/venues/ethfut/{d0}.parquet"), ("okx_btc", f"{C}/venues/okx/{d0}.parquet")):
            if os.path.exists(fn):
                o = pd.read_parquet(fn, columns=["T", "p"]).sort_values("T", kind="stable"); series[nm] = (o["T"].to_numpy(np.int64), o.p.to_numpy(float))
        fn = f"{C}/bybit_ob/linear_{d0}.parquet"
        if os.path.exists(fn):
            o = pd.read_parquet(fn, columns=["b", "bid", "ask", "bq", "aq"]).sort_values("b")
            series["bybit_btc"] = ((o.b.to_numpy(np.int64) + 1) * 100 - 1, ((o.bid * o.aq + o.ask * o.bq) / (o.bq + o.aq)).to_numpy(float))
        for h0 in range(0, 24, 6):
            lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 6) * 3600) * 1000
            sel = np.where((m0 >= lo) & (m0 < hi))[0]
            if not len(sel):
                continue
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "price"],
                              filters=[("receivedTimestampMs", ">=", lo - 8000), ("receivedTimestampMs", "<", hi + 2000)])
            ty = t.column("type").to_numpy(zero_copy_only=False); bk = ty == "book"; td = ty == "trade"
            Tb = t.column("receivedTimestampMs").to_numpy()[bk] - 131
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False)[bk].astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); mid = (bp + ap) / 2; o = np.argsort(Tb, kind="stable"); Tb, mic, mid = Tb[o], mic[o], mid[o]
            Tt = t.column("exchangeTimestampMs").to_numpy(zero_copy_only=False)[td].astype(np.int64); pt = t.column("price").to_numpy(zero_copy_only=False)[td].astype(float)
            o = np.argsort(Tt, kind="stable"); Tt, pt = Tt[o], pt[o]
            del t, ty, bk, td, bp, bq, ap, aq; gc.collect()
            S = dict(series); S["spot_book"] = (Tb, mic); S["spot_trade"] = (Tt, pt)
            mm = m0[sel]; gi = ii[sel]
            for v, (T_, X_) in S.items():
                for c in CS:
                    sig[v][c][gi] = at(T_, X_, mm - c) - at(T_, X_, mm - c - 250)
            yy = y[gi]
            for tag, sh in (("band", 0), ("pl3", 3000), ("pl5", 5000)):
                a1, a0 = mm - 230 - sh, mm - 320 - sh
                dmic = (at(Tb, mic, a1) / at(Tb, mic, a0) - 1) * 1e4; dmid = at(Tb, mid, a1) - at(Tb, mid, a0)
                lock[f"mic_{tag}"][gi] = (np.nan_to_num(dmic) * yy >= 0.1).astype(float)
                lock[f"mid_{tag}"][gi] = (np.nan_to_num(dmid) * yy > 0).astype(float)
            del Tb, mic, mid, Tt, pt; gc.collect()
        print(day, flush=True)
    fit = P.day.isin(FIT).to_numpy(); W = P.wallet.to_numpy()
    res = {"first_legs": int(len(P)), "venues": {}}
    for v in venues:
        o = {}
        for lab, sel in (("fit_days", fit), ("score_days", ~fit)):
            full, cov, agc = [], [], []
            for c in CS:
                s = sig[v][c][sel]; yy = y[sel]; nz = np.isfinite(s) & (s != 0)
                full.append(round(float(np.where(nz, np.sign(np.nan_to_num(s)) == yy, 0.5).mean()), 4))
                cov.append(round(float(nz.mean()), 4)); agc.append(round(float((np.sign(s[nz]) == yy[nz]).mean()), 4) if nz.any() else None)
            o[lab] = {"full_coverage": dict(zip(CS, full)), "coverage": dict(zip(CS, cov)), "agree_on_covered": dict(zip(CS, agc)),
                      "two_segment_full": two_seg(CS, full)}
        res["venues"][v] = o
        print(v, o["fit_days"]["two_segment_full"], {c: o["fit_days"]["full_coverage"][c] for c in (400, 320, 280, 260, 230, 200, 150, 100)},
              {c: o["fit_days"]["agree_on_covered"][c] for c in (320, 260, 230, 150)}, {c: o["fit_days"]["coverage"][c] for c in (320, 260, 230)}, flush=True)
    lk = {}
    for lab, sel in (("all", np.ones(len(P), bool)),) + tuple((w, W == w) for w in ("DS", "GF", "XM")):
        lk[lab] = {k: round(float(v[sel].mean()), 4) for k, v in lock.items()}
        lk[lab]["mic_excess_vs_placebo"] = round(lk[lab]["mic_band"] - 0.5 * (lk[lab]["mic_pl3"] + lk[lab]["mic_pl5"]), 4)
        lk[lab]["mid_excess_vs_placebo"] = round(lk[lab]["mid_band"] - 0.5 * (lk[lab]["mid_pl3"] + lk[lab]["mid_pl5"]), 4)
    res["locked_share_knee_band"] = lk
    print(json.dumps(lk))
    json.dump(res, open(f"{R}/knee14.json", "w"), indent=1)


if __name__ == "__main__":
    main()
