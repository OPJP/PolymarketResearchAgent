"""Iteration 14 (X126 = X136 compact form, and PRE-REGISTRATION 7; NOTES iteration 14 findings 8 and 10): exam routes of the
DECISION-CLOCK TAKE HAZARD, imported by final_rule.evaluate():
  - decision_clock_presence(): reported component 'presence_decision_clock' (VALIDATE-only, not a pre-registered target metric);
  - hazard_imbalance(): the per-second hazard imbalance h(s) used by the adopted PnL tracker target mix14 (pre-registration 7).

Unit: 50-ms bins on the exchange-equivalent clock for every (window, outcome), bin ends e = start + 50 k (k = 1 .. 5400, i.e.
[0, 270) s). Label: a cluster FIRST leg (the first taker order of an event: same window and outcome, < 300 ms after the previous
order) whose capture match ms m0 lies in [e + 205, e + 255). Features (all published before the order arrived at m0 - 150): the
Binance spot book from the public capture (receive - 131) and spot trades (exchange ms) ending at e; others' Polymarket prints
(capture server ms, cluster txs excluded) ending at e + 50; rel. Frozen LightGBM models model_it14_hazard_full.txt and its
market-only baseline model_it14_hazard_pm_only.txt (fitted on 10-17..19). VALIDATE 10-20..22 (scored once): weighted AUC 0.8885 vs
0.7591 (gain +0.129, 2-h block CI [0.122, 0.137]); the reverse split (fit 10-20..22, score 10-17..19) 0.925 vs 0.781. Negatives
are sampled at 1% with a fixed seed (weight 100). h(s) = sum over ALL bins with end e in [s - 2, s - 1) s of P^(Up) - P^(Down).
W4 / W5 prints are not excluded here (no list inside evaluate; 0.7% of non-cluster prints).
Data access: one pass over segments of at most 6 hours built from the evaluated windows' start times; each capture day file is read
only for the row groups overlapping a segment (so a lot's other days are never read), and memory stays bounded per segment.
Development runs never open a capture day file that starts at or after H."""
import os, time
import numpy as np, pandas as pd

import dc_exam13 as _d13

H = 1792713600
CODE = os.path.dirname(os.path.abspath(__file__))
MODEL_FULL = f"{CODE}/model_it14_hazard_full.txt"
MODEL_PM = f"{CODE}/model_it14_hazard_pm_only.txt"
NEG = 0.01
HAZ_C = 5.935  # pre-registration 7: no-intercept OLS (10-17..19) of the operator per-second signed flow on the hazard imbalance h
SP = [f"sp_r{K}" for K in (50, 100, 250, 500, 1000, 3000)] + ["sp_mid100", "sp_mid250", "sp_nupd250", "sp_flow250", "sp_flow1000"]
PM = ["pm_last", "pm_d1", "pm_d5", "pm_bo1", "pm_bo3", "pm_bx1", "pm_bx3", "pm_dist", "rel"]
SEG_S = 6 * 3600
_CACHE = {}


def _at(T, X, t):
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def segments(starts, seg_s: int = SEG_S):
    """Window start times -> list of arrays of starts, each spanning at most seg_s seconds."""
    st = np.unique(np.asarray(starts, np.int64))
    out, cur = [], []
    for s in st:
        if cur and s - cur[0] >= seg_s:
            out.append(np.array(cur)); cur = []
        cur.append(s)
    if cur:
        out.append(np.array(cur))
    return out


