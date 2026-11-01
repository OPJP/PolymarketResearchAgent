"""Examiner r1: independent recomputation of the SIDE component on the h1 lot (the frozen dc_exam14 model on the decision clock), from
the saved fills and the public HF capture row groups memoized by run_eval.py, with the examiner's own feature code written from the
documented spec (anchor X = m - 260 ms exchange time; spot book cut at X + 131 ms collector receive time; spot trades cut at X;
returns over K = 100..2000 ms; rel = (m - 180) / 1000 - start). Baselines on the same orders: market-only (favourite, underdog,
Polymarket price momentum over 1 / 3 s, the side of others' last taker BUY), own-inventory-only (buy the cluster's / the wallet's
short leg, ties half), plus side applicability (one-sided windows per wallet vs the order-count null), a within-window label
permutation null (2,000 draws) and McNemar against the best market-only baseline.
Usage: python an_side.py OUT_JSON"""
import os, sys, json, glob, time, pickle
ARGS = sys.argv[1:]
ROOT = os.getcwd(); CODE = f"{ROOT}/research/reverse_engineering/btc5m-bot/code"
import numpy as np, pandas as pd, lightgbm as lgb
from scipy import stats

EX = f"{ROOT}/.cache/exam/btc5m-bot"; AN = f"{EX}/an"; CAP = f"{EX}/capture"
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]
CUT = 1793059200
KS = (100, 250, 500, 1000, 2000)


def chunks():
    out = []
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/evaluate.json")):
        a, b = map(int, os.path.basename(os.path.dirname(p)).split("_"))
        if any(x <= a < y for x, y in LOT) or os.environ.get("EXAM_TEST"):
            out.append((a, b, os.path.dirname(p)))
    return out


def cap_rows(sub, t0_ms, t1_ms, cols):
    tcol = "exchangeTimestampMs" if sub == "polymarket" else "receivedTimestampMs"
    parts = []
    for mp in glob.glob(f"{CAP}/{sub}_*_meta.pkl"):
        day = os.path.basename(mp)[len(sub) + 1:-9]
        M = pickle.load(open(mp, "rb"))
        for i, (has, mn, mx) in enumerate(M["stats"][tcol]):
            if has and not (mx < t0_ms or mn > t1_ms):
                p = f"{CAP}/{sub}_{day}_rg{i}.parquet"
                if os.path.exists(p):
                    parts.append(pd.read_parquet(p, columns=cols))
    return pd.concat(parts, ignore_index=True) if parts else None


def before(T, X, t):
    """value of the last event strictly before t (np.searchsorted left - 1)."""
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float); o[i < 0] = np.nan
    return o


