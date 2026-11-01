"""directional-maker iteration 14, T1-T3 (panel iter13: mechanics P1, assumptions P3, information I13-1).

One lagged-quote law for both fill classes? The side of each cluster-class post at the touch (quote unit, filled or
not) and of each filled order (per class), against the Binance USD-M bookTicker mid move before it, the Chainlink
posture (with a volatility grid) and market-only baselines.

Development block 10-31 14:00-18:00 UTC (fit 14-16, test 16-18), or any development span with dm_clob_raw + dm_bnf
(the 11-01 06-12 block: pass --tables to rebuild the post tables from dm_clob_raw first).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/lagged_quote.py 1793455200 1793469600
"""
from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import live  # noqa: E402
import cl_source  # noqa: E402

IT13 = ROOT / ".cache/re/directional-maker/it13"
RES = HERE.parent / "results"
SIZES = {62.0, 250.0, 500.0, 1000.0}


def fut_mid(h0, h1):
    """Binance USD-M bookTicker mid by Binance event ms (dm_bnf ['b',E,T,b,B,a,A])."""
    E, M = [], []
    for h in range(h0 - h0 % 3600, h1, 3600):
        try:
            for r in live.iter_live("dm_bnf", h, min(h + 3600, h1)):
                v = r.get("r")
                if v and v[0] == "b":
                    E.append(v[1]); M.append((v[3] + v[5]) / 2)
        except (zlib.error, EOFError, OSError) as e:
            print("dm_bnf read error hour", h, repr(e)[:60])
    E = np.asarray(E, np.int64); M = np.asarray(M, np.float64)
    o = np.argsort(E, kind="stable")
    return E[o], M[o]


def at(E, M, t):
    """value of the series at or before t (NaN before the first record)."""
    i = np.searchsorted(E, t, side="right") - 1
    out = np.where(i >= 0, M[np.clip(i, 0, None)], np.nan)
    return out