def read_segment(cl, ws, allow_sealed, pm_cols, bt_cols, pre_ms=6000, post_ms=310000):
    """Capture rows for windows starting in ws: Polymarket trade rows over [min - pre, max + post] ms and Binance rows likewise. The
    Polymarket day file of day D covers 00:00-23:00 server time of D (hour 23 is in D + 1), so the files of every day the range
    touches are opened, but only their row groups overlapping the range are read."""
    t0, t1 = int(ws.min()) * 1000 - pre_ms, int(ws.max()) * 1000 + post_ms
    trs, bts, days = [], [], []
    for d0 in range((t0 // 1000 // 86400) * 86400, ((t1 // 1000 + 3600) // 86400) * 86400 + 1, 86400):  # D + 1 only when the range reaches D's hour 23
        if d0 + 86400 > H and not allow_sealed:
            continue
        day = time.strftime("%Y-%m-%d", time.gmtime(d0))
        t = _d13._read(cl, "polymarket", day, pm_cols, "exchangeTimestampMs", t0, t1)
        if t is not None and len(t):
            trs.append(t[t.eventType == "last_trade_price"].drop(columns=["eventType"])); days.append(day)
        b = _d13._read(cl, "btc", day, bt_cols, "receivedTimestampMs", t0, t1)
        if b is not None and len(b):
            bts.append(b)
    tr = pd.concat(trs, ignore_index=True) if trs else None
    bt = pd.concat(bts, ignore_index=True) if bts else None
    return tr, bt, days


def _spot(bt):
    bk = bt[bt.type == "book"]; td = bt[bt.type == "trade"]
    Tb = bk.receivedTimestampMs.to_numpy(np.int64) - 131
    mic = ((bk.bidPrice * bk.askQuantity + bk.askPrice * bk.bidQuantity) / (bk.bidQuantity + bk.askQuantity)).to_numpy(float)
    mid = ((bk.bidPrice + bk.askPrice) / 2).to_numpy(float)
    o = np.argsort(Tb, kind="stable"); Tb, mic, mid = Tb[o], mic[o], mid[o]
    Tt = td.exchangeTimestampMs.to_numpy(np.int64); qq = td.quantity.to_numpy(float); bm = td.isBuyerMaker.astype(bool).to_numpy()
    o = np.argsort(Tt, kind="stable"); Tt = Tt[o]; cf = np.concatenate([[0.0], np.cumsum(np.where(bm[o], -1.0, 1.0) * qq[o])])
    return Tb, mic, mid, Tt, cf


def _feats(r, up, ee, Tb, mic, mid, Tt, cf, byt):
    sg = 1.0 if up == 1 else -1.0
    F = {"rel": ee / 1000.0 - r.start_ts}
    x0 = _at(Tb, mic, ee)
    for K in (50, 100, 250, 500, 1000, 3000):
        F[f"sp_r{K}"] = (x0 / _at(Tb, mic, ee - K) - 1) * 1e4 * sg
    y0 = _at(Tb, mid, ee)
    for K in (100, 250):
        F[f"sp_mid{K}"] = (y0 / _at(Tb, mid, ee - K) - 1) * 1e4 * sg
    F["sp_nupd250"] = (np.searchsorted(Tb, ee, "left") - np.searchsorted(Tb, ee - 250, "left")).astype(float)
    for K in (250, 1000):
        F[f"sp_flow{K}"] = (cf[np.searchsorted(Tt, ee, "left")] - cf[np.searchsorted(Tt, ee - K, "left")]) * sg
    to, tx = (str(r.up_token), str(r.down_token)) if up == 1 else (str(r.down_token), str(r.up_token))
    cut = ee + 50
    for k in ("pm_last", "pm_d1", "pm_d5", "pm_bo1", "pm_bo3", "pm_bx1", "pm_bx3"):
        F[k] = np.full(len(ee), np.nan)
    if to in byt:
        Tg, pr, sd = byt[to]
        l0 = _at(Tg, pr, cut); F["pm_last"] = l0; F["pm_d1"] = l0 - _at(Tg, pr, cut - 1000); F["pm_d5"] = l0 - _at(Tg, pr, cut - 5000)
        Tbu = Tg[sd == "BUY"]
        F["pm_bo1"] = (np.searchsorted(Tbu, cut, "left") - np.searchsorted(Tbu, cut - 1000, "left")).astype(float)
        F["pm_bo3"] = (np.searchsorted(Tbu, cut, "left") - np.searchsorted(Tbu, cut - 3000, "left")).astype(float)
    if tx in byt:
        Tg, pr, sd = byt[tx]; Tbu = Tg[sd == "BUY"]
        F["pm_bx1"] = (np.searchsorted(Tbu, cut, "left") - np.searchsorted(Tbu, cut - 1000, "left")).astype(float)
        F["pm_bx3"] = (np.searchsorted(Tbu, cut, "left") - np.searchsorted(Tbu, cut - 3000, "left")).astype(float)
    F["pm_dist"] = np.abs(F["pm_last"] - 0.5)
    return F


def _run(fills, win, start_ts, end_ts, allow_sealed):
    """One pass: sampled presence rows (with labels) and the full per-second hazard imbalance h, segment by segment."""
    key = (int(start_ts), int(end_ts), bool(allow_sealed), int(len(fills)) if fills is not None else 0, int(len(win)))
    if key in _CACHE:
        return _CACHE[key]
    import httpx, lightgbm as lgb
    cl = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "research-exam-route"})
    mf, mp = lgb.Booster(model_file=MODEL_FULL), lgb.Booster(model_file=MODEL_PM)
    FN, FP = mf.feature_name(), mp.feature_name()
    W = win[(win.start_ts >= start_ts) & (win.start_ts < end_ts)].sort_values("start_ts")
    excl = set(fills.tx.str.lower()) if fills is not None and len(fills) else set()
    f_all = fills[fills.role == "T"].drop_duplicates(["tx", "wallet", "token"]) if fills is not None and len(fills) else None
    rng = np.random.default_rng(14)
    rows, hs, days_read, n_first = [], [], [], 0
    for ws in segments(W.start_ts.to_numpy()):
        tr, bt, days = read_segment(cl, ws, allow_sealed, ["eventType", "exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice", "tradeSide"],
                                    ["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "quantity", "isBuyerMaker"])
        days_read += [d for d in days if d not in days_read]
        if tr is None or bt is None or not len(bt):
            continue
        tr["h"] = tr.transactionHash.str.lower(); tr["tokenId"] = tr.tokenId.astype(str)
        Tb, mic, mid, Tt, cf = _spot(bt); del bt
        pos, posw = {}, {w: {} for w in ("DS", "GF", "XM")}
        if f_all is not None:
            mt = tr.groupby("h").exchangeTimestampMs.min()
            f = f_all[f_all.start_ts.isin(ws)].copy(); f["m"] = f.tx.str.lower().map(mt)
            f = f[f.m.notna()].copy()
            if len(f):
                f["m"] = f.m.astype(np.int64)
                f = f.sort_values(["cid", "is_up", "m"], kind="stable").reset_index(drop=True)
                new = (f.cid != f.cid.shift()) | (f.is_up != f.is_up.shift()) | (f.m - f.m.shift() >= 300)
                first = f[new.to_numpy()]; n_first += len(first)
                pos = {(c, int(u)): np.sort(g.m.to_numpy(np.int64)) for (c, u), g in first.groupby(["cid", "is_up"])}
                posw = {w: {(c, int(u)): np.sort(g.m.to_numpy(np.int64)) for (c, u), g in first[first.wallet == w].groupby(["cid", "is_up"])} for w in ("DS", "GF", "XM")}
        t2 = tr[~tr.h.isin(excl)].sort_values("exchangeTimestampMs", kind="stable")
        byt = {k: (g.exchangeTimestampMs.to_numpy(np.int64), g.tradePrice.to_numpy(float), g.tradeSide.to_numpy()) for k, g in t2.groupby("tokenId")}
        del tr, t2
        for r in W[W.start_ts.isin(ws)].itertuples():
            st = int(r.start_ts) * 1000; ee = st + 50 * np.arange(1, 5401)
            ps = {}
            for up in (1, 0):
                F = _feats(r, up, ee, Tb, mic, mid, Tt, cf, byt)
                Xf = np.column_stack([F[k] for k in FN])
                ps[up] = mf.predict(Xf)
                mm = pos.get((r.cid, up)); y = np.zeros(len(ee), np.int8)
                if mm is not None and len(mm):
                    y = (np.searchsorted(mm, ee + 255, "left") > np.searchsorted(mm, ee + 205, "left")).astype(np.int8)
                keep = (y == 1) | (rng.random(len(ee)) < NEG)
                if keep.any():
                    R_ = {"cid": np.full(keep.sum(), r.cid, object), "e": ee[keep], "y": y[keep], "w": np.where(y[keep] == 1, 1.0, 1 / NEG), "pf": ps[up][keep],
                          "pp": mp.predict(np.column_stack([F[k] for k in FP])[keep])}
                    for wn in ("DS", "GF", "XM"):
                        mw = posw[wn].get((r.cid, up))
                        R_[f"y_{wn}"] = ((np.searchsorted(mw, ee + 255, "left") > np.searchsorted(mw, ee + 205, "left")).astype(np.int8)[keep]
                                         if mw is not None and len(mw) else np.zeros(keep.sum(), np.int8))
                    rows.append(pd.DataFrame(R_))
            sec = ((ee - st) // 1000 + 2).astype(np.int64)
            hh = np.bincount(sec, weights=ps[1] - ps[0], minlength=302)[:300]
            hs.append(pd.DataFrame({"cid": r.cid, "rel": np.arange(300, dtype=np.int64), "h": hh}))
        del Tb, mic, mid, Tt, cf, byt
    res = (pd.concat(rows, ignore_index=True) if rows else None, pd.concat(hs, ignore_index=True) if hs else None, days_read, n_first)
    _CACHE.clear(); _CACHE[key] = res
    return res


def hazard_imbalance(fills: pd.DataFrame, win: pd.DataFrame, start_ts: int, end_ts: int, allow_sealed: bool = False):
    """Pre-registration 7: per (window, second s) h(s) = sum over ALL 50-ms bins with end e in [s - 2, s - 1) s of P^(Up) - P^(Down);
    the tracker target is 0.5 x the frozen avg flow + 0.5 x HAZ_C x h."""
    if win is None or not len(win):
        return None
    return _run(fills, win, start_ts, end_ts, allow_sealed)[1]


def decision_clock_presence(fills: pd.DataFrame, win: pd.DataFrame, start_ts: int, end_ts: int, allow_sealed: bool = False) -> dict | None:
    from sklearn.metrics import roc_auc_score
    if fills is None or not len(fills) or win is None or not len(win):
        return None
    X, _, days_read, n_first = _run(fills, win, start_ts, end_ts, allow_sealed)
    if X is None or not len(X):
        return {"days_read": days_read, "error": "no capture rows"}
    y, w, pf, pp = X.y.to_numpy(), X.w.to_numpy(), X.pf.to_numpy(), X.pp.to_numpy()
    if y.sum() == 0 or y.sum() == len(y):
        return {"days_read": days_read, "error": "degenerate labels", "instants": int(len(X))}
    auc = lambda yy, q, ww: round(float(roc_auc_score(yy, q, sample_weight=ww)), 4)
    out = {"model": os.path.basename(MODEL_FULL), "days_read": days_read, "instants_sampled": int(len(X)), "positives": int(y.sum()),
           "first_legs_matched": int(n_first), "auc_full": auc(y, pf, w), "auc_pm_only_baseline": auc(y, pp, w)}
    out["gain"] = round(out["auc_full"] - out["auc_pm_only_baseline"], 4)
    out["by_wallet"] = {wn: {"full": auc(X[f"y_{wn}"].to_numpy(), pf, w), "pm_only": auc(X[f"y_{wn}"].to_numpy(), pp, w)} for wn in ("DS", "GF", "XM") if X[f"y_{wn}"].sum() > 0}
    W = win[(win.start_ts >= start_ts) & (win.start_ts < end_ts)]
    us = np.unique(W.start_ts.to_numpy()); mid_st = us[len(us) // 2] if len(us) else 0
    hf = X.e.to_numpy() // 1000 < mid_st
    out["halves"] = [{"full": auc(y[m], pf[m], w[m]), "pm_only": auc(y[m], pp[m], w[m])} if 0 < y[m].sum() < m.sum() else None for m in (hf, ~hf)]
    blocks = X.e.to_numpy() // 7200000; ub = np.unique(blocks)
    if len(ub) >= 4:
        rng = np.random.default_rng(15); bidx = {b: np.where(blocks == b)[0] for b in ub}; gs = []
        for _ in range(300):
            ii = np.concatenate([bidx[b] for b in rng.choice(ub, len(ub))])
            if 0 < y[ii].sum() < len(ii):
                gs.append(roc_auc_score(y[ii], pf[ii], sample_weight=w[ii]) - roc_auc_score(y[ii], pp[ii], sample_weight=w[ii]))
        out["gain_block_ci95"] = [round(float(np.quantile(gs, 0.025)), 4), round(float(np.quantile(gs, 0.975)), 4)] if gs else None
        out["gain_one_sided_p_le_0"] = round(float(np.mean(np.array(gs) <= 0)), 4) if gs else None
    return out
