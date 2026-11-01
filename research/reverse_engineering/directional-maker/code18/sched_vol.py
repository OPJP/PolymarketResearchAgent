"""iteration 18, T1 = X215 (mechanics P1 / assumptions P1; pre-registered in NOTES.md 12:37 UTC 11-01): the fair's sigma
as a scheduled time-of-day profile. Profile P_d(s) = median over the previous N same-type days of the 5-min slot's 1-s
realised vol (code18/slot_rv.py). Forms: k x max(v300, P), k x P^a x v300^(1-a). Fit on BUILD 10-09..22 (Binance
stand-in posture), score once on the lot (STUDY case by case, VALIDATE aggregate) against R8c / R8."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE.parent / "code17"))
import side_sm  # noqa: E402
import inform_gate as ig  # noqa: E402
from features2 import Spot  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
HOL = {1788739200}  # 2026-09-07 Labor Day (NYSE closed)
KS = (0.8, 1.0, 1.2, 1.4, 1.7, 2.0, 2.5, 3.0)
AS = (0.25, 0.5, 0.75, 1.0)


def day_type(day):
    day = int(day)
    wd = pd.Timestamp(day, unit="s").weekday()
    return int(wd < 5 and day not in HOL)  # 1 = NYSE trading day


def profiles(T):
    """dict variant -> function(day, slot) -> P, all point in time (days strictly before `day`)."""
    T = T[T.n >= 200].copy()
    days = np.array(sorted(T.day.unique()), dtype=np.int64)
    rv = {(int(d), int(s)): float(v) for d, s, v in zip(T.day, T.slot, T.rv)}
    typ = {int(d): day_type(d) for d in days}
    typ_ny = {}
    for d in days:
        for s in range(288):
            typ_ny[(int(d), s)] = typ.get(int(d) - 86400, day_type(int(d) - 86400)) if s < 48 else typ[int(d)]
    cache = {}

    def make(N, mode):
        def P(day, slot):
            key = (N, mode, int(day), int(slot))
            if key in cache:
                return cache[key]
            ref = [int(d) for d in days if int(day) - N * 86400 <= d < int(day)]
            if mode == "pooled":
                sel = ref
            elif mode == "utc":
                t0 = day_type(day)
                sel = [d for d in ref if typ[d] == t0]
            else:
                t0 = day_type(int(day) - 86400) if slot < 48 else day_type(day)
                sel = [d for d in ref if typ_ny[(d, int(slot))] == t0]
            vals = [rv[(d, int(slot))] for d in sel if (d, int(slot)) in rv]
            v = float(np.median(vals)) if len(vals) >= 3 else np.nan
            cache[key] = v
            return v
        return P

    return {f"{mode}_N{N}": make(N, mode) for N in (28, 56) for mode in ("pooled", "utc", "ny")}


def prof_col(Pf, st):
    st = np.asarray(st, np.int64)
    day = st // 86400 * 86400
    slot = (st - day) // 300
    out = np.empty(len(st))
    memo = {}
    for i, (d, s) in enumerate(zip(day, slot)):
        k = (int(d), int(s))
        if k not in memo:
            memo[k] = Pf(*k)
        out[i] = memo[k]
    return out


def side(x, tau, sig, mid, dec, cheap):
    with np.errstate(divide="ignore", invalid="ignore"):
        f = norm.cdf(x / (sig * np.sqrt(np.maximum(tau, 1.0))))
    return np.where(dec, cheap, f > mid), f


def acc(p, y, m=None):
    m = np.ones(len(y), bool) if m is None else m
    return round(float((p == y)[m].mean()), 4) if m.any() else None


def main():
    T = pd.read_parquet(C / "it18" / "slot_rv.parquet")
    PV = profiles(T)
    # BUILD fills with the Binance stand-in posture rebuilt from spot
    a = pd.read_parquet(C / "spot_btc_1s.parquet")
    b = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    s = pd.concat([a, b]).dropna().drop_duplicates("sec").sort_values("sec")
    sp = Spot(s.sec.to_numpy(np.int64), s.px.to_numpy(float))
    F = ig.build_fills().reset_index(drop=True)
    F = F[(F.en - F.st) == 300].reset_index(drop=True)
    t = F.ts.to_numpy(np.int64) - 2
    S = sp.last(t)
    K = sp.mean(F.st.to_numpy(np.int64) - 60, F.st.to_numpy(np.int64))
    v300 = sp.sigma(t, look=300)
    tau = F.en.to_numpy(np.int64) - t
    xb = np.log(S / K)
    yb = F.y.to_numpy(bool)
    midb = F.mid_up.to_numpy(float)
    decb = np.abs(midb - 0.5) > 0.4
    cheapb = midb < 0.5
    opb = side_sm.nyse_open_window(F.st.to_numpy(), F.en.to_numpy())
    res = {"n_build": int(len(F)), "build_open_fills": int(opb.sum())}
    r8b, f8b = side(xb, tau, 1.4 * v300, midb, decb, cheapb)
    res["build_R8"] = acc(r8b, yb)
    res["build_R8c"] = acc(np.where(opb, cheapb, r8b), yb)
    res["build_trailing_k"] = {str(k): acc(side(xb, tau, k * v300, midb, decb, cheapb)[0], yb) for k in KS}
    grid = []
    profb = {}
    for vn, Pf in PV.items():
        P = prof_col(Pf, F.st.to_numpy())
        profb[vn] = P
        okp = np.isfinite(P)
        Pz = np.where(okp, P, v300)
        for k in KS:
            sig = k * np.maximum(v300, Pz)
            grid.append((vn, "max", None, k, acc(side(xb, tau, sig, midb, decb, cheapb)[0], yb)))
            for aa in AS:
                sig = k * Pz ** aa * v300 ** (1 - aa)
                grid.append((vn, "geo", aa, k, acc(side(xb, tau, sig, midb, decb, cheapb)[0], yb)))
    G = pd.DataFrame(grid, columns=["variant", "form", "a", "k", "acc"]).sort_values("acc", ascending=False)
    res["build_profile_coverage"] = {vn: round(float(np.isfinite(P).mean()), 3) for vn, P in profb.items()}
    res["build_top10"] = G.head(10).to_dict("records")
    best = G.iloc[0]
    res["chosen"] = {"variant": best.variant, "form": best.form, "a": None if pd.isna(best.a) else float(best.a), "k": float(best.k),
                     "build_S1": float(best.acc)}
    # BUILD descriptive at the chosen setting
    Pb = np.where(np.isfinite(profb[best.variant]), profb[best.variant], v300)

    def sig_of(P, v, k=float(best.k)):
        if best.form == "max":
            return k * np.maximum(v, P)
        return k * P ** float(best.a) * v ** (1 - float(best.a))
    s1b, f1b = side(xb, tau, sig_of(Pb, v300), midb, decb, cheapb)
    res["build_S1_open"] = acc(s1b, yb, opb)
    res["build_R8_open"] = acc(r8b, yb, opb)
    res["build_cheaper_open"] = acc(cheapb, yb, opb)
    # lot
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet", columns=["st", "en", "b", "is_up", "mid_up", "cl", "Kg", "tau_cl", "S", "K", "tau",
                                                                   "v300", "sp", "wallet"])
    V = V[((V.en - V.st) == 300) & np.isfinite(V.mid_up)].reset_index(drop=True)
    y = (V.is_up == 1).to_numpy()
    mid = V.mid_up.to_numpy(float)
    dec = np.abs(mid - 0.5) > 0.4
    cheap = mid < 0.5
    hascl = np.isfinite(V.cl.to_numpy(float))
    x = np.where(hascl, np.log(V.cl / V.Kg), np.log(V.S / V.K))
    tl = np.where(hascl, V.tau_cl, V.tau).astype(float)
    v = V.v300.to_numpy(float)
    P = prof_col(PV[best.variant], V.st.to_numpy())
    Pz = np.where(np.isfinite(P), P, v)
    r8, f8 = side(x, tl, 1.4 * v, mid, dec, cheap)
    op = side_sm.nyse_open_window(V.st.to_numpy(), V.en.to_numpy())
    r8c = np.where(op, cheap, r8)
    s1, f1 = side(x, tl, sig_of(Pz, v), mid, dec, cheap)
    s2 = np.where(op, cheap, s1)
    edge = np.abs(f8 - mid)
    ratio = Pz / v
    bands = {"lt0.05": edge < 0.05, "0.05-0.1": (edge >= 0.05) & (edge < 0.1), "ge0.1": edge >= 0.1}
    rb = {"r<1": ratio < 1, "1-1.5": (ratio >= 1) & (ratio < 1.5), "1.5-2.5": (ratio >= 1.5) & (ratio < 2.5), "ge2.5": ratio >= 2.5}
    for spn in ("study", "validate"):
        m = (V.sp == spn).to_numpy()
        rec = {"n": int(m.sum()), "profile_coverage": round(float(np.isfinite(P[m]).mean()), 3),
               "R8": acc(r8, y, m), "R8c": acc(r8c, y, m), "S1": acc(s1, y, m), "S2": acc(s2, y, m), "cheaper": acc(cheap, y, m),
               "open": {"n": int((m & op).sum()), "R8": acc(r8, y, m & op), "R8c": acc(r8c, y, m & op), "S1": acc(s1, y, m & op)},
               "outside_open": {"n": int((m & ~op).sum()), "R8": acc(r8, y, m & ~op), "S1": acc(s1, y, m & ~op)},
               "by_edge_nondecided_outside_open": {k: {"n": int((m & bm & ~dec & ~op).sum()), "R8": acc(r8, y, m & bm & ~dec & ~op),
                                                         "S1": acc(s1, y, m & bm & ~dec & ~op), "cheaper": acc(cheap, y, m & bm & ~dec & ~op)}
                                                     for k, bm in bands.items()},
               "by_ratio_nondecided_outside_open": {k: {"n": int((m & bm & ~dec & ~op).sum()), "R8": acc(r8, y, m & bm & ~dec & ~op),
                                                          "S1": acc(s1, y, m & bm & ~dec & ~op), "cheaper": acc(cheap, y, m & bm & ~dec & ~op)}
                                                      for k, bm in rb.items()},
               "share_side_changed_vs_R8": round(float((s1 != r8)[m].mean()), 4)}
        if spn == "validate":
            mt = (int(V.b[m].min()) + int(V.b[m].max())) // 2
            h1 = m & (V.b.to_numpy() < mt)
            h2 = m & (V.b.to_numpy() >= mt)
            rec["halves"] = {"first": {"R8c": acc(r8c, y, h1), "S1": acc(s1, y, h1), "S2": acc(s2, y, h1)},
                             "second": {"R8c": acc(r8c, y, h2), "S1": acc(s1, y, h2), "S2": acc(s2, y, h2)}}
            rec["per_wallet"] = {w: {"R8c": acc(r8c, y, m & (V.wallet == w).to_numpy()), "S1": acc(s1, y, m & (V.wallet == w).to_numpy()),
                                     "S2": acc(s2, y, m & (V.wallet == w).to_numpy())} for w in sorted(V.wallet[m].unique())}
        res[spn] = rec
    vS1, vS2, vR = res["validate"]["S1"], res["validate"]["S2"], res["validate"]["R8c"]
    pick = "S1" if vS1 >= vS2 else "S2"
    res["picked_on_validate"] = pick
    res["adopt"] = bool(res["validate"][pick] >= vR + 0.005 and res["study"][pick] >= res["study"]["R8c"] - 0.01)
    res["signature_open_S1"] = bool((res["study"]["open"]["S1"] or 0) >= 0.85 and (res["validate"]["open"]["S1"] or 0) >= 0.85)
    out = HERE.parent / "results" / "iter18_sched_vol.json"
    out.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
