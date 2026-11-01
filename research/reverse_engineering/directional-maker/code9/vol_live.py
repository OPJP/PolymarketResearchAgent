"""Iteration 9 (X74 I8-1, X79 M1, X76 I8-3, X77 I8-4, X85 B3): the posture side on the live match clock, 10-31
12:00-18:00 UTC (development; the per-fill table of the frozen path final_rule.side_posture_match_clock, copied from the
iteration-8 information panel's run: wallet, st, en, is_up, T match ms, mid_up, K Gamma strike, cl = Chainlink report
stamped floor((T-1432)/1000)). Binance spot 1-s from the REST API. Descriptive: this block was read by the panels.
Outputs results/iter9_vol_live.json."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.signal import lfilter
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
C = ROOT / ".cache/re/directional-maker/it9"
A, B = 1793448000, 1793469600
NAMES = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
         "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "mo-money"}


def spot():
    f = C / f"spot1s_rest_{A - 7200}_{B}.parquet"
    if not f.exists():
        import final_rule as F
        rows = F._binance_rest_seconds(A - 7200, B)
        pd.DataFrame(rows, columns=["sec", "px"]).drop_duplicates("sec").to_parquet(f)
    s = pd.read_parquet(f).sort_values("sec")
    base = int(s.sec.iloc[0])
    n = int(s.sec.iloc[-1]) - base + 1
    px = np.full(n, np.nan)
    px[s.sec.astype(int).to_numpy() - base] = s.px.to_numpy()
    return base, pd.Series(px).ffill().to_numpy()


def hyst(e, win, th):
    pred = np.empty(len(e), bool)
    st_ = {}
    for i in range(len(e)):
        cur = st_.get(win[i])
        if cur is None or abs(e[i]) > th:
            cur = e[i] > 0
        st_[win[i]] = cur
        pred[i] = cur
    return pred


def main():
    D = pd.read_parquet(C / f"side_D_{A}_{B}.parquet").reset_index(drop=True)
    base, px = spot()
    r = np.r_[0.0, np.diff(np.log(px))]
    r2 = r * r
    cs = np.r_[0.0, np.cumsum(r2)]
    ti = (D["T"].to_numpy() // 1000) - 1 - base

    def rv(L):
        lo = np.maximum(ti + 1 - L, 0)
        return np.sqrt((cs[ti + 1] - cs[lo]) / np.maximum(ti + 1 - lo, 1))
    V = {f"v{L}": rv(L) for L in (120, 300, 900, 1800, 3600, 7200)}
    for hl in (300, 900, 1800, 3600):
        lam = 0.5 ** (1 / hl)
        e, _ = lfilter([1 - lam], [1, -lam], r2, zi=[lam * r2[:3600].mean()])
        V[f"e{hl}"] = np.sqrt(e[ti])
    V["cap1.0"] = np.minimum(1.4 * V["v300"], V["v3600"]) / 1.4
    tau = np.maximum(D.en.to_numpy() - D["T"].to_numpy() / 1000, 1.0)
    x = np.log(D.cl.to_numpy(float) / D.K.to_numpy(float))
    m = D.mid_up.to_numpy()
    y = D.is_up.to_numpy() == 1
    zm = norm.ppf(np.clip(m, 0.005, 0.995))
    regA = np.sign(x) == np.sign(zm)
    tsec = D["T"].to_numpy() // 1000
    slc = np.select([tsec < 1793458800, tsec < 1793464200], ["12-15", "15-1630"], "1630-18")
    fam = np.where(D.en - D.st == 900, "15m", "5m")
    ratio = V["v300"] / V["v3600"]
    out = {"n": int(len(D)), "share_regionD": float((~regA).mean())}

    def acc(sg, k=1.0, off=0.0):
        f = norm.cdf((x + off) / (k * sg * np.sqrt(tau)))
        return (f > m) == y
    ok6 = acc(V["v300"], 1.4)
    okS = acc(V["v3600"], 1.0)
    out["region"] = {"D_sigma_free": {"n": int((~regA).sum()), "acc": float(ok6[~regA].mean())},
                     "A_R6": {"n": int(regA.sum()), "acc": float(ok6[regA].mean())}, "A_v3600k1": float(okS[regA].mean()),
                     "A_always_favourite": float(np.mean(((m > 0.5) == y)[regA])),
                     "A_always_underdog": float(np.mean(((m < 0.5) == y)[regA]))}
    print("regions", out["region"])
    # interval-censored engine sigma per 10-min bin (region A)
    ia = np.where(regA)[0]
    sstar = x[ia] / (np.sqrt(tau[ia]) * zm[ia])
    fav_up = m[ia] > 0.5
    bought_fav = y[ia] == fav_up
    binid = tsec[ia] // 600
    ub = np.unique(binid)
    X = np.column_stack([np.log(sstar)] + [(binid == b_).astype(float) for b_ in ub])
    mdl = sm.Logit(bought_fav.astype(float), X).fit(disp=0, maxiter=300)
    a_ = mdl.params[0]
    path = []
    for j, b_ in enumerate(ub):
        c, se = mdl.params[j + 1], mdl.bse[j + 1]
        sel = binid == b_
        lo, hi = np.exp(-(c + 1.96 * se) / a_), np.exp(-(c - 1.96 * se) / a_)
        row = {"bin": int(b_ * 600), "n": int(sel.sum()), "sig_e": float(np.exp(-c / a_)), "lo": float(min(lo, hi)),
               "hi": float(max(lo, hi)), "fav_share": float(bought_fav[sel].mean())}
        for nm in ("v300", "v900", "v1800", "v3600", "e900", "e1800", "cap1.0"):
            row[nm] = float(np.median(V[nm][ia][sel]) * (1.4 if nm in ("v300", "cap1.0") else 1.0))
        path.append(row)
    P = pd.DataFrame(path)
    good = P[(P.n >= 15) & (P.hi / P.lo < 20)]
    cov = {}
    for nm in ("v300", "v900", "v1800", "v3600", "e900", "e1800", "cap1.0"):
        cov[nm + ("x1.4" if nm in ("v300", "cap1.0") else "")] = {
            "inside_ci": float(((good[nm] >= good.lo) & (good[nm] <= good.hi)).mean()),
            "corr_log": float(np.corrcoef(np.log(good.sig_e), np.log(good[nm]))[0, 1]),
            "median_sig_e_over_cand": float(np.median(good.sig_e / good[nm]))}
    out["sigma_e"] = {"slope_a": float(a_), "bins_used": int(len(good)), "coverage": cov, "path": P.to_dict("records")}
    print("slope", round(a_, 2), "bins", len(good))
    print(pd.DataFrame(cov).T.round(3).to_string())
    show = good[["bin", "n", "sig_e", "lo", "hi", "v300", "v3600", "e1800", "fav_share"]].copy()
    show["bin"] = pd.to_datetime(show.bin, unit="s").dt.strftime("%H:%M")
    for c_ in ("sig_e", "lo", "hi", "v300", "v3600", "e1800"):
        show[c_] = show[c_] * 1e5
    print(show.round(2).to_string(index=False))
    # per wallet, family, slice, regime
    wl = D.wallet.map(NAMES).to_numpy()
    tab = {}
    groups = [("all", np.ones(len(D), bool))] + [(f"slice {z}", slc == z) for z in ("12-15", "15-1630", "1630-18")]
    groups += [(f"fam {f_}", fam == f_) for f_ in ("5m", "15m")] + [(f"wallet {w_}", wl == w_) for w_ in NAMES.values()]
    groups += [("burst>1.5", ratio > 1.5), ("calm<0.85", ratio < 0.85)]
    okE = acc(V["e1800"])
    for lab, g in groups:
        tab[lab] = {"n": int(g.sum()), "R6": float(ok6[g].mean()), "v3600k1": float(okS[g].mean()), "e1800k1": float(okE[g].mean())}
    out["table"] = tab
    print(pd.DataFrame(tab).T.round(3).to_string())
    # B3: taker events and own-history baselines; hysteresis
    o = np.lexsort((D.wallet.to_numpy(), D["T"].to_numpy()))
    Ds = D.iloc[o].reset_index(drop=True)
    xs, ms_, ys, Ts = x[o], m[o], y[o], D["T"].to_numpy()[o]
    eS = norm.cdf(xs / (V["v3600"][o] * np.sqrt(tau[o]))) - ms_
    e6 = norm.cdf(xs / (1.4 * V["v300"][o] * np.sqrt(tau[o]))) - ms_
    key = (Ds.st.astype(str) + "_" + Ds.en.astype(str)).to_numpy()
    ev, last = [], {}
    for i in range(len(Ds)):
        k_ = key[i]
        if k_ in last and Ts[i] - last[k_][0] <= 100 and ys[i] == last[k_][1]:
            continue
        last[k_] = (Ts[i], ys[i])
        ev.append(i)
    ev = np.array(ev)
    E = pd.DataFrame({"win": key[ev], "T": Ts[ev], "y": ys[ev], "eS": eS[ev], "e6": e6[ev]})
    E["slice"] = np.select([E["T"] // 1000 < 1793458800, E["T"] // 1000 < 1793464200], ["12-15", "15-1630"], "1630-18")
    E["prev"] = E.groupby("win").y.shift(1)
    hasprev = E.prev.notna().to_numpy()
    prevb = E.prev.fillna(False).astype(bool).to_numpy()
    yy = E.y.to_numpy()
    evr = {"n_events": int(len(E)), "n_windows": int(E.win.nunique())}
    for nm in ("eS", "e6"):
        pe = E[nm].to_numpy() > 0
        evr[f"{nm}_per_event"] = float(np.mean(pe == yy))
        evr[f"{nm}_per_event_hasprev"] = float(np.mean((pe == yy)[hasprev]))
        evr[f"{nm}_per_window_mean"] = float(pd.Series(pe == yy).groupby(E.win.to_numpy()).mean().mean())
    evr["prev_event_baseline_hasprev"] = float(np.mean((prevb == yy)[hasprev]))
    fit = E.slice.to_numpy() == "12-15"
    best = None
    for th in (0.0, 0.005, 0.01, 0.02, 0.03, 0.05):
        pr = hyst(E.eS.to_numpy(), E.win.to_numpy(), th)
        a_fit = float(np.mean((pr == yy)[fit]))
        evr[f"hyst_eS_th{th}"] = {"fit_12_15": a_fit, "test_15_18": float(np.mean((pr == yy)[~fit]))}
        if best is None or a_fit > best[1]:
            best = (th, a_fit)
    evr["hyst_chosen_on_12_15"] = best[0]
    sw = hasprev & (prevb != yy)
    evr["switch_events"] = {"n": int(sw.sum()), "eS_acc": float(np.mean(((E.eS.to_numpy() > 0) == yy)[sw])),
                            "e6_acc": float(np.mean(((E.e6.to_numpy() > 0) == yy)[sw]))}
    small = np.abs(E.eS.to_numpy()) <= 0.01
    evr["small_edge_events"] = {"n": int(small.sum()), "eS_acc": float(np.mean(((E.eS.to_numpy() > 0) == yy)[small])),
                                "prev_acc": float(np.mean((prevb == yy)[small & hasprev]))}
    out["events"] = evr
    print(json.dumps(evr, indent=0))
    # I8-4: constant reference offset (dollars) per slice, slow sigma
    offs = {}
    for z in ("12-15", "15-1630", "1630-18"):
        g = slc == z
        best_ = None
        for dd in np.arange(-10, 10.5, 1.0):
            a2 = float(acc(V["v3600"], 1.0, off=dd / D.K.to_numpy(float))[g].mean())
            if best_ is None or a2 > best_[1]:
                best_ = (float(dd), a2)
        offs[z] = {"best_offset_usd": best_[0], "acc": best_[1], "acc_at_0": float(okS[g].mean())}
    out["offset"] = offs
    print("offsets", offs)
    (HERE.parent / "results" / "iter9_vol_live.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
