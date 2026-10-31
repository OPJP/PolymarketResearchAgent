"""Iteration 6 live-lab event study at exchange / matching-engine ms (X18, X19, X20, X23; panel iteration 5).
Development blocks only (iter_live through live_lab.recs; fills of windows that START in development intervals).
Unit: every cluster TAKER order fill (on-chain OrderFilled, counterparty = exchange) whose tx has a recorded match time
(min server ms of the recorded last-trade events with the same tx hash; shared clob_crypto, plus btc5m_clob_raw).
For each match m and each feed: the signed move over [m - W - g, m - g) (bp, last trade/mid price), side agreement
(Up = price up) against a placebo at m +- U(5, 60) s (same side label). Also Chainlink RTDS 1-s values under an assumed
availability lag L, Polymarket book events on the bought outcome (ask change in the last 1 s / 300 ms), crowd co-trades.
Usage: python live6.py OWN_PARQUET START END"""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import sealed
C = L.C
P = C + "/post"
EXCH = ("e111180000d2663c0091e4f400237545b87b996b", "e2222d279d744050d28e00520010520000310f59")
RNG = np.random.default_rng(6)


def own_taker(path, a, b):
    d = pd.read_parquet(path)
    d = d[(d.ts >= a) & (d.ts < b)].copy()
    d["wal"] = d.owner.map(L.W)
    d["role"] = np.where(d.cp.str[-40:].isin(EXCH), "T", "M")
    return d


def raw_clob(a, b):
    """my unthrottled BTC 5m recorder: tokens per window, Up-token touch after every near-touch change, trades."""
    tok, touch, trades = {}, [], []
    for r in L.recs("btc5m_clob_raw", a, b):
        k = r.get("k")
        if k == "S":
            tok[r["u"]] = (r["m"], True, r["u"]); tok[r["d"]] = (r["m"], False, r["u"])
        elif k == "p":
            touch.append((r["s"], r["m"], r["bb"], r["ba"], r["d"], r["p"], r["z"]))
        elif k == "x":
            trades.append((r["s"], r["t"], r["m"], r["u"], r["p"], r["z"], r["d"], r["h"]))
    touch = pd.DataFrame(touch, columns=["s", "m", "bb", "ba", "d", "p", "z"])
    trades = pd.DataFrame(trades, columns=["s_ms", "t_ms", "m", "u", "p", "z", "d", "tx"])
    return tok, touch, trades


def series(feed_files):
    if not feed_files:
        return None
    df = pd.concat([pd.read_parquet(f) for f in feed_files]).sort_values("T").drop_duplicates()
    return df["T"].to_numpy(np.int64), df["p"].to_numpy(float)


def last_px(T, p, t):
    i = np.searchsorted(T, t, side="left") - 1
    out = np.where(i >= 0, p[np.clip(i, 0, None)], np.nan)
    return out


def move_bp(T, p, m, W, g=0):
    a = last_px(T, p, m - g); b0 = last_px(T, p, m - g - W)
    return (a / b0 - 1.0) * 1e4


def agree_stats(mv, up, thr):
    ok = np.isfinite(mv) & (np.abs(mv) > thr)
    if ok.sum() == 0:
        return {"moved": 0.0, "n_moved": 0, "agree": None}
    ag = (np.sign(mv[ok]) > 0) == up[ok]
    return {"moved": round(float(ok.mean()), 4), "n_moved": int(ok.sum()), "agree": round(float(ag.mean()), 4)}


