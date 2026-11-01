"""Iteration 14 (PRE-REGISTRATION 5, X125 = X135): exam route of the DECISION-CLOCK side re-anchored on EXCHANGE time, imported by
final_rule.evaluate(). It replaces dc_exam13 (whose anchor a = m - 180 ms on the collector receive clock cut the trigger's last
50-60 ms; dc_exam13's model is still scored here on the same orders for comparison, as 'old_anchor_it13').

For every cluster taker order (fills role T, one per (tx, wallet, token)) the matching-engine ms m is read from the public CC0 capture
Fahri-5/updown-5m-polymarket-raw (revision pinned in dc_exam13.REV; trade rows, minimum exchangeTimestampMs by transactionHash).
Anchor (physics, fixed before fitting): X = m - C_EX_MS, C_EX_MS = 150 (taker delay) + 105 (Binance -> London) + 5 (reaction) = 260 ms
on exchange time; the capture's Binance spot book (collector receive clock) is cut at X + TRANSIT_MS (131 ms, the capture's median
spot-trade transit). Features: spot-book microprice and mid returns over [X + 131 - K, X + 131), spot-trade last-price returns over
[X - K, X) by exchangeTimestampMs, K = 100 / 250 / 500 / 1000 / 2000 ms, and rel = (m - 180) / 1000 - start_ts. Frozen model:
model_it14_dcside_spot.txt (LightGBM, dcside13 PARAMS / ROUNDS, fitted on the 10-17..19 operator taker orders). VALIDATE 10-20..22,
scored once: 83.7% per order (DS 83.1 / GF 85.5 / XM 81.3%), 82.4% per decision (every leg at its event's first-leg anchor), XM
one-sided windows 84.3%; placebo anchors m -/+ 3 s 49.9 / 50.0%; market-only (Polymarket trades) 56.8%; old anchor 74.2%.
Development runs never open a capture day file that starts at or after H; only the examiner's driver (allow_sealed=True) does."""
import os, time
import numpy as np, pandas as pd

import dc_exam13 as _d13

H = 1792713600
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_it14_dcside_spot.txt")
KS = (100, 250, 500, 1000, 2000)
C_EX_MS = 260
TRANSIT_MS = 131
REL_LAG_MS = 180


def globex_open_ms(ms) -> np.ndarray:
    """Iteration 19 (reporting only; the rule is unchanged): True where CME Globex is open at UTC ms, from the public CME calendar on
    Chicago local time (CDT = UTC-5 from 2026-03-08 08:00 UTC to 2026-11-01 07:00 UTC, CST = UTC-6 otherwise): closed on Saturday,
    Friday from 16:00, Sunday before 17:00 and the Mon-Thu daily break 16:00-17:00 local. Holidays are not modelled."""
    ms = np.asarray(ms, np.int64)
    off = np.where((ms >= 1772956800000) & (ms < 1793516400000), -5, -6).astype(np.int64)
    t = pd.to_datetime(ms + off * 3600000, unit="ms")
    wd, h = t.day_of_week.to_numpy(), t.hour.to_numpy()
    closed = (wd == 5) | ((wd == 4) & (h >= 16)) | ((wd == 6) & (h < 17)) | ((wd <= 3) & (h == 16))
    return ~closed


