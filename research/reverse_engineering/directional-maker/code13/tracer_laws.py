"""X135 / X138 (panel iter12 mechanics P1, P4): fit the quote laws on the tracer re-sign prices (development block
10-31 12-18; tracer table from code13/tracers.py).

Split (pre-registered before any fit was looked at): tracer orders sorted by fill time; the earlier half of the orders
is FIT, the later half is TEST (a time split; every re-sign of an order stays with its order).
Laws for the re-sign price on the order's own token (tick 0.01, post-only cap at own ask - 0.01):
  (a)  fair cap        min(F_own - h, ask - 0.01)              F_own = Chainlink digital (report stamped (s-1432 ms)/1000,
                                                              Gamma strike, 1.4 x 300-s Binance vol, tau = end - s)
  (a2) fair cap, h by time left (tau buckets)
  (b)  mid skew        min(mid_ex + beta (F_own - mid_ex) - h, ask - 0.01)
  (c)  complement lock 1 - m - (top same-pass schedule rung of the other outcome, +-20 ms)     [own quote state]
  (e)  touch peg       bid_ex - j                                                               [market only]
  (e2) touch peg, j by age since the order's first add                                           [market only]
  anchors: bid_ex, bid_ex - 0.01, last ex-cluster trade of the own token - 0.01
Scores on TEST: share within one tick (|pred - p| <= 0.0101), MAE; per wallet; residual structure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
OUT = ROOT / ".cache/re/directional-maker/it13"
RES = HERE.parent / "results"
CL_DELAY_MS = 1432
TICK = 0.01


def spot(start, end):
    import final_rule as fr
    from polyrea.adapters.spot import binance_seconds
    from features2 import Spot
    rows, _ = binance_seconds("btc", start, end)
    have = {int(r[0]) for r in rows}
    if len(have) < 0.9 * (end - start):
        rows = list(rows) + [r for r in fr._binance_rest_seconds(start, end) if int(r[0]) not in have]
        rows.sort()
    a = np.asarray(rows, dtype=float).reshape(-1, 2)
    return Spot(a[:, 0].astype(np.int64), a[:, 1])


def build():
    from scipy.stats import norm
    import cl_source
    from polyrea.workflows.updown_study import fetch_windows
    R = pd.read_parquet(OUT / "tracer_events.parquet")
    slugs = sorted(set(R.w))
    raw = fetch_windows(slugs)
    meta = {}
    for m in raw.values():
        toks = json.loads(m.get("clobTokenIds") or "[]")
        outs = json.loads(m.get("outcomes") or "[]")
        up = 0 if (outs and str(outs[0]).lower() == "up") else 1
        ptb = None
        for e in m.get("events") or []:
            ptb = (e.get("eventMetadata") or {}).get("priceToBeat", ptb)
        meta[m["slug"]] = (str(toks[up]), str(toks[1 - up]), ptb)
    R["start"] = R.w.str.rsplit("-", n=1).str[1].astype(int)
    R["fam"] = np.where(R.w.str.contains("-15m-"), "15m", "5m")
    R["end"] = R.start + np.where(R.fam == "15m", 900, 300)
    R["up_tok"] = R.w.map(lambda s: meta.get(s, (None, None, None))[0])
    R["K"] = R.w.map(lambda s: meta.get(s, (None, None, None))[2]).astype(float)
    R["is_up"] = (R.token == R.up_tok).astype(int)
    R["side_ok"] = ((R.is_up == 1) & (R.sd == 1)) | ((R.is_up == 0) & (R.sd == 0))
    up = R.is_up == 1
    R["p_own"] = np.where(up, R.p, 1 - R.p).round(3)
    R["bid"] = np.where(up, R.bb, 1 - R.ba)
    R["ask"] = np.where(up, R.ba, 1 - R.bb)
    R["bid_ex"] = np.where(up, R.ex, 1 - R.ex)
    R["mid_ex"] = (R.bid_ex + R.ask) / 2
    stamps = sorted(set(((R.s - CL_DELAY_MS) // 1000).astype(np.int64)))
    clv = cl_source.cl_values(stamps, allow_sealed=False, fetch=True, max_requests=400)
    R["cl"] = ((R.s - CL_DELAY_MS) // 1000).map(clv)
    sp = spot(int(R.s.min() // 1000) - 7200, int(R.s.max() // 1000) + 5)
    tsec = (R.s // 1000).to_numpy()
    R["sig"] = sp.sigma(tsec, look=300) * 1.4
    R["tau"] = np.maximum(R.end.to_numpy() - R.s.to_numpy() / 1000.0, 1.0)
    fu = norm.cdf(np.log(R.cl.to_numpy(float) / R.K.to_numpy(float)) / (R.sig.to_numpy() * np.sqrt(R.tau.to_numpy())))
    R["F_up"] = fu
    R["F_own"] = np.where(up, fu, 1 - fu)
    R["spot"] = sp.last(tsec)
    # same-pass schedule rungs of the other outcome (+-20 ms) and of the same outcome
    S = pd.read_parquet(OUT / "sched_adds.parquet")
    S["own_p"] = S.p  # Up-book price; converted per tracer below
    oth_top, same_near = [], []
    for w, g in R.groupby("w"):
        sg = S[S.w == w].sort_values("s")
        ss = sg.s.to_numpy()
        for idx, r in g.iterrows():
            i0, i1 = np.searchsorted(ss, r.s - 20), np.searchsorted(ss, r.s + 21)
            m = sg.iloc[i0:i1]
            other_sd = 0 if r.sd == 1 else 1
            o = m[m.sd == other_sd]
            # the other outcome's own-token price: other = Down if tracer is Up (Down bid = Up ask at 1-p)
            if len(o):
                op = (1 - o.p) if other_sd == 0 else o.p
                oth_top.append((idx, float(op.max())))
            sm = m[m.sd == r.sd]
            if len(sm):
                spp = (sm.p if r.sd == 1 else 1 - sm.p).to_numpy()
                same_near.append((idx, float(spp[np.argmin(np.abs(spp - r.p_own))])))
    R["oth_top"] = pd.Series(dict(oth_top))
    R["same_near"] = pd.Series(dict(same_near))
    # last ex-cluster trade on the own token before the re-sign
    X = pd.read_parquet(OUT / "trades.parquet")
    X = X[~X.cluster_tx]
    lt = []
    for w, g in R.groupby("w"):
        xg = X[X.w == w].sort_values("s")
        xs = xg.s.to_numpy()
        # the trade stream reports prices on the asset ai; ai 0 = first token of the market (Up for these slugs)
        xp = np.where(xg.ai.to_numpy() == 0, xg.p.to_numpy(), 1 - xg.p.to_numpy())
        for idx, r in g.iterrows():
            i = np.searchsorted(xs, r.s, side="left") - 1
            v = xp[i] if i >= 0 else np.nan
            lt.append((idx, v if r.is_up == 1 else 1 - v))
    R["last_trade_own"] = pd.Series(dict(lt))
    R["age"] = (R.s - R.groupby("order").s.transform("min")) / 1000
    R["to_fill"] = (R.fill_ms - R.s) / 1000
    R.to_parquet(OUT / "tracer_features.parquet", index=False)
    return R


def snap(x):
    return np.round(np.asarray(x, float) / TICK) * TICK


def score(pred, y):
    e = np.abs(np.asarray(pred, float) - np.asarray(y, float))
    ok = np.isfinite(e)
    return {"n": int(ok.sum()), "within_tick": float(np.mean(e[ok] <= TICK + 1e-4)) if ok.any() else None,
            "exact": float(np.mean(e[ok] <= 1e-4)) if ok.any() else None, "mae": float(np.mean(e[ok])) if ok.any() else None}


def cap(x, ask):
    return np.minimum(snap(x), snap(ask) - TICK)


def main():
    R = build() if "--rebuild" in sys.argv or not (OUT / "tracer_features.parquet").exists() else pd.read_parquet(OUT / "tracer_features.parquet")
    R = R[R.side_ok & R.F_own.notna() & R.bid_ex.notna() & R.ask.notna()].copy()
    orders = R.groupby("order").fill_ms.first().sort_values()
    fit_orders = set(orders.index[: len(orders) // 2])
    R["fit"] = R.order.isin(fit_orders)
    F, T = R[R.fit], R[~R.fit]
    y_f, y_t = F.p_own.to_numpy(), T.p_own.to_numpy()
    out = {"n_events": int(len(R)), "n_orders": int(R.order.nunique()), "fit_events": int(len(F)), "test_events": int(len(T)),
           "fit_orders": len(fit_orders), "split_ms": int(orders.iloc[len(orders) // 2]) if len(orders) > 1 else None,
           "families": R.fam.value_counts().to_dict(), "wallets": R.wallet.value_counts().to_dict(),
           "cl_coverage": float(R.cl.notna().mean())}
    hs = np.arange(-0.10, 0.40, 0.005)
    laws = {}

    def best_grid(fn, grid, X, y):
        best = None
        for g in grid:
            sc = score(fn(X, g), y)["within_tick"]
            if best is None or sc > best[1]:
                best = (g, sc)
        return best
    # (a) fair cap
    fa = lambda X, h: cap(X.F_own - h, X.ask)
    h_a, _ = best_grid(fa, hs, F, y_f)
    laws["a_fair_cap"] = {"h": float(h_a), "fit": score(fa(F, h_a), y_f), "test": score(fa(T, h_a), y_t)}
    # (a2) h by tau bucket
    bk = lambda X: np.digitize(X.tau, [30, 60, 120, 240, 600])
    h_b = {}
    for b in sorted(set(bk(F))):
        m = bk(F) == b
        h_b[int(b)] = float(best_grid(fa, hs, F[m], y_f[m])[0])
    fa2 = lambda X: cap(X.F_own - np.array([h_b.get(int(b), h_a) for b in bk(X)]), X.ask)
    laws["a2_fair_cap_tau"] = {"h_by_tau_bucket": h_b, "fit": score(fa2(F), y_f), "test": score(fa2(T), y_t)}
    # (b) mid skew
    best = None
    for beta in np.arange(0, 1.51, 0.1):
        for h in np.arange(-0.10, 0.30, 0.01):
            sc = score(cap(F.mid_ex + beta * (F.F_own - F.mid_ex) - h, F.ask), y_f)["within_tick"]
            if best is None or sc > best[2]:
                best = (beta, h, sc)
    bb_, hb_ = best[0], best[1]
    fb = lambda X: cap(X.mid_ex + bb_ * (X.F_own - X.mid_ex) - hb_, X.ask)
    laws["b_mid_skew"] = {"beta": float(bb_), "h": float(hb_), "fit": score(fb(F), y_f), "test": score(fb(T), y_t)}
    # (c) complement lock against the other outcome's same-pass top rung (own quote state)
    Fc, Tc = F[F.oth_top.notna()], T[T.oth_top.notna()]
    fc = lambda X, m: cap(1 - m - X.oth_top, X.ask)
    if len(Fc):
        m_c, _ = best_grid(fc, np.arange(-0.05, 0.30, 0.005), Fc, Fc.p_own.to_numpy())
        laws["c_complement_lock"] = {"m": float(m_c), "coverage": float(R.oth_top.notna().mean()), "fit": score(fc(Fc, m_c), Fc.p_own),
                                     "test": score(fc(Tc, m_c), Tc.p_own) if len(Tc) else None}
    # (e) touch peg
    fe = lambda X, j: snap(X.bid_ex - j)
    j_e, _ = best_grid(fe, np.arange(-0.05, 0.30, 0.01), F, y_f)
    laws["e_touch_peg"] = {"j": float(j_e), "fit": score(fe(F, j_e), y_f), "test": score(fe(T, j_e), y_t)}
    ab = lambda X: np.digitize(X.age, [1, 3, 10, 30, 60])
    j_b = {int(b): float(best_grid(fe, np.arange(-0.05, 0.30, 0.01), F[ab(F) == b], y_f[ab(F) == b])[0]) for b in sorted(set(ab(F)))}
    fe2 = lambda X: snap(X.bid_ex - np.array([j_b.get(int(b), j_e) for b in ab(X)]))
    laws["e2_touch_peg_age"] = {"j_by_age_bucket": j_b, "fit": score(fe2(F), y_f), "test": score(fe2(T), y_t)}
    tb = lambda X: np.digitize(X.to_fill, [0.5, 1, 3, 10, 30])
    # anchors
    laws["anchor_bid_ex"] = {"test": score(snap(T.bid_ex), y_t), "fit": score(snap(F.bid_ex), y_f)}
    laws["anchor_bid_ex_minus_tick"] = {"test": score(snap(T.bid_ex) - TICK, y_t)}
    laws["anchor_last_trade_minus_tick"] = {"test": score(snap(T.last_trade_own) - TICK, y_t)}
    out["laws"] = laws
    # residual structure of the best public law on all events
    best_law = max(["a_fair_cap", "a2_fair_cap_tau", "b_mid_skew"], key=lambda k: laws[k]["test"]["within_tick"] or 0)
    pred_all = {"a_fair_cap": fa(R, h_a), "a2_fair_cap_tau": fa2(R), "b_mid_skew": fb(R)}[best_law]
    res = R.p_own.to_numpy() - pred_all
    R["res"] = res
    ac = []
    for o, g in R.sort_values("s").groupby("order"):
        if len(g) > 3:
            v = g.res.to_numpy()
            if np.std(v[:-1]) > 0 and np.std(v[1:]) > 0:
                ac.append(np.corrcoef(v[:-1], v[1:])[0, 1])
    out["best_public_law"] = best_law
    out["residual"] = {"mean": float(np.nanmean(res)), "sd": float(np.nanstd(res)), "lag1_autocorr_median": float(np.median(ac)) if ac else None,
                       "by_distance_to_fill": {str(k): float(np.nanmean(np.abs(res[tb(R) == k]))) for k in sorted(set(tb(R)))},
                       "corr_with_edge": float(np.corrcoef(res[np.isfinite(res)], (R.F_own - R.mid_ex).to_numpy()[np.isfinite(res)])[0, 1]),
                       "corr_with_tau": float(np.corrcoef(res[np.isfinite(res)], R.tau.to_numpy()[np.isfinite(res)])[0, 1])}
    # where the tracer sits: distance to its own ex-tracer touch, by time to fill
    R["rel_ex"] = R.p_own - R.bid_ex
    out["rel_to_touch_by_time_to_fill"] = {str(k): {"n": int((tb(R) == k).sum()), "median": float(R.rel_ex[tb(R) == k].median()),
                                                     "share_at_or_above": float((R.rel_ex[tb(R) == k] >= -1e-6).mean())} for k in sorted(set(tb(R)))}
    out["edge_vs_rel"] = {"corr(F_own - bid_ex, rel_ex)": float(np.corrcoef((R.F_own - R.bid_ex), R.rel_ex)[0, 1])}
    # per wallet (P4): the best public law re-fit per wallet on FIT, scored on TEST
    pw = {}
    for wname, g in R.groupby("wallet"):
        gf, gt = g[g.fit], g[~g.fit]
        if len(gf) < 20 or len(gt) < 10:
            pw[wname] = {"n": int(len(g)), "note": "too few events"}
            continue
        hw, _ = best_grid(fa, hs, gf, gf.p_own.to_numpy())
        pw[wname] = {"n": int(len(g)), "h": float(hw), "test_own_h": score(fa(gt, hw), gt.p_own), "test_pooled_h": score(fa(gt, h_a), gt.p_own)}
    out["per_wallet_fair_cap"] = pw
    RES.mkdir(exist_ok=True)
    (RES / "iter13_tracer_laws.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()
