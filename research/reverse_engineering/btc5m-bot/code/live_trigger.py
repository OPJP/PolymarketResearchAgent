"""Iteration 5 (live lab): what comes just before the cluster's MATCH times (server ms of the recorded last-trade event with
the cluster tx hash). Uses live_lab_cluster_orders.parquet (live_lab.py), the recorded trades/books (clob_crypto),
Chainlink RTDS (crypto_prices btc/usd, 1-s), and Binance futures aggTrades REST (fetch_binance_rest.py) for the same
development interval. Placebo: the same statistics at random times in the same windows (rel 5..270 s).
Usage: python live_trigger.py START END BNF_PARQUET [ETH_PARQUET]"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
C = L.C


def chainlink(a, b):
    rows = {}
    for r in L.recs("rtds", a - 120, b + 120):
        try:
            m = json.loads(r["m"])
        except Exception:
            continue
        if m.get("topic") != "crypto_prices" or (m.get("payload") or {}).get("symbol") != "btc/usd":
            continue
        for x in m["payload"].get("data", []):
            rows[int(x["timestamp"])] = float(x["value"])
    s = pd.Series(rows).sort_index()
    return s


def move_toward(ts_ms, px_t, px, t, lag0, lag1, up):
    """log move of px over [t-lag1, t-lag0) (ms), signed toward the bought side."""
    i1 = np.searchsorted(ts_ms, t - lag0, side="left") - 1
    i0 = np.searchsorted(ts_ms, t - lag1, side="left") - 1
    ok = (i0 >= 0) & (i1 >= 0)
    r = np.where(ok, np.log(px[np.clip(i1, 0, None)] / px[np.clip(i0, 0, None)]) * 1e4, np.nan)
    return np.where(up, r, -r)


def main(a, b, bnf_path, eth_path=None):
    cl = pd.read_parquet(C + "/live_lab_cluster_orders.parquet")
    tk = cl[(cl.role == "T") & cl.match_s.notna()].drop_duplicates("tx").copy()
    tok, books, trades = L.load_books(a, b)
    rng = np.random.default_rng(7)
    # placebo times in the same windows
    pl = tk[["start_ts", "is_up", "up_token", "token"]].copy()
    pl["match_s"] = (pl.start_ts + rng.uniform(5, 270, len(pl))) * 1000.0
    pl["is_up"] = rng.random(len(pl)) < 0.5
    res = {"n_taker_orders": int(len(tk))}
    # Binance futures (and ETH) moves toward the bought side at sub-second lags before the match
    for name, path in (("bnf", bnf_path), ("eth", eth_path)):
        if not path or not os.path.exists(path):
            continue
        f = pd.read_parquet(path).sort_values("T")
        T = f["T"].to_numpy().astype(float); P = f["p"].to_numpy()
        for lag0, lag1 in ((0, 250), (250, 500), (500, 1000), (1000, 1500), (1500, 2000), (2000, 3000), (3000, 5000), (0, 1000), (0, 2000)):
            for lab, x in (("bot", tk), ("placebo", pl)):
                mv = move_toward(T, None, P, x.match_s.to_numpy(), lag0, lag1, x.is_up.to_numpy())
                nz = np.abs(mv) > 0.05
                res[f"{name}_[{-lag1},{-lag0})ms_{lab}"] = {"agree": round(float((mv[nz] > 0).mean()), 4) if nz.sum() else None, "n_moved": int(nz.sum()), "n": int(len(mv))}
    # Chainlink RTDS 1-s price: move over the last 1..3 s (timestamps are the second the value refers to)
    cs = chainlink(a, b)
    if len(cs):
        T = cs.index.to_numpy().astype(float); P = cs.to_numpy()
        for lag0, lag1 in ((0, 1000), (1000, 2000), (2000, 3000), (0, 3000), (-2000, 0)):
            for lab, x in (("bot", tk), ("placebo", pl)):
                mv = move_toward(T, None, P, x.match_s.to_numpy(), lag0, lag1, x.is_up.to_numpy())
                nz = np.abs(mv) > 0.01
                res[f"chainlink_[{-lag1},{-lag0})ms_{lab}"] = {"agree": round(float((mv[nz] > 0).mean()), 4) if nz.sum() else None, "n_moved": int(nz.sum()), "n": int(len(mv))}
        res["chainlink_points"] = int(len(cs))
    # Polymarket tape just before the match: time since the last OTHER trade on the market, same token & price
    clus_tx = set(cl.tx)
    tr = trades[~trades.tx.isin(clus_tx)].copy()
    tr["up_token"] = tr.token.map(lambda t: tok[t][3]); tr["is_up"] = tr.token.map(lambda t: tok[t][2])
    by_mkt = {u: g.sort_values("s_ms") for u, g in tr.groupby("up_token")}
    def since(x, same_token_px):
        out = []
        for u, m, up, lim in zip(x.up_token, x.match_s, x.is_up, x.get("limit", pd.Series(np.nan, index=x.index))):
            g = by_mkt.get(u)
            if g is None:
                out.append(np.nan); continue
            gg = g[g.s_ms < m]
            if same_token_px:
                # trades that took the same price on the same token (BUY) or the complementary token at 1-p
                gg = gg[((gg.is_up == up) & (np.abs(gg.p - lim) < 1e-6)) | ((gg.is_up != up) & (np.abs(gg.p - (1 - lim)) < 1e-6))]
            out.append((m - gg.s_ms.iloc[-1]) / 1000.0 if len(gg) else np.nan)
        return np.array(out)
    s_any = since(tk, False); s_same = since(tk, True)
    pl2 = pl.copy(); pl2["limit"] = tk["limit"].to_numpy()
    p_any = since(pl2, False)
    for lab, v in (("bot_since_any_other_trade_s", s_any), ("placebo_since_any_other_trade_s", p_any), ("bot_since_other_trade_same_price_s", s_same)):
        vv = v[np.isfinite(v)]
        res[lab] = {str(k): round(float(np.quantile(vv, k)), 3) for k in (0.1, 0.25, 0.5, 0.75, 0.9)} if len(vv) else None
        res[lab + "_share_lt_0.5s"] = float((vv < 0.5).mean()) if len(vv) else None
        res[lab + "_share_lt_2s"] = float((vv < 2).mean()) if len(vv) else None
    # book change of the bought token's ask in the last 1 s before the match vs placebo
    def ask_change(x):
        out = []
        for u, m, up in zip(x.up_token, x.match_s, x.is_up):
            a1 = L.touch_before(books, u, m, up)[0]; a0 = L.touch_before(books, u, m - 1000, up)[0]
            out.append(a1 - a0)
        return np.array(out)
    ab = ask_change(tk); ap = ask_change(pl)
    for lab, v in (("bot", ab), ("placebo", ap)):
        vv = v[np.isfinite(v)]
        res[f"ask_change_1s_{lab}"] = {"down": round(float((vv < -1e-6).mean()), 3), "up": round(float((vv > 1e-6).mean()), 3), "n": int(len(vv))} if len(vv) else None
    # E5 at sub-second resolution: direction of the OTHER traders' trades (websocket last-trade events, server ms) in the
    # last W ms before the bot's match, in Up terms (BUY Up / SELL Down = +1), vs the bot's side; placebo = random times
    tr2 = tr.copy()
    tr2["dirn"] = np.where(tr2.is_up == (tr2.d.str.upper() == "BUY"), 1.0, -1.0) * tr2.z.astype(float)
    by2 = {u: (g.s_ms.to_numpy(float), g.dirn.to_numpy(float)) for u, g in tr2.sort_values("s_ms").groupby("up_token")}
    def flow(x, W):
        out = []
        for u, m in zip(x.up_token, x.match_s):
            g = by2.get(u)
            if g is None:
                out.append(0.0); continue
            i0 = np.searchsorted(g[0], m - W, side="left"); i1 = np.searchsorted(g[0], m, side="left")
            out.append(float(g[1][i0:i1].sum()))
        return np.array(out)
    bot_dir = np.where(tk.is_up.to_numpy(), 1.0, -1.0)
    rnd_dir = np.where(rng.random(len(pl)) < 0.5, 1.0, -1.0)
    for W in (100, 200, 500, 1000, 2000):
        fb = flow(tk, W); fp = flow(pl, W)
        nz = fb != 0; nzp = fp != 0
        res[f"tape_flow_{W}ms_bot"] = {"agree": round(float((np.sign(fb[nz]) == bot_dir[nz]).mean()), 4) if nz.any() else None, "n_nonzero": int(nz.sum()), "n": int(len(fb))}
        res[f"tape_flow_{W}ms_placebo_random_side"] = {"agree": round(float((np.sign(fp[nzp]) == rnd_dir[nzp]).mean()), 4) if nzp.any() else None, "n_nonzero": int(nzp.sum())}
    # Why did the bought outcome's ask rise in the last second: lifted by other traders (a trade on that outcome at a
    # price >= the old ask, or on the complement at <= 1 - old ask) or repriced by makers without a trade?
    cls = {"ask_up_with_trade": 0, "ask_up_no_trade": 0, "ask_flat": 0, "ask_down": 0, "na": 0}
    for u, m, up in zip(tk.up_token, tk.match_s, tk.is_up):
        a1 = L.touch_before(books, u, m - 50, up)[0]; a0 = L.touch_before(books, u, m - 1000, up)[0]
        if not (np.isfinite(a1) and np.isfinite(a0)):
            cls["na"] += 1; continue
        if a1 < a0 - 1e-9:
            cls["ask_down"] += 1; continue
        if abs(a1 - a0) < 1e-9:
            cls["ask_flat"] += 1; continue
        g = by_mkt.get(u)
        hit = False
        if g is not None:
            gg = g[(g.s_ms >= m - 1000) & (g.s_ms < m - 50)]
            hit = bool((((gg.is_up == up) & (gg.p >= a0 - 1e-9)) | ((gg.is_up != up) & (gg.p <= 1 - a0 + 1e-9))).any())
        cls["ask_up_with_trade" if hit else "ask_up_no_trade"] += 1
    res["ask_rise_cause_last_1s"] = cls
    # Binance futures QUOTES (own recorder btc5m_bnfut, from 10-31 13:11 UTC): bookTicker mid move toward the bought side
    # over [m - W, m - 0) using the exchange event time E (the laptop clock runs ~0.8 s behind exchange/server time)
    bq = {}
    for r in L.recs("btc5m_bnfut", a - 60, b + 60):
        if r.get("k") == "b" and r.get("E"):
            bq.setdefault(r["s"], []).append((float(r["E"]), 0.5 * (r["b"] + r["a"])))
    bq = {s_: np.array(sorted(v)) for s_, v in bq.items()}
    for sym in ("BTCUSDT", "ETHUSDT"):
        q_ = bq.get(sym)
        if q_ is None or len(q_) < 10:
            continue
        cover = (tk.match_s.to_numpy() > q_[0, 0] + 5000) & (tk.match_s.to_numpy() < q_[-1, 0])
        coverp = (pl.match_s.to_numpy() > q_[0, 0] + 5000) & (pl.match_s.to_numpy() < q_[-1, 0])
        for lag0, lag1 in ((0, 250), (250, 500), (500, 1000), (0, 1000), (1000, 2000), (0, 2000)):
            for lab, x, cv in (("bot", tk, cover), ("placebo", pl, coverp)):
                mv = move_toward(q_[:, 0], None, q_[:, 1], x.match_s.to_numpy(), lag0, lag1, x.is_up.to_numpy())
                nz = cv & np.isfinite(mv) & (np.abs(mv) > 0.01)
                res[f"quote_{sym}_[{-lag1},{-lag0})ms_{lab}"] = {"agree": round(float((mv[nz] > 0).mean()), 4) if nz.any() else None, "n_moved": int(nz.sum()), "n_covered": int(cv.sum())}
    # SIZE vs the recorded ask size: does it send the large order when the touch is deep?
    if "size" in tk:
        az = np.array([L.touch_before(books, u, s - 50, up)[3] for u, s, up in zip(tk.up_token, tk.match_s, tk.is_up)])
        lg = tk["size"].to_numpy() >= 99
        res["size_vs_ask_size"] = {"n_large": int(lg.sum()), "n_small": int((~lg).sum()),
                                   "ask_size_median_large": round(float(np.nanmedian(az[lg])), 1) if lg.any() else None,
                                   "ask_size_median_small": round(float(np.nanmedian(az[~lg])), 1) if (~lg).any() else None}
    # X8: the overlapping BTC 15-minute Up/Down market (recorded in clob_crypto): did its Up mid move toward the bought
    # side in the last 1 s / 3 s before the match (placebo: random times, random sides)?
    m15 = {}
    for r in L.recs("subs", a - 3600, b):
        if r.get("feed") == "clob_crypto":
            for slug, tks in r["markets"].items():
                if slug.startswith("btc-updown-15m-"):
                    m15[tks[0]] = int(slug.rsplit("-", 1)[1])
    mid15 = {}
    for r in L.recs("clob_crypto", a, b):
        if r.get("k") in ("q", "f") and r["a"] in m15 and r["b"] and r["o"]:
            mid15.setdefault(r["a"], []).append((r["s"], 0.5 * (max(p for p, z in r["b"]) + min(p for p, z in r["o"]))))
    mid15 = {t: np.array(sorted(v), dtype=float) for t, v in mid15.items()}
    def m15_move(x, W):
        out = []
        for m, up in zip(x.match_s, x.is_up):
            best = None
            for t, st in m15.items():  # the 15m window that contains the match
                if st * 1000 <= m < (st + 900) * 1000 and t in mid15:
                    best = mid15[t]
            if best is None:
                out.append(np.nan); continue
            i1 = np.searchsorted(best[:, 0], m - 50, side="left") - 1; i0 = np.searchsorted(best[:, 0], m - W, side="left") - 1
            if i0 < 0 or i1 < 0:
                out.append(np.nan); continue
            d = best[i1, 1] - best[i0, 1]
            out.append(d if up else -d)
        return np.array(out)
    for W in (1000, 3000):
        vb = m15_move(tk, W); vp = m15_move(pl, W)
        for lab, v in (("bot", vb), ("placebo", vp)):
            nz = np.isfinite(v) & (np.abs(v) > 1e-9)
            res[f"m15_mid_move_{W}ms_{lab}"] = {"agree": round(float((v[nz] > 0).mean()), 4) if nz.any() else None, "n_moved": int(nz.sum()), "n": int(np.isfinite(v).sum())}
    # composite of the last 2 s: Binance futures + ETH moves (if any) vs tape flow, for the orders with no reference move
    # fair value vs the recorded ask at the match (E7 / B3): FV = Phi(ln(S/K) / (sigma sqrt(tau_eff))) with S = Binance futures
    # (last trade before the match), K = Chainlink 60-s TWAP at the window open (RTDS), sigma from 1-s futures returns
    from scipy.stats import norm
    tw = {}
    for r in L.recs("rtds", a - 400, b + 60):
        try:
            m = json.loads(r["m"])
        except Exception:
            continue
        if m.get("topic") == "crypto_prices_twap_sixty" and (m.get("payload") or {}).get("symbol") == "btc/usd":
            for x in m["payload"].get("data", []):
                tw[int(x["timestamp"])] = float(x["value"])
    # S = Chainlink RTDS price (same units as the strike K): the last 1-s value whose second ended before the match
    T = (cs.index.to_numpy().astype(float) + 1000.0); P = cs.to_numpy()
    sec = (cs.index.to_numpy() // 1000).astype(np.int64)
    lr = np.r_[0.0, np.diff(np.log(P))]

    def fv_edge(x):
        out = []
        for st, m, up, u in zip(x.start_ts, x.match_s, x.is_up, x.up_token):
            K = tw.get(int(st) * 1000)
            i = np.searchsorted(T, m, side="left") - 1
            if K is None or i < 120:
                out.append((np.nan, np.nan)); continue
            sig = np.std(lr[max(1, i - 300):i + 1]) + 1e-9
            tau = max(st + 300 - m / 1000.0 - 30.0, 1.0)
            fv_up = norm.cdf(np.log(P[i] / K) / (sig * np.sqrt(tau)))
            fv = fv_up if up else 1.0 - fv_up
            ask = L.touch_before(books, u, m, up)[0]
            out.append((fv, ask))
        return np.array(out)
    eb = fv_edge(tk); ep = fv_edge(pl)
    res["twap_points"] = len(tw)
    for lab, e in (("bot", eb), ("placebo", ep)):
        ok = np.isfinite(e).all(1)
        if ok.sum():
            d = e[ok, 0] - e[ok, 1]
            res[f"fv_minus_ask_{lab}"] = {"n": int(ok.sum()), "q": {str(k): round(float(np.quantile(d, k)), 3) for k in (0.1, 0.25, 0.5, 0.75, 0.9)},
                                         "share_pos": round(float((d > 0).mean()), 3), "share_gt_0.02": round(float((d > 0.02).mean()), 3)}
    return res


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    res = main(a, b, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_live_trigger_iter5.json")
    json.dump(res, open(out, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:6000])