def _atl(T, X, tt):
    i = np.searchsorted(T, tt, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def _rets(T, S, cut):
    x0 = _atl(T, S, cut)
    return {K: ((x0 / _atl(T, S, cut - K) - 1) * 1e4).astype(np.float32) for K in KS}


def features(m: np.ndarray, start_ts: np.ndarray, Tb, mic, mid, Tt, pt) -> pd.DataFrame:
    X = np.asarray(m, np.int64) - C_EX_MS
    F = pd.DataFrame({"rel": (np.asarray(m, np.int64) - REL_LAG_MS) / 1000.0 - np.asarray(start_ts, float)})
    for nm, S in (("bs_mic", mic), ("bs_mid", mid)):
        for K, v in _rets(Tb, S, X + TRANSIT_MS).items():
            F[f"{nm}_{K}"] = v
    for K, v in _rets(Tt, pt, X).items():
        F[f"bt_{K}"] = v
    return F


def decision_clock_side(fills: pd.DataFrame, start_ts: int, end_ts: int, allow_sealed: bool = False) -> dict | None:
    """Segment-wise (<= 6 h of window starts per pass; only row groups overlapping each segment are read, so a lot's other days are
    never opened beyond their footers, and memory stays bounded)."""
    import httpx, lightgbm as lgb
    import dc_hazard14 as _hz
    if fills is None or not len(fills):
        return None
    f0 = fills[fills.role == "T"].drop_duplicates(["tx", "wallet", "token"]).copy()
    if not len(f0):
        return None
    cl = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "research-exam-route"})
    mdl = lgb.Booster(model_file=MODEL); FN = mdl.feature_name()
    try:
        mo = lgb.Booster(model_file=_d13.MODEL)
    except Exception:  # pragma: no cover
        mo = None
    parts, days_read = [], []
    for ws in _hz.segments(f0.start_ts.to_numpy()):
        f = f0[f0.start_ts.isin(ws)].copy()
        tr, bt, days = _hz.read_segment(cl, ws, allow_sealed, ["eventType", "exchangeTimestampMs", "transactionHash"],
                                        ["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "price"], pre_ms=8000, post_ms=310000)
        days_read += [d for d in days if d not in days_read]
        if tr is None or bt is None or not len(bt) or not len(f):
            continue
        mt = tr.assign(h=tr.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min(); del tr
        f["m"] = f.tx.str.lower().map(mt)
        f = f[f.m.notna()].copy()
        if not len(f):
            continue
        bk = bt[bt.type == "book"].sort_values("receivedTimestampMs", kind="stable")
        Tb = bk.receivedTimestampMs.to_numpy(np.int64)
        mic = ((bk.bidPrice * bk.askQuantity + bk.askPrice * bk.bidQuantity) / (bk.bidQuantity + bk.askQuantity)).to_numpy(float)
        mid = ((bk.bidPrice + bk.askPrice) / 2).to_numpy(float)
        td = bt[bt.type == "trade"].sort_values("exchangeTimestampMs", kind="stable")
        Tt = td.exchangeTimestampMs.to_numpy(np.int64) if len(td) else np.zeros(1, np.int64)
        pt = td.price.to_numpy(float) if len(td) else np.full(1, np.nan)
        del bk, td, bt
        m = f.m.to_numpy(np.int64); st = f.start_ts.to_numpy(np.int64); upv = f.is_up.to_numpy(bool)
        g = pd.DataFrame({"cid": f.cid.to_numpy(), "up": upv.astype(int), "m": m}).reset_index(drop=True)
        o = np.lexsort((g.m.to_numpy(), g.up.to_numpy(), g.cid.astype(str).to_numpy()))
        gs = g.iloc[o].reset_index()
        new = (gs.cid != gs.cid.shift()) | (gs.up != gs.up.shift()) | (gs.m - gs.m.shift() >= 300)
        gs["m0"] = gs.m.where(new).ffill().astype(np.int64)
        m0 = np.empty(len(g), np.int64); m0[gs["index"].to_numpy()] = gs.m0.to_numpy()
        first = np.zeros(len(g), bool); first[gs["index"].to_numpy()] = new.to_numpy()
        P = {"cid": f.cid.to_numpy(), "wallet": f.wallet.to_numpy(), "up": upv, "st": st, "first": first, "m": m,
             "p": mdl.predict(features(m, st, Tb, mic, mid, Tt, pt)[FN]), "pdc": mdl.predict(features(m0, st, Tb, mic, mid, Tt, pt)[FN])}
        for nm, sh in (("plm", -3000), ("plp", 3000)):
            Xp = features(m + sh, st, Tb, mic, mid, Tt, pt); Xp["rel"] = Xp.rel + sh / 1000.0
            P[nm] = mdl.predict(Xp[FN])
        if mo is not None:
            a = m - _d13.DECISION_LAG_MS
            Xo = pd.DataFrame({"rel": a / 1000.0 - st.astype(float)})
            for nm, S in (("mic", mic), ("mid", mid)):
                x0 = _d13._at(Tb, S, a)
                for K in KS:
                    r = (x0 / _d13._at(Tb, S, a - K) - 1) * 1e4
                    r[(a - K < Tb[0])] = np.nan
                    Xo[f"bs_{nm}_{K}"] = r.astype(np.float32)
            P["po"] = mo.predict(Xo[mo.feature_name()])
        else:
            P["po"] = np.full(len(m), np.nan)
        parts.append(pd.DataFrame(P))
        del Tb, mic, mid, Tt, pt
    n_all = len(f0)
    if not parts:
        return {"orders": int(n_all), "matched": 0, "days_read": days_read}
    Dd = pd.concat(parts, ignore_index=True)
    up = Dd.up.to_numpy(bool); wal = Dd.wallet.to_numpy(); st = Dd.st.to_numpy(np.int64); first = Dd["first"].to_numpy(bool)
    p = Dd.p.to_numpy(); ok = (p > 0.5) == up; okd = (Dd.pdc.to_numpy() > 0.5) == up
    out = {"model": os.path.basename(MODEL), "anchor_exchange_ms_before_match": C_EX_MS, "orders": int(n_all), "matched": int(len(Dd)),
           "match_coverage": round(len(Dd) / n_all, 4), "days_read": days_read, "accuracy_per_order": round(float(ok.mean()), 4),
           "by_wallet": {w: [round(float(ok[wal == w].mean()), 4), int((wal == w).sum())] for w in ("DS", "GF", "XM") if (wal == w).any()}}
    out["accuracy_per_decision"] = round(float(okd.mean()), 4)
    out["accuracy_first_legs"] = round(float(ok[first].mean()), 4) if first.any() else None
    out["by_wallet_per_decision"] = {w: round(float(okd[wal == w].mean()), 4) for w in ("DS", "GF", "XM") if (wal == w).any()}
    us = np.unique(st); mid_st = us[len(us) // 2] if len(us) else 0
    out["halves"] = {"first": round(float(ok[st < mid_st].mean()), 4) if (st < mid_st).any() else None, "second": round(float(ok[st >= mid_st].mean()), 4) if (st >= mid_st).any() else None}
    out["halves_by_wallet"] = {w: [round(float(ok[(st < mid_st) & (wal == w)].mean()), 4) if ((st < mid_st) & (wal == w)).any() else None,
                                   round(float(ok[(st >= mid_st) & (wal == w)].mean()), 4) if ((st >= mid_st) & (wal == w)).any() else None] for w in ("DS", "GF", "XM")}
    out["placebo_m_minus_plus_3s"] = [round(float(((Dd.plm.to_numpy() > 0.5) == up).mean()), 4), round(float(((Dd.plp.to_numpy() > 0.5) == up).mean()), 4)]
    out["old_anchor_it13"] = round(float(((Dd.po.to_numpy() > 0.5) == up).mean()), 4) if np.isfinite(Dd.po.to_numpy()).any() else None
    try:  # iteration 19 (reporting only): accuracy by CME Globex session (X191; VALIDATE 10-20..22 closed 0.861 vs open 0.836)
        gx = globex_open_ms(Dd.m.to_numpy(np.int64))
        out["by_globex_session"] = {nm: [round(float(ok[mk].mean()), 4), int(mk.sum())] if mk.any() else [None, 0] for nm, mk in (("open", gx), ("closed", ~gx))}
        out["by_globex_session_by_wallet"] = {w: {nm: round(float(ok[mk & (wal == w)].mean()), 4) if (mk & (wal == w)).any() else None for nm, mk in (("open", gx), ("closed", ~gx))}
                                              for w in ("DS", "GF", "XM")}
    except Exception as e:  # pragma: no cover
        out["by_globex_session_error"] = repr(e)[:200]
    f = Dd.rename(columns={"wallet": "w"})
    gw = pd.DataFrame({"cid": f.cid.to_numpy(), "w": wal, "up": up.astype(int), "p": p, "st": st})
    one = {}
    for w in ("DS", "GF", "XM"):
        x = gw[gw.w == w].groupby("cid").agg(up=("up", "mean"), p=("p", "mean"), st=("st", "first"))
        if len(x):
            o1 = x[(x.up == 0) | (x.up == 1)]
            okw = (o1.p > 0.5).astype(int) == o1.up.astype(int)
            one[w] = {"windows": int(len(x)), "one_sided_share": round(float(len(o1) / len(x)), 4),
                      "one_sided_window_side_acc": round(float(okw.mean()), 4) if len(o1) else None,
                      "one_sided_window_side_acc_halves": [round(float(okw[o1.st < mid_st].mean()), 4) if (o1.st < mid_st).any() else None,
                                                           round(float(okw[o1.st >= mid_st].mean()), 4) if (o1.st >= mid_st).any() else None]}
    out["one_sided_windows"] = one
    return out
