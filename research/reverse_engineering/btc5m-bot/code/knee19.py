"""Iteration 19, X191 (assumptions panel iter18 P1 step 1) and X193 (P3 session-aware routes, diagnostic part): is the operator's
decision knee a property of the CME Globex session?

PRE-REGISTRATION 16 (written before the first run, 11-01 ~12:50 UTC). Units: operator FIRST legs (dcfit14_pred rank 0) of 10-17..22
with capture match ms m0. Session from the public CME Globex calendar (CDT, valid until 11-01 07:00 UTC): closed on Saturday, Friday
>= 21:00, Sunday < 22:00 and the Mon-Thu daily break 21:00-22:00 UTC; open otherwise; 'open_us' = open and 13:30-20:00 UTC.
(1) Per-venue univariate profiles by session (knee14's definition: sign of the last-value change over [m0 - c - 250, m0 - c),
    c = 400..100 ms, full coverage 0 -> 1/2) for spot book (receive - 131), spot trades (T), USD-M BTC / ETH (T), OKX swap (T), Bybit
    linear 100-ms book bins (bin end), Coinbase and Deribit (T, the 12 cached hours). G = acc(c=160) - acc(c=260).
(2) DISCRIMINATOR (mine, not the panel's): the event-aligned PSTH. Events = Binance spot microprice jumps on the capture book (10-ms
    grid, |100-ms log return| > 3 sigma of the trailing 60-s 100-ms returns, 300-ms refractory). Histogram of m0 - t_event for first
    legs on the jump's side (and, as control, the opposite side) in 10-ms bins over [-500, +1000) ms, per event, by session.
    H_lat (a shorter latency chain on weekdays): the main peak itself moves ~100 ms earlier in open hours.
    H_lead (an extra input that leads Binance in open hours): the main peak stays at the closed-hour lag (~255 ms) and open hours add
    mass at short / negative lags (decisions before the Binance print), i.e. a lower same-side share at the peak relative to
    early-lag mass.
    Reported: peak lag (argmax of a 30-ms boxcar), half-max interval, the share of same-side mass in [-500, +150) and [150, 400) per
    1,000 events, the opposite-side baseline.
(3) Crowd control: the same profile for the 975,955 non-operator taker BUYs (dcclock14_crowd k-columns) by session.
Nothing is fitted, so there is no BUILD / VALIDATE choice here; the days are the capture days 10-17..22 (development, before H).
Usage: python knee19.py FRAME_DIR HF_DIR"""
import os, sys, json, gc, glob
import numpy as np, pandas as pd, pyarrow.parquet as pq

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
CS = list(range(400, 90, -10))
LAGS = np.arange(-500, 1000, 10)


def at(T, X, t):
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def session(ms):
    t = pd.to_datetime(np.asarray(ms, np.int64), unit="ms", utc=True)
    wd, h, mi = t.dayofweek.to_numpy(), t.hour.to_numpy(), t.minute.to_numpy()
    closed = (wd == 5) | ((wd == 4) & (h >= 21)) | ((wd == 6) & (h < 22)) | ((wd <= 3) & (h == 21))
    us = (~closed) & (wd <= 4) & ((h * 60 + mi) >= 13 * 60 + 30) & (h < 20)
    return np.where(closed, "closed", np.where(us, "open_us", "open_other"))


def two_seg(cs, a):
    cs, a = np.asarray(cs, float), np.asarray(a, float); best = None
    for k in cs[2:-2]:
        Z = np.column_stack([np.ones_like(cs), np.where(cs >= k, cs - k, 0.0), np.where(cs < k, cs - k, 0.0)])
        b, *_ = np.linalg.lstsq(Z, a, rcond=None); sse = float(((Z @ b - a) ** 2).sum())
        if best is None or sse < best[1]:
            best = (float(k), sse, b)
    return {"knee_c": best[0], "level": round(float(best[2][0]), 4), "slope_before_per_10ms": round(float(-10 * best[2][1]), 4),
            "slope_after_per_10ms": round(float(-10 * best[2][2]), 4)}


def jump_events(Tb, mic, lo, hi):
    G = np.arange(lo, hi, 10, dtype=np.int64)
    m = at(Tb, mic, G)
    lm = np.log(m)
    r = np.full(len(G), np.nan); r[10:] = lm[10:] - lm[:-10]
    sub = pd.Series(r[::10])
    sd = sub.rolling(600, min_periods=300).std().shift(1).to_numpy()
    sdg = np.repeat(sd, 10)[: len(G)]
    z = r / sdg
    cand = np.where(np.isfinite(z) & (np.abs(z) > 3.0))[0]
    ev, last = [], -10 ** 9
    for i in cand:
        if i - last > 30:  # 300 ms refractory, first crossing only
            ev.append(i)
        last = i
    ev = np.asarray(ev, np.int64)
    return G[ev], np.sign(z[ev]).astype(int)