def main(out_json):
    t0 = time.time()
    mdl = lgb.Booster(model_file=f"{CODE}/model_it14_dcside_spot.txt"); FN = mdl.feature_name()
    rows = []; onesided = []
    for a, b, d in chunks():
        win = pd.read_parquet(f"{d}/windows_all.parquet"); win = win[(win.start_ts >= a) & (win.start_ts < b)]
        fills = pd.read_parquet(f"{d}/fills.parquet")
        ev = json.load(open(f"{d}/evaluate.json"))
        # side applicability per wallet (all fills of the chunk's windows)
        for w, g in fills.groupby("wallet"):
            for cid, x in g.groupby("cid"):
                onesided.append((w, cid, int(x.start_ts.iloc[0]), int(x.is_up.nunique() == 1), int(x.oh.nunique())))
        f = fills[fills.role == "T"].drop_duplicates(["tx", "wallet", "token"]).copy()
        lo, hi = (a - 70) * 1000, (b + 400) * 1000
        tr = cap_rows("polymarket", lo - 10000, hi, ["exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice", "tradeSide"])
        bt = cap_rows("btc", lo - 10000, hi, ["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "price"])
        if tr is None or bt is None:
            print("no capture", a, b, flush=True); continue
        tr["h"] = tr.transactionHash.str.lower(); tr["tokenId"] = tr.tokenId.astype(str)
        mt = tr.groupby("h").exchangeTimestampMs.min()
        f["m"] = f.tx.str.lower().map(mt)
        n_all = len(f); f = f[f.m.notna()].copy(); f["m"] = f.m.astype(np.int64)
        bk = bt[bt.type == "book"].sort_values("receivedTimestampMs", kind="stable")
        Tb = bk.receivedTimestampMs.to_numpy(np.int64)
        mic = ((bk.bidPrice * bk.askQuantity + bk.askPrice * bk.bidQuantity) / (bk.bidQuantity + bk.askQuantity)).to_numpy(float)
        mid = ((bk.bidPrice + bk.askPrice) / 2).to_numpy(float)
        td = bt[bt.type == "trade"].sort_values("exchangeTimestampMs", kind="stable")
        Tt = td.exchangeTimestampMs.to_numpy(np.int64); pt = td.price.to_numpy(float)
        m = f.m.to_numpy(np.int64); X = m - 260
        F = pd.DataFrame({"rel": (m - 180) / 1000.0 - f.start_ts.to_numpy(float)})
        for nm, S, T_, cut in (("bs_mic", mic, Tb, X + 131), ("bs_mid", mid, Tb, X + 131), ("bt", pt, Tt, X)):
            x0 = before(T_, S, cut)
            for K in KS:
                F[f"{nm}_{K}"] = ((x0 / before(T_, S, cut - K) - 1) * 1e4).astype(np.float32)
        p = mdl.predict(F[FN])
        # market-only state of the window at X from OTHERS' prints (cluster txs excluded)
        excl = set(fills.tx.str.lower())
        oth = tr[~tr.h.isin(excl)].sort_values("exchangeTimestampMs", kind="stable")
        tok = {}
        for r in win.itertuples():
            tok[str(r.up_token)] = (r.cid, True); tok[str(r.down_token)] = (r.cid, False)
        oth = oth[oth.tokenId.isin(tok)]
        oth["cid"] = oth.tokenId.map(lambda t: tok[t][0]); oth["up"] = oth.tokenId.map(lambda t: tok[t][1])
        oth["pU"] = np.where(oth.up, oth.tradePrice.astype(float), 1 - oth.tradePrice.astype(float))
        byc = {c: g for c, g in oth.groupby("cid")}
        pU0 = np.full(len(f), np.nan); pU1 = np.full(len(f), np.nan); pU3 = np.full(len(f), np.nan); lastbuy = np.full(len(f), np.nan)
        cids = f.cid.to_numpy()
        for c in np.unique(cids):
            ii = np.where(cids == c)[0]
            g = byc.get(c)
            if g is None or not len(g):
                continue
            Tg = g.exchangeTimestampMs.to_numpy(np.int64); pu = g.pU.to_numpy(float)
            pU0[ii] = before(Tg, pu, X[ii]); pU1[ii] = before(Tg, pu, X[ii] - 1000); pU3[ii] = before(Tg, pu, X[ii] - 3000)
            gb = g[g.tradeSide == "BUY"]
            if len(gb):
                lastbuy[ii] = before(gb.exchangeTimestampMs.to_numpy(np.int64), gb.up.to_numpy(float), X[ii])
        # own inventory before the order (cluster and wallet), from fills matched before m (capture ms of their tx; else block ts)
        fl = fills.copy(); fl["mm"] = fl.tx.str.lower().map(mt); fl["mm"] = np.where(fl.mm.notna(), fl.mm, fl.ts * 1000.0 - 2000)
        fl["sgn"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
        invc = np.zeros(len(f)); invw = np.zeros(len(f))
        for c in np.unique(cids):
            ii = np.where(cids == c)[0]; g = fl[fl.cid == c].sort_values("mm")
            Tm = g.mm.to_numpy(float); cs = np.r_[0.0, np.cumsum(g.sgn.to_numpy())]
            invc[ii] = cs[np.searchsorted(Tm, m[ii].astype(float), "left")]
            for w in np.unique(f.wallet.to_numpy()[ii]):
                jj = ii[f.wallet.to_numpy()[ii] == w]; gw = g[g.wallet == w]
                Tw = gw.mm.to_numpy(float); cw = np.r_[0.0, np.cumsum(gw.sgn.to_numpy())]
                invw[jj] = cw[np.searchsorted(Tw, m[jj].astype(float), "left")]
        R = pd.DataFrame({"chunk": a, "cid": cids, "wallet": f.wallet.to_numpy(), "st": f.start_ts.to_numpy(np.int64), "m": m, "up": f.is_up.to_numpy(bool),
                          "p": p, "pU0": pU0, "pU1": pU1, "pU3": pU3, "lastbuy": lastbuy, "invc": invc, "invw": invw,
                          "mic100": F.bs_mic_100.to_numpy(), "mic250": F.bs_mic_250.to_numpy(), "mic1000": F.bs_mic_1000.to_numpy(), "bt250": F.bt_250.to_numpy(),
                          "shares": f.shares.to_numpy(float), "price": f.price.to_numpy(float), "tx": f.tx.to_numpy()})
        o_ = np.lexsort((R.m.to_numpy(), R.up.to_numpy(), R.cid.astype(str).to_numpy())); gs = R.iloc[o_]
        new_ = ((gs.cid != gs.cid.shift()) | (gs.up != gs.up.shift()) | (gs.m - gs.m.shift() >= 300)).to_numpy()
        fl_ = np.zeros(len(R), bool); fl_[o_] = new_; R["first"] = fl_
        R.attrs["n_all"] = n_all
        rows.append(R)
        sd = ev.get("side_decision_clock") or {}
        print("side chunk", a, b, "orders", n_all, "matched", len(R), "mine", round(float(((p > 0.5) == R.up).mean()), 4), "evaluate", sd.get("accuracy_per_order"), sd.get("matched"), round(time.time() - t0), flush=True)
        del bt, bk, td, tr, oth
    D = pd.concat(rows, ignore_index=True)
    D.to_parquet(f"{AN}/side_orders.parquet", index=False)
    up = D.up.to_numpy(); ok = (D.p.to_numpy() > 0.5) == up
    half = D.st.to_numpy() < CUT
    def acc(x, msk=None):
        msk = np.ones(len(x), bool) if msk is None else msk
        return round(float(np.mean(x[msk])), 4) if msk.any() else None
    # baselines (accuracy with ties scored 1/2)
    def score(pred):  # pred: +1 Up, -1 Down, 0 tie
        return np.where(pred == 0, 0.5, ((pred > 0) == up).astype(float))
    fav = np.sign(np.nan_to_num(D.pU0.to_numpy() - 0.5)); und = -fav
    mom1 = np.sign(np.nan_to_num(D.pU0.to_numpy() - D.pU1.to_numpy())); mom3 = np.sign(np.nan_to_num(D.pU0.to_numpy() - D.pU3.to_numpy()))
    mom1f = np.where(mom1 == 0, fav, mom1); mom3f = np.where(mom3 == 0, fav, mom3)
    lb = np.where(np.isfinite(D.lastbuy.to_numpy()), np.where(D.lastbuy.to_numpy() > 0.5, 1, -1), 0)
    shortc = -np.sign(D.invc.to_numpy()); shortw = -np.sign(D.invw.to_numpy())
    B = {"favourite": score(fav), "underdog": score(und), "pm_momentum_1s_then_favourite": score(mom1f), "pm_momentum_3s_then_favourite": score(mom3f),
         "others_last_taker_buy_side": score(lb), "own_inventory_short_leg_cluster": score(shortc), "own_inventory_short_leg_wallet": score(shortw)}
    res = {"orders_taker_unique": int(sum(r.attrs.get("n_all", 0) for r in rows)), "orders_matched_to_capture": int(len(D)),
           "accuracy_per_order": acc(ok), "halves": [acc(ok, half), acc(ok, ~half)],
           "by_wallet": {w: {"acc": acc(ok, D.wallet.to_numpy() == w), "n": int((D.wallet == w).sum()),
                             "halves": [acc(ok, (D.wallet.to_numpy() == w) & half), acc(ok, (D.wallet.to_numpy() == w) & ~half)]} for w in ("GF", "XM", "DS")},
           "baselines": {k: {"acc": acc(v), "halves": [acc(v, half), acc(v, ~half)], "by_wallet": {w: acc(v, D.wallet.to_numpy() == w) for w in ("GF", "XM", "DS")}} for k, v in B.items()}}
    mk = [k for k in B if not k.startswith("own")]
    best = max(mk, key=lambda k: np.mean(B[k])); bo = max([k for k in B if k.startswith("own")], key=lambda k: np.mean(B[k]))
    res["best_market_only"] = best; res["best_own_inventory_only"] = bo
    okb = B[best] == 1.0
    b_ = int((ok & ~okb).sum()); c_ = int((~ok & okb).sum())
    res["mcnemar_vs_best_market_only_p"] = float(stats.binomtest(b_, b_ + c_, 0.5, alternative="greater").pvalue) if b_ + c_ else None
    # within-window label permutation null (2,000 draws)
    rng = np.random.default_rng(21); grp = pd.factorize(D.cid.astype(str) + "_" + D.wallet.astype(str))[0]
    order = np.argsort(grp, kind="stable"); gs = grp[order]; bounds = np.r_[0, np.flatnonzero(gs[1:] != gs[:-1]) + 1, len(gs)]
    pr = (D.p.to_numpy() > 0.5)[order]; uu = up[order]; vals = []
    for _ in range(2000):
        yy = uu.copy()
        for i0, i1 in zip(bounds[:-1], bounds[1:]):
            if i1 - i0 > 1:
                yy[i0:i1] = yy[i0:i1][rng.permutation(i1 - i0)]
        vals.append(float((pr == yy).mean()))
    v = np.array(vals)
    res["within_window_permutation_null"] = {"null_mean": round(float(v.mean()), 4), "null_max": round(float(v.max()), 4),
                                             "p_one_sided": round(float(((v >= ok.mean()).sum() + 1) / 2001), 5), "draws": 2000}
    # one-sided windows per wallet vs the order-count null P(all same side) = 2 * 0.5^n
    O = pd.DataFrame(onesided, columns=["wallet", "cid", "st", "one", "orders"])
    res["side_applicability"] = {w: {"windows": int(len(g)), "share_one_sided": round(float(g.one.mean()), 4),
                                     "order_count_null_share": round(float(np.mean(np.where(g.orders <= 1, 1.0, 2 * 0.5 ** g.orders))), 4),
                                     "halves": [round(float(g[g.st < CUT].one.mean()), 4) if (g.st < CUT).any() else None, round(float(g[g.st >= CUT].one.mean()), 4) if (g.st >= CUT).any() else None]}
                                 for w, g in O.groupby("wallet")}
    # one-sided windows: side accuracy of the frozen model on them (first order of the wallet in the window)
    one_ok = {}
    for w in ("GF", "XM", "DS"):
        oo = O[(O.wallet == w) & (O.one == 1)].cid
        x = D[(D.wallet == w) & D.cid.isin(oo)].sort_values("m").drop_duplicates("cid")
        one_ok[w] = {"windows_scored": int(len(x)), "acc_first_order": round(float(((x.p > 0.5) == x.up).mean()), 4) if len(x) else None}
    res["one_sided_windows_side_acc"] = one_ok
    res["elapsed_s"] = round(time.time() - t0)
    json.dump(res, open(out_json, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:5000])


if __name__ == "__main__":
    main(ARGS[0])