def quote_feeds(m, pl, up, quiet, ev):
    """my recorder (btc5m_venues): sized top of book; time = exchange ms E (Binance spot has none: recv - median recv-E offset of
    Binance futures). Mid and microprice moves over [m - W - g, m - g)."""
    a, b = int(m.min() // 1000) - 30, int(m.max() // 1000) + 5
    rows = {}
    for r in L.recs("btc5m_venues", a, b):
        v = r.get("v")
        if v in ("bf", "bs", "by", "ok", "hl") and r.get("b") and r.get("a"):
            rows.setdefault((v, r["y"]), []).append((r.get("E") or 0, r["t"], r["b"], r.get("B") or 0, r["a"], r.get("A") or 0))
    if not rows:
        return None
    off = None
    if ("bf", "BTC") in rows:
        x = np.array(rows[("bf", "BTC")], float); off = float(np.median(x[:, 1] - x[:, 0]))
    out = {"recv_minus_exchange_ms_bf": off}
    cov = None
    for (v, y), lst in rows.items():
        x = np.array(lst, float)
        T = x[:, 0] if v != "bs" else x[:, 1] - (off or 0)
        o = np.argsort(T, kind="stable"); x = x[o]; T = T[o].astype(np.int64)
        mid = (x[:, 2] + x[:, 4]) / 2
        mic = (x[:, 2] * x[:, 5] + x[:, 4] * x[:, 3]) / np.maximum(x[:, 3] + x[:, 5], 1e-12)
        ins = (m > T[0] + 3000) & (m < T[-1] - 500)
        r = {"n_records": int(len(T)), "matches_covered": int(ins.sum())}
        for nm, px, thr in (("mid", mid, 0.02), ("micro", mic, 0.05)):
            for W, g in ((1000, 0), (500, 100), (300, 0), (200, 50)):
                mv = move_bp(T, px, m, W, g); mvp = move_bp(T, px, pl, W, g)
                r[f"{nm}_W{W}_g{g}"] = {"match": agree_stats(mv[ins], up[ins], thr), "placebo": agree_stats(mvp[ins], up[ins], thr),
                                        "quiet": agree_stats(mv[ins & quiet], up[ins & quiet], thr)}
                if nm == "micro" and (W, g) == (500, 100):
                    ev[f"q_{v}_{y}"] = np.where(ins, mv, np.nan)
        out[f"{v}_{y}"] = r
    return out


def chainlink(a, b):
    rows = {}
    for r in L.recs("rtds", a - 120, b):
        try:
            j = json.loads(r["m"]) if isinstance(r.get("m"), str) else r
        except Exception:
            continue
        pl = j.get("payload") or {}
        sym = pl.get("symbol") or ""
        topic = j.get("topic") or ""
        if "btc" not in sym or "twap" in topic:
            continue
        for x in pl.get("data") or []:
            rows[int(x["timestamp"])] = float(x["value"])
    if not rows:
        return None
    s = pd.Series(rows).sort_index()
    return s.index.to_numpy(np.int64), s.to_numpy(float)


def main(own_path, a, b):
    res = {}
    d = own_taker(own_path, a, b)
    # windows must start in development intervals (units, not timestamps)
    tok, books, trades = L.load_books(a, b)
    tok2, touch2, trades2 = raw_clob(a, b)
    allt = pd.concat([trades[["s_ms", "tx"]], trades2[["s_ms", "tx"]]])
    mt = allt.groupby("tx").s_ms.min()
    tk = d[d.role == "T"].copy()
    tmap = {**{k: (v[1], v[2], v[3]) for k, v in tok.items()}, **tok2}
    tk = tk[tk.token.isin(tmap.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tmap[t][0]); tk["is_up"] = tk.token.map(lambda t: tmap[t][1]); tk["up_token"] = tk.token.map(lambda t: tmap[t][2])
    tk = tk[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in tk.start], bool)]
    tk = tk.drop_duplicates(["tx", "owner", "token"])
    tk["m"] = tk.tx.map(mt)
    res["taker_fills"] = int(len(tk)); res["with_match_time"] = int(tk.m.notna().sum())
    tk = tk[tk.m.notna()].copy()
    tk["m"] = tk.m.astype(np.int64)
    tk.to_parquet(C + "/live6_takers.parquet", index=False)
    # one event per (tx, outcome): the decision unit is the submitted order; wallets kept for per-wallet splits
    ev = tk.sort_values("m").drop_duplicates(["tx", "token"]).copy()
    res["matches"] = int(len(ev)); res["by_wallet"] = ev.wal.value_counts().to_dict()
    up = ev.is_up.to_numpy(bool); m = ev.m.to_numpy(np.int64)
    pl = m + (RNG.choice([-1, 1], len(m)) * RNG.uniform(5000, 60000, len(m))).astype(np.int64)
    feeds = {}
    for v, sym in [("bnf", "BTCUSDT"), ("bnf", "ETHUSDT"), ("bns", "BTCUSDT"), ("bns", "ETHUSDT"), ("cb", "BTC-USD"), ("cb", "ETH-USD"), ("okx", "BTC-USDT-SWAP"), ("okx", "ETH-USDT-SWAP")]:
        s = series(sorted(glob.glob(f"{P}/rest6_{v}_{sym}_*.parquet")))
        if s is not None:
            feeds[f"{v}_{sym[:3]}"] = s
    res["feeds"] = {k: int(len(v[0])) for k, v in feeds.items()}
    cov_lo = max(v[0][0] for v in feeds.values()) if feeds else 0
    cov_hi = min(v[0][-1] for v in feeds.values()) if feeds else 0
    inside = (m > cov_lo + 3000) & (m < cov_hi - 1000)
    res["matches_inside_feed_coverage"] = int(inside.sum())
    out = {}
    MV = {}
    MV3 = {}
    for name, (T, p) in feeds.items():
        thr = 0.1
        r = {}
        for W, g in ((1000, 0), (300, 0), (500, 100), (1000, 100), (2000, 0)):
            mv = move_bp(T, p, m, W, g); mvp = move_bp(T, p, pl, W, g)
            r[f"W{W}_g{g}"] = {"match": agree_stats(mv[inside], up[inside], thr), "placebo": agree_stats(mvp[inside], up[inside], thr)}
            if (W, g) == (1000, 0):
                MV[name] = mv
            if (W, g) == (2000, 0):
                MV3.setdefault(name, mv)
        # lag of the last price change toward the side before m (ms), matches vs placebo
        out[name] = r
    res["trade_feeds"] = out
    # composite quiet label (all trade feeds, 1 s, > 0.1 bp)
    if MV:
        M = np.vstack([MV[k] for k in MV])  # feeds x matches
        moved = np.nanmax(np.abs(M), axis=0) > 0.1
        votes = np.nansum(np.sign(M) * (np.abs(M) > 0.1), axis=0)
        res["composite_1s"] = {"moved_any": round(float(moved[inside].mean()), 4),
                               "agree_vote_where_moved": round(float(((votes > 0) == up)[inside & moved & (votes != 0)].mean()), 4),
                               "n_moved_vote": int((inside & moved & (votes != 0)).sum())}
        quiet = inside & ~moved
        ev["quiet_trades8"] = quiet
        M3 = np.vstack([MV3[k] for k in MV3])
        moved3 = np.nanmax(np.abs(M3), axis=0) > 0.1
        votes3 = np.nansum(np.sign(M3) * (np.abs(M3) > 0.1), axis=0)
        res["composite_2s"] = {"moved_any": round(float(moved3[inside].mean()), 4),
                               "agree_vote_where_moved": round(float(((votes3 > 0) == up)[inside & moved3 & (votes3 != 0)].mean()), 4)}
        # decision-aligned window [m - 600, m - 100) ms: the reaction window found live
        MVd = []
        for name, (T, p) in feeds.items():
            x = move_bp(T, p, m, 500, 100)
            MVd.append(x / (1.235 if "ETH" in name else 1.0))
        Md = np.vstack(MVd)
        big = np.nanargmax(np.where(np.isfinite(Md), np.abs(Md), -1), axis=0)
        lead = Md[big, np.arange(Md.shape[1])]
        movd = np.abs(lead) > 0.1
        res["composite_600_100ms_largest_move"] = {"moved": round(float(movd[inside].mean()), 4), "agree": round(float(((lead > 0) == up)[inside & movd].mean()), 4),
                                                    "n": int((inside & movd).sum())}
        ev["lead_move"] = lead
    else:
        quiet = inside
    res["quiet_share"] = round(float(quiet[inside].mean()), 4) if inside.any() else None
    # staleness: older moves (before the last second) in quiet matches
    st = {}
    for name, (T, p) in feeds.items():
        r = {}
        for W, g in ((2000, 1000), (4000, 1000), (9000, 1000), (500, 100)):
            mv = move_bp(T, p, m, W, g); mvp = move_bp(T, p, pl, W, g)
            r[f"W{W}_g{g}"] = {"quiet_match": agree_stats(mv[quiet], up[quiet], 0.1), "quiet_placebo": agree_stats(mvp[quiet], up[quiet], 0.1)}
        st[name] = r
    res["staleness_quiet"] = st
    res["quotes"] = quote_feeds(m, pl, up, quiet, ev)
    # Chainlink RTDS 1-s values: assume the value stamped k is usable from k + Lag ms
    cl = chainlink(a, b)
    if cl is not None:
        T, p = cl
        r = {}
        for lag in (0, 250, 500, 750, 1000, 1250, 1500, 2000, 3000):
            mv = move_bp(T + lag, p, m, 1000); mvp = move_bp(T + lag, p, pl, 1000)
            r[str(lag)] = {"match": agree_stats(mv, up, 0.05), "placebo": agree_stats(mvp, up, 0.05),
                           "quiet_match": agree_stats(mv[quiet], up[quiet], 0.05)}
        res["chainlink_lag_scan"] = r
    # Polymarket book: effective ask of the bought outcome, shared 200-ms record (q) and my raw touch (p)
    def eff_ask_shared(upt, t, is_up):
        arr = books.get(upt)
        if arr is None or not len(arr):
            return np.nan
        i = np.searchsorted(arr[:, 0], t, side="left") - 1
        if i < 0:
            return np.nan
        return arr[i, 3] if is_up else 1.0 - arr[i, 2]
    raw_by_m = {k: g.sort_values("s")[["s", "bb", "ba"]].to_numpy(float) for k, g in touch2.groupby("m")} if len(touch2) else {}
    def eff_ask_raw(start, t, is_up):
        arr = raw_by_m.get(start)
        if arr is None or not len(arr):
            return np.nan
        i = np.searchsorted(arr[:, 0], t, side="left") - 1
        if i < 0:
            return np.nan
        return arr[i, 2] if is_up else 1.0 - arr[i, 1]
    bk = {}
    for src, fn, key in (("shared200ms", eff_ask_shared, "up_token"), ("raw", eff_ask_raw, "start")):
        r = {}
        for W in (1000, 300, 100):
            vals = []
            for tt in (m, pl):
                a1 = np.array([fn(k, t - 50, u) for k, t, u in zip(ev[key], tt, up)])
                a0 = np.array([fn(k, t - 50 - W, u) for k, t, u in zip(ev[key], tt, up)])
                vals.append(np.round(a1 - a0, 4))
            dm, dp = vals
            okm, okp = np.isfinite(dm), np.isfinite(dp)
            r[f"W{W}"] = {"n": int(okm.sum()), "ask_rose": round(float((dm[okm] > 0).mean()), 4) if okm.any() else None, "ask_fell": round(float((dm[okm] < 0).mean()), 4) if okm.any() else None,
                          "placebo_rose": round(float((dp[okp] > 0).mean()), 4) if okp.any() else None, "placebo_fell": round(float((dp[okp] < 0).mean()), 4) if okp.any() else None,
                          "quiet_n": int((okm & quiet).sum()), "quiet_rose": round(float((dm[okm & quiet] > 0).mean()), 4) if (okm & quiet).any() else None,
                          "quiet_fell": round(float((dm[okm & quiet] < 0).mean()), 4) if (okm & quiet).any() else None}
            if src == "raw" and W == 300:
                ev["d_ask_300"] = dm
        bk[src] = r
    res["polymarket_book"] = bk
    # raw (unthrottled) book: bid of the bought outcome (= 1 - ask of the other outcome) and the mid, end at m - 20 ms
    def eff_bid_raw(start, t, is_up):
        arr = raw_by_m.get(start)
        if arr is None or not len(arr):
            return np.nan
        i = np.searchsorted(arr[:, 0], t, side="left") - 1
        if i < 0:
            return np.nan
        return arr[i, 1] if is_up else 1.0 - arr[i, 2]
    rb = {}
    for W in (1000, 300):
        r = {}
        for nm, fn in (("ask", eff_ask_raw), ("bid", eff_bid_raw)):
            vals = []
            for tt in (m, pl):
                a1 = np.array([fn(k, t - 20, u) for k, t, u in zip(ev.start, tt, up)])
                a0 = np.array([fn(k, t - 20 - W, u) for k, t, u in zip(ev.start, tt, up)])
                vals.append(np.round(a1 - a0, 4))
            dm, dp = vals
            okm, okp = np.isfinite(dm), np.isfinite(dp)
            for lab, msk in (("all", okm), ("quiet", okm & quiet), ("moving", okm & ~quiet)):
                if msk.sum():
                    r[f"{nm}_{lab}"] = {"n": int(msk.sum()), "rose": round(float((dm[msk] > 0).mean()), 4), "fell": round(float((dm[msk] < 0).mean()), 4)}
            if okp.any():
                r[f"{nm}_placebo"] = {"n": int(okp.sum()), "rose": round(float((dp[okp] > 0).mean()), 4), "fell": round(float((dp[okp] < 0).mean()), 4)}
        rb[f"W{W}_end20"] = r
    res["raw_book_bought_outcome"] = rb
    # crowd: other trades on the same market (any token) within +-300 ms, and same-direction share
    tr_all = pd.concat([trades.assign(start=trades.token.map(lambda t: tok.get(t, (0, 0, 0, 0))[1]), u=trades.token.map(lambda t: int(bool(tok.get(t, (0, 0, False, 0))[2]))))[["s_ms", "start", "u", "d", "tx"]],
                        trades2.rename(columns={"m": "start"})[["s_ms", "start", "u", "d", "tx"]]]).drop_duplicates(["tx", "u", "s_ms"])
    tr_all["buy_up"] = np.where(tr_all.d == "BUY", tr_all.u == 1, tr_all.u == 0)
    cl_tx = set(d.tx)
    oth = tr_all[~tr_all.tx.isin(cl_tx)]
    by_start = {k: g.sort_values("s_ms")[["s_ms", "buy_up"]].to_numpy() for k, g in oth.groupby("start")}
    def crowd(tt):
        before, after, same_b = [], [], []
        for k, t, u in zip(ev.start, tt, up):
            arr = by_start.get(k)
            if arr is None:
                before.append(np.nan); after.append(np.nan); same_b.append(np.nan); continue
            s = arr[:, 0].astype(np.int64)
            i0, i1, i2 = np.searchsorted(s, t - 300), np.searchsorted(s, t), np.searchsorted(s, t + 300, side="right")
            before.append(i1 - i0); after.append(i2 - i1)
            same_b.append(float(np.mean(arr[i0:i1, 1].astype(bool) == u)) if i1 > i0 else np.nan)
        return np.array(before, float), np.array(after, float), np.array(same_b, float)
    cb_, ca_, cs_ = crowd(m); pb_, pa_, ps_ = crowd(pl)
    res["crowd_300ms"] = {"match_any_before": round(float(np.nanmean(cb_ > 0)), 4), "match_any_after": round(float(np.nanmean(ca_ > 0)), 4),
                          "placebo_any_before": round(float(np.nanmean(pb_ > 0)), 4), "placebo_any_after": round(float(np.nanmean(pa_ > 0)), 4),
                          "match_same_dir_before": round(float(np.nanmean(cs_)), 4), "quiet_any_before": round(float(np.nanmean(cb_[quiet] > 0)), 4) if quiet.any() else None,
                          "quiet_same_dir_before": round(float(np.nanmean(cs_[quiet])), 4) if quiet.any() else None}
    ev["crowd_before"] = cb_; ev["crowd_after"] = ca_; ev["crowd_same"] = cs_
    for k, v in MV.items():
        ev["mv_" + k] = v
    ev.to_parquet(C + "/live6_events.parquet", index=False)
    return res


if __name__ == "__main__":
    own_path, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    res = main(own_path, a, b)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_live6_iter6.json")
    json.dump(res, open(out, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:6000])