def main():
    D, A = sys.argv[1], sys.argv[2]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m0", "rank", "day"])
    P = P[P["rank"] == 0].reset_index(drop=True)
    y = np.where(P.up.to_numpy() == 1, 1, -1)
    ses = session(P.m0.to_numpy())
    venues = ("spot_book", "spot_trade", "usdm_btc", "usdm_eth", "okx_btc", "bybit_btc", "coinbase", "deribit")
    sig = {v: {c: np.full(len(P), np.nan) for c in CS} for v in venues}
    hourly = {}
    for v in ("coinbase", "deribit"):
        fs = sorted(glob.glob(f"{C}/venues/{v}/*.parquet"))
        T = pd.concat([pd.read_parquet(f, columns=["T", "p"]) for f in fs]).sort_values("T", kind="stable")
        hrs = [int(os.path.basename(f)[:-8]) for f in fs]
        selh = np.zeros(len(P), bool)
        for h in hrs:
            selh |= (P.m0.to_numpy() >= h * 1000 + 5000) & (P.m0.to_numpy() < (h + 3600) * 1000)
        hourly[v] = (T["T"].to_numpy(np.int64), T.p.to_numpy(float), selh)
    psth = {s: {"same": np.zeros(len(LAGS)), "opp": np.zeros(len(LAGS)), "events": 0, "legs": 0} for s in ("closed", "open_us", "open_other")}
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
        for v in ("coinbase", "deribit"):
            Th, ph, selh = hourly[v]
            gi = ii[selh[ii]]
            if len(gi):
                for c in CS:
                    mm = P.m0.to_numpy(np.int64)[gi]
                    sig[v][c][gi] = at(Th, ph, mm - c) - at(Th, ph, mm - c - 250)
        for h0 in range(0, 24, 6):
            lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 6) * 3600) * 1000
            sel = np.where((m0 >= lo) & (m0 < hi))[0]
            if not len(sel):
                continue
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "price"],
                              filters=[("receivedTimestampMs", ">=", lo - 70000), ("receivedTimestampMs", "<", hi + 2000)])
            ty = t.column("type").to_numpy(zero_copy_only=False); bk = ty == "book"; td = ty == "trade"
            Tb = t.column("receivedTimestampMs").to_numpy()[bk] - 131
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False)[bk].astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); o = np.argsort(Tb, kind="stable"); Tb, mic = Tb[o], mic[o]
            Tt = t.column("exchangeTimestampMs").to_numpy(zero_copy_only=False)[td].astype(np.int64); pt = t.column("price").to_numpy(zero_copy_only=False)[td].astype(float)
            o = np.argsort(Tt, kind="stable"); Tt, pt = Tt[o], pt[o]
            del t, ty, bk, td, bp, bq, ap, aq; gc.collect()
            S = dict(series); S["spot_book"] = (Tb, mic); S["spot_trade"] = (Tt, pt)
            mm = m0[sel]; gi = ii[sel]
            for v, (T_, X_) in S.items():
                for c in CS:
                    sig[v][c][gi] = at(T_, X_, mm - c) - at(T_, X_, mm - c - 250)
            # PSTH around spot microprice jumps
            te, se = jump_events(Tb, mic, lo - 60000, hi)
            keep = te >= lo
            te, se = te[keep], se[keep]
            evs = session(te)
            order = np.argsort(mm, kind="stable"); ms_, ys_ = mm[order], y[gi][order]
            for s in psth:
                psth[s]["events"] += int((evs == s).sum())
            a = np.searchsorted(ms_, te - 500, "left"); b = np.searchsorted(ms_, te + 1000, "left")
            for k in np.where(b > a)[0]:
                lag = ms_[a[k]:b[k]] - te[k]; yy = ys_[a[k]:b[k]]
                bi = ((lag + 500) // 10).astype(int)
                s = evs[k]
                np.add.at(psth[s]["same"], bi[yy == se[k]], 1.0)
                np.add.at(psth[s]["opp"], bi[yy != se[k]], 1.0)
            for s in psth:
                psth[s]["legs"] += int((ses[gi] == s).sum())
            del Tb, mic, Tt, pt; gc.collect()
        print(day, flush=True)
    res = {"prereg": "16", "first_legs": int(len(P)), "session_counts": {s: int((ses == s).sum()) for s in ("closed", "open_us", "open_other")}, "venues": {}, "psth": {}, "crowd": {}}
    W = P.wallet.to_numpy(); days = P.day.to_numpy()
    for v in venues:
        o = {}
        for s in ("closed", "open_us", "open_other", "open"):
            sel = (ses == s) if s != "open" else (ses != "closed")
            if v in hourly:
                sel = sel & hourly[v][2]
            if sel.sum() < 50:
                continue
            full = []
            for c in CS:
                x = sig[v][c][sel]; yy = y[sel]; nz = np.isfinite(x) & (x != 0)
                full.append(round(float(np.where(nz, np.sign(np.nan_to_num(x)) == yy, 0.5).mean()), 4))
            prof = dict(zip(CS, full))
            o[s] = {"n": int(sel.sum()), "profile": {c: prof[c] for c in (400, 320, 300, 280, 260, 250, 240, 230, 220, 200, 180, 160, 150, 130, 100)},
                    "G_260_160": round(prof[160] - prof[260], 4), "G_260_200": round(prof[200] - prof[260], 4), "argmax_c": int(CS[int(np.argmax(full))]),
                    "max": float(max(full)), "two_segment": two_seg(CS, full)}
            if v == "spot_book":
                o[s]["per_wallet_G_260_160"] = {}
                for w in ("DS", "GF", "XM"):
                    sw = sel & (W == w)
                    if sw.sum() > 200:
                        a1 = []
                        for c in (260, 160):
                            x = sig[v][c][sw]; yy = y[sw]; nz = np.isfinite(x) & (x != 0)
                            a1.append(float(np.where(nz, np.sign(np.nan_to_num(x)) == yy, 0.5).mean()))
                        o[s]["per_wallet_G_260_160"][w] = round(a1[1] - a1[0], 4)
                o[s]["per_day_G_260_160"] = {}
                for d in sorted(set(days[sel])):
                    sd = sel & (days == d)
                    if sd.sum() > 300:
                        a1 = []
                        for c in (260, 160):
                            x = sig[v][c][sd]; yy = y[sd]; nz = np.isfinite(x) & (x != 0)
                            a1.append(float(np.where(nz, np.sign(np.nan_to_num(x)) == yy, 0.5).mean()))
                        o[s]["per_day_G_260_160"][d] = [int(sd.sum()), round(a1[1] - a1[0], 4)]
        res["venues"][v] = o
        print(v, {s: (o[s]["n"], o[s]["G_260_160"], o[s]["argmax_c"], o[s]["two_segment"]["knee_c"]) for s in o}, flush=True)
    for s, d in psth.items():
        ne = max(d["events"], 1)
        same = d["same"] / ne * 1000; opp = d["opp"] / ne * 1000
        sm = np.convolve(same - opp, np.ones(3) / 3, "same")
        k = int(np.argmax(sm)); pk = float(sm[k]); half = np.where(sm >= pk / 2)[0]
        # contiguous half-max interval around the peak
        lo_i = k
        while lo_i - 1 >= 0 and sm[lo_i - 1] >= pk / 2:
            lo_i -= 1
        hi_i = k
        while hi_i + 1 < len(sm) and sm[hi_i + 1] >= pk / 2:
            hi_i += 1
        def mass(a, b):
            m = (LAGS >= a) & (LAGS < b)
            return round(float(same[m].sum()), 3), round(float(opp[m].sum()), 3)
        res["psth"][s] = {"events": int(d["events"]), "legs": int(d["legs"]), "peak_lag_ms": int(LAGS[k]), "peak_excess_per_1000_events": round(pk, 3),
                          "halfmax_ms": [int(LAGS[lo_i]), int(LAGS[hi_i]) + 10],
                          "same_opp_mass_per_1000_events": {"[-500,0)": mass(-500, 0), "[0,150)": mass(0, 150), "[150,230)": mass(150, 230),
                                                             "[230,320)": mass(230, 320), "[320,500)": mass(320, 500), "[500,1000)": mass(500, 1000)},
                          "excess_curve_20ms": {int(LAGS[i]): round(float(same[i:i + 2].sum() - opp[i:i + 2].sum()), 3) for i in range(0, len(LAGS), 2) if -200 <= LAGS[i] < 600}}
        print(s, {k2: res["psth"][s][k2] for k2 in ("events", "legs", "peak_lag_ms", "peak_excess_per_1000_events", "halfmax_ms")}, res["psth"][s]["same_opp_mass_per_1000_events"], flush=True)
    Cw = pd.read_parquet(f"{D}/dcclock14_crowd.parquet")
    cs_ = session(Cw.mc.to_numpy()); yc = np.where(Cw.up.to_numpy() == 1, 1, -1)
    for s in ("closed", "open_us", "open_other"):
        sel = cs_ == s
        prof = {}
        for c in range(400, 140, -10):
            x = Cw[f"k{c}"].to_numpy()[sel]
            prof[c] = round(float(np.where(np.isfinite(x) & (x != 0), np.sign(np.nan_to_num(x)) == yc[sel], 0.5).mean()), 4)
        res["crowd"][s] = {"n": int(sel.sum()), "profile": {c: prof[c] for c in (400, 300, 260, 230, 200, 160, 150)}, "G_260_160": round(prof[160] - prof[260], 4),
                           "argmax_c": int(max(prof, key=prof.get))}
        print("crowd", s, res["crowd"][s], flush=True)
    json.dump(res, open(f"{R}/knee19.json", "w"), indent=1)


if __name__ == "__main__":
    main()