def sec_sigma(E, M, look):
    """sigma ($ per root second) of 1-s changes of the last mid per second over the previous `look` seconds."""
    s0, s1 = int(E[0] // 1000), int(E[-1] // 1000) + 1
    secs = np.arange(s0, s1 + 1)
    last = at(E, M, secs * 1000 + 999)
    d = np.diff(last, prepend=np.nan)
    sr = pd.Series(d, index=secs)
    sd = sr.rolling(look, min_periods=max(30, look // 2)).std().shift(1)
    return sd


def main(a, b):
    E, M = fut_mid(a - 3600, b)
    print("futures bookTicker rows", len(E))
    S = pd.read_parquet(IT13 / "sched_adds.parquet")
    S = S[(S.s >= a * 1000) & (S.s < b * 1000)].copy()
    S["p"] = S.p.round(3); S["bb"] = S.bb.round(3); S["ba"] = S.ba.round(3)
    S["mid"] = (S.bb + S.ba) / 2
    S = S.sort_values(["w", "s"], kind="stable").reset_index(drop=True)
    # the Up mid just BEFORE each add (previous add row of the window; excludes the add's own effect)
    S["mid_prev"] = S.groupby("w").mid.shift(1)
    # per-window mid series for lookups
    ser = {w: (g.s.to_numpy(np.int64), g.mid.to_numpy(float)) for w, g in S.groupby("w")}

    def pm_mid(w_arr, t_arr):
        out = np.full(len(t_arr), np.nan)
        for w in np.unique(w_arr):
            ix = np.where(w_arr == w)[0]
            s_, m_ = ser[w]
            out[ix] = at(s_, m_, t_arr[ix] - 1)  # strictly before t
        return out

    X = pd.read_parquet(IT13 / "trades.parquet")
    X = X[~X.cluster_tx].sort_values("s", kind="stable")
    X = X.drop_duplicates("h", keep="first")
    # the token whose BID was hit (0 = Up book bid hit = Up sold / 1 = Down bid hit) from the first record of the tx
    X["bid_hit_up"] = np.where(X.ai == 0, (X.d == "SELL"), (X.d == "BUY")).astype(int)
    xs = {w: (g.s.to_numpy(np.int64), g.bid_hit_up.to_numpy(float)) for w, g in X.groupby("w")}

    def last_hit(w_arr, t_arr):
        out = np.full(len(t_arr), np.nan)
        for w in np.unique(w_arr):
            if w not in xs:
                continue
            ix = np.where(w_arr == w)[0]
            s_, v_ = xs[w]
            out[ix] = at(s_, v_, t_arr[ix] - 1)
        return out

    from polyrea.workflows.updown_study import fetch_windows
    wins = sorted(set(S.w))
    raw = fetch_windows(wins)
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    print("windows", len(wins), "with strike", len(K))
    sig = {lk: sec_sigma(E, M, lk) for lk in (60, 300, 900, 3600)}
    L = 1250
    secs_needed = sorted(set(range(a - 5, b + 1)))
    clv = cl_source.cl_values(secs_needed, allow_sealed=False, fetch=True, max_requests=300)
    print("chainlink seconds", int(clv.notna().sum()), "of", len(secs_needed))

    def posture(w_arr, t_arr, mid_arr, k=1.0, look=300):
        st = pd.Series(w_arr).str.rsplit("-", n=1).str[1].astype(int).to_numpy()
        en = st + np.where(pd.Series(w_arr).str.contains("-15m-").to_numpy(), 900, 300)
        kk = pd.Series(w_arr).map(K).to_numpy(float)
        cl = clv.reindex((t_arr - L) // 1000).to_numpy(float)
        sg = sig[look].reindex(t_arr // 1000).to_numpy(float) * k
        tau = np.maximum(en - t_arr / 1000, 1.0)
        F = norm.cdf((cl - kk) / (sg * np.sqrt(tau)))
        return np.where(np.isfinite(F) & np.isfinite(mid_arr), (F > mid_arr).astype(float), np.nan), F

    out = {"span": [a, b]}
    # ---------------- T1: quote unit ----------------
    q = S[S.dz.isin(SIZES) & (((S.sd == 1) & (S.p == S.bb)) | ((S.sd == 0) & (S.p == S.ba)))].copy()
    q = q[q.mid_prev.notna()]
    t = q.s.to_numpy(np.int64); w = q.w.to_numpy(object)
    y = (q.sd == 1).to_numpy(int)
    f50 = at(E, M, t - 50)
    rows = {"n": int(len(q)), "share_up": float(y.mean())}
    q["P"], _ = posture(w, t, q.mid_prev.to_numpy(float), 1.4, 300)
    for W in (500, 1000, 2000):
        dF = f50 - at(E, M, t - W)
        q[f"dF{W}"] = dF
        q[f"dPM{W}"] = pm_mid(w, t - 50) - pm_mid(w, t - W)
    q["hit"] = last_hit(w, t)
    q["y"] = y
    q["half"] = np.where(t < (a + (b - a) // 2) * 1000, "fit", "test")
    q["size"] = q.dz

    def acc(pred, yy):
        m = np.isfinite(pred)
        return (float((pred[m] == yy[m]).mean()) if m.sum() else None, int(m.sum()))

    def t1_block(g):
        yy = g.y.to_numpy()
        r = {"n": int(len(g)), "posture_k1.4": acc(g.P.to_numpy(), yy), "bid_hit_last_trade": acc(g.hit.to_numpy(), yy)}
        for W in (500, 1000, 2000):
            dF = g[f"dF{W}"].to_numpy(); dP = g[f"dPM{W}"].to_numpy()
            for th in (0.5, 2.0, 5.0):
                mv = np.abs(dF) >= th
                fell = np.where(mv, (dF < 0).astype(float), np.nan)  # Up fell -> post on Up
                pmf = np.where(np.abs(dP) >= 0.005, (dP < 0).astype(float), np.nan)
                comb = np.where(mv, (dF < 0).astype(float), g.P.to_numpy())
                r[f"W{W}_th{th}"] = {"moving_share": float(mv.mean()), "fell_rule_on_moving": acc(fell, yy),
                                     "posture_on_moving": acc(np.where(mv, g.P.to_numpy(), np.nan), yy),
                                     "posture_on_quiet": acc(np.where(~mv, g.P.to_numpy(), np.nan), yy),
                                     "combined_all": acc(comb, yy), "pm_mid_fell_any": acc(pmf, yy)}
        return r

    out["T1_quote_unit"] = {h: t1_block(g) for h, g in q.groupby("half")}
    out["T1_quote_unit_500"] = {h: t1_block(g) for h, g in q[q.dz.isin({500.0, 1000.0})].groupby("half")}
    # ---------------- T2 / T3: filled orders ----------------
    o = pd.read_parquet(IT13 / "fills_posts.parquet")
    o = o[o.post_ms.notna() & (o.fill_ms >= a * 1000) & (o.fill_ms < b * 1000)].copy()
    o["post_ms"] = o.post_ms.astype(np.int64)
    w2 = o.w.to_numpy(object); tp = o.post_ms.to_numpy(np.int64); tf = o.fill_ms.to_numpy(np.int64)
    o["mid_post"] = pm_mid(w2, tp); o["mid_fill"] = pm_mid(w2, tf)
    o["y"] = o.is_up.astype(int)
    o["cls"] = np.where(o.post_at_touch == 1, "i", "ii")
    o["half"] = np.where(tf < (a + (b - a) // 2) * 1000, "fit", "test")
    for W in (250, 500, 1000, 2000):
        o[f"dFp{W}"] = at(E, M, tp - 50) - at(E, M, tp - W)
        o[f"dFf{W}"] = at(E, M, tf - 50) - at(E, M, tf - W)
    o["Pp"], _ = posture(w2, tp, o.mid_post.to_numpy(float), 1.4, 300)
    o["Pf"], _ = posture(w2, tf, o.mid_fill.to_numpy(float), 1.4, 300)
    o["hit_f"] = last_hit(w2, tf)
    t2 = {}
    for (h, c), g in o.groupby(["half", "cls"]):
        yy = g.y.to_numpy()
        r = {"n": int(len(g)), "posture_post": acc(g.Pp.to_numpy(), yy), "posture_fill": acc(g.Pf.to_numpy(), yy),
             "bid_hit_last_trade_fill": acc(g.hit_f.to_numpy(), yy)}
        for W in (250, 500, 1000, 2000):
            for th in (0.5, 2.0):
                dp = g[f"dFp{W}"].to_numpy(); df = g[f"dFf{W}"].to_numpy()
                mvp = np.abs(dp) >= th; mvf = np.abs(df) >= th
                r[f"post_W{W}_th{th}"] = {"moving": float(mvp.mean()),
                                          "fell": acc(np.where(mvp, (dp < 0).astype(float), np.nan), yy)}
                r[f"fill_W{W}_th{th}"] = {"moving": float(mvf.mean()),
                                          "fell": acc(np.where(mvf, (df < 0).astype(float), np.nan), yy),
                                          "combined": acc(np.where(mvf, (df < 0).astype(float), g.Pf.to_numpy()), yy)}
        t2[f"{h}_{c}"] = r
    # class-free per-fill rule (T2 proper), every (D, theta) for fit selection
    t2all = {}
    for h, g in o.groupby("half"):
        yy = g.y.to_numpy(); r = {"n": int(len(g)), "posture_fill": acc(g.Pf.to_numpy(), yy),
                                  "bid_hit_last_trade_fill": acc(g.hit_f.to_numpy(), yy)}
        for W in (250, 500, 1000, 2000):
            for th in (0.5, 1.0, 2.0, 5.0):
                df = g[f"dFf{W}"].to_numpy(); mvf = np.abs(df) >= th
                r[f"W{W}_th{th}"] = acc(np.where(mvf, (df < 0).astype(float), g.Pf.to_numpy()), yy)
        t2all[h] = r
    out["T2_per_fill_by_class"] = t2
    out["T2_per_fill_all"] = t2all
    # T3: volatility grid on the posture at the post
    t3 = {}
    for look in (60, 300, 900, 3600):
        for k in (0.5, 0.7, 1.0, 1.4, 2.0, 2.5):
            P, _ = posture(w2, tp, o.mid_post.to_numpy(float), k, look)
            for (h, c), ix in o.groupby(["half", "cls"]).indices.items():
                t3.setdefault(f"{h}_{c}", {})[f"L{look}_k{k}"] = acc(P[ix], o.y.to_numpy()[ix])
    out["T3_vol_grid_post"] = t3
    o.drop(columns=[c for c in o.columns if c in ("metadata", "builder")]).to_parquet(
        ROOT / ".cache/re/directional-maker/it14_fills_lq.parquet", index=False)
    q[["w", "s", "sd", "p", "dz", "mid_prev", "P", "dF500", "dF1000", "dF2000", "dPM500", "dPM1000", "dPM2000", "hit", "y",
       "half"]].to_parquet(ROOT / ".cache/re/directional-maker/it14_quote_unit.parquet", index=False)
    RES.mkdir(exist_ok=True)
    (RES / f"iter14_lagged_quote_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"T1": {h: {k: v for k, v in d.items() if k in ("n", "posture_k1.4", "bid_hit_last_trade", "W1000_th2.0", "W2000_th2.0")}
                             for h, d in out["T1_quote_unit"].items()}}, indent=0)[:3000])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
