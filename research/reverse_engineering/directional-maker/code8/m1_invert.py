"""Iteration 8, panel iter7 mechanics M1 (X64): invert the engine's internal price from simultaneous quotes in two markets.

Development live block 10-31 14:06-16:30 UTC (own raw recorder, full depth, BTC 5m current + 15m current). Every second t
where both markets show cluster-class top rungs on both outcomes (highest exact-500 bid add and lowest exact-500 ask add
of the Up book in the last 1.5 s, as code6/m1_center.py): center F_m = (q_up + a_up)/2. Inverting the digital pricer
F = Phi(ln(S/K_m) / (sigma sqrt(tau_m))) with the true strike K_m (RTDS TWAP-60 stamped at the window start) and sigma =
1.4 x the 300-s futures 1-s vol gives S_hat_m. If one internal price S drives both ladders, S_hat_5m = S_hat_15m (within
a tick-equivalent) and S_hat tracks it. The same inversion of each market's own Up mid gives S_mid_m (where the market
puts S). Candidates for S: the Chainlink report (stamped floor((t - D)/1000)), the futures mid (in Chainlink units by the
trailing 300-s basis), EMAs of Chainlink, the market's own mid-implied S, and blends.
    python code8/m1_invert.py 1793455600 1793464202
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(HERE.parent / "code6"))
from pres_live import load_ref  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
SPLIT = 1793458800


def top_rungs(ev_w, T):
    gb = ev_w[(ev_w.side == 1)]
    ga = ev_w[(ev_w.side == 0)]
    mb = gb.p.to_numpy()[(gb.s.to_numpy() > T - 1500) & (gb.s.to_numpy() <= T)]
    ma = ga.p.to_numpy()[(ga.s.to_numpy() > T - 1500) & (ga.s.to_numpy() <= T)]
    if not len(mb) or not len(ma):
        return None
    return float(mb.max()), float(ma.min())


def main(a, b):
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet", columns=["s", "w", "side", "p", "d"])
    ev = ev[ev.d == 500.0]
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    # Chainlink by second (forward-filled) and EMAs on the 1-s grid
    clsec = np.arange(cls[0], cls[-1] + 1)
    clfill = clv[np.clip(np.searchsorted(cls, clsec, side="right") - 1, 0, None)]
    emas = {}
    for k in (2, 3, 5, 10):
        al = 1 - np.exp(-1 / k)
        e = np.empty_like(clfill)
        e[0] = clfill[0]
        for i in range(1, len(e)):
            e[i] = e[i - 1] + al * (clfill[i] - e[i - 1])
        emas[k] = e
    groups = {w: g.sort_values("s") for w, g in ev.groupby("w")}
    tgroups = {w: g.sort_values("s") for w, g in tch.groupby("w")}
    rows = []
    t0, t1 = (a // 300 + 1) * 300, b - 1
    for t in range(t0 + 5, t1):
        st5 = (t // 300) * 300
        st15 = (t // 900) * 900
        w5, w15 = f"btc-updown-5m-{st5}", f"btc-updown-15m-{st15}"
        tau5, tau15 = st5 + 300 - t, st15 + 900 - t
        if tau5 < 70 or tau15 < 70 or w5 not in groups or w15 not in groups:
            continue
        K5, K15 = tw.get(st5), tw.get(st15)
        if K5 is None or K15 is None:
            continue
        T = t * 1000
        r5, r15 = top_rungs(groups[w5], T), top_rungs(groups[w15], T)
        if r5 is None or r15 is None:
            continue
        jj = np.searchsorted(sec, t)
        sig = np.std(r1[max(jj - 300, 0):jj]) * 1.4
        if not sig > 0:
            continue
        row = {"t": t, "st5": st5, "st15": st15, "tau5": tau5, "tau15": tau15, "K5": K5, "K15": K15, "sig": sig}
        ok = True
        for nm, (qu, au), w, K, tau in (("5", r5, w5, K5, tau5), ("15", r15, w15, K15, tau15)):
            F = (qu + au) / 2
            tg = tgroups.get(w)
            if tg is None or not (0.04 < F < 0.96) or au <= qu:
                ok = False
                break
            i = np.searchsorted(tg.s.to_numpy(), T, side="right") - 1
            if i < 0:
                ok = False
                break
            mid = (tg.bb.to_numpy()[i] + tg.ba.to_numpy()[i]) / 2
            if not (0.04 < mid < 0.96):
                ok = False
                break
            sst = sig * np.sqrt(tau)
            z = norm.ppf(F)
            row[f"F{nm}"], row[f"h{nm}"], row[f"mid{nm}"] = F, (au - qu) / 2, mid
            row[f"S{nm}"] = K * np.exp(sst * z)
            row[f"Smid{nm}"] = K * np.exp(sst * norm.ppf(mid))
            row[f"tick{nm}"] = 0.01 * sst * K * np.exp(sst * z) / norm.pdf(z)
        if not ok:
            continue
        for D in (700, 1083, 1432, 2000, 3000):
            k = np.searchsorted(cls, (T - D) // 1000, side="right") - 1
            row[f"cl{D}"] = clv[k] if k >= 0 else np.nan
        ci = (T - 1432) // 1000 - clsec[0]
        for k, e in emas.items():
            row[f"ema{k}"] = e[ci] if 0 <= ci < len(e) else np.nan
        fi = max(np.searchsorted(fs, T, side="right") - 1, 0)
        row["fut"] = fm[fi]
        # basis: Chainlink (stamp s) minus futures (second s + 2: the stamp runs 2 s behind the settlement clock), trailing 300 s
        lo = np.searchsorted(cls, t - 302)
        hi = np.searchsorted(cls, t - 2)
        if hi - lo > 30:
            fsec = ms_sec[np.clip(np.searchsorted(sec, cls[lo:hi] + 2), 0, len(ms_sec) - 1)]
            row["fut_cl"] = fm[fi] + float(np.median(clv[lo:hi] - fsec))
        else:
            row["fut_cl"] = np.nan
        rows.append(row)
    D = pd.DataFrame(rows)
    out = {"seconds": int(len(D)), "windows5": int(D.st5.nunique()), "windows15": int(D.st15.nunique())}
    D["dS"] = D.S5 - D.S15
    D["tickmax"] = np.maximum(D.tick5, D.tick15)
    out["S5_minus_S15_usd_q"] = D.dS.quantile([.1, .25, .5, .75, .9]).round(2).to_dict()
    out["abs_S5_minus_S15_in_tick_equiv_q"] = (D.dS.abs() / D.tickmax).quantile([.25, .5, .75, .9]).round(2).to_dict()
    out["share_within_one_tick_equiv"] = round(float((D.dS.abs() <= D.tickmax).mean()), 3)
    out["tick_equiv_usd_median"] = {"5m": round(float(D.tick5.median()), 2), "15m": round(float(D.tick15.median()), 2)}
    D["dSmid"] = D.Smid5 - D.Smid15
    out["Smid5_minus_Smid15_usd_q"] = D.dSmid.quantile([.1, .25, .5, .75, .9]).round(2).to_dict()
    sl, ic = np.polyfit(D.dSmid, D.dS, 1)
    out["regress_dS_on_dSmid"] = {"slope": round(float(sl), 3), "r2": round(float(np.corrcoef(D.dSmid, D.dS)[0, 1] ** 2), 3)}
    # which X does S_hat track? residual sd after removing a per-window mean (basis / strike offsets), and 2-s change corr
    cand = [c for c in D.columns if c.startswith("cl") or c.startswith("ema")] + ["fut_cl"]
    res = {}
    for m in ("5", "15"):
        S = D[f"S{m}"]
        wkey = D[f"st{m}"]
        for X in cand + [f"Smid{m}"]:
            r = (S - D[X])
            r = r - r.groupby(wkey).transform("mean")
            g = D.assign(S=S, X=D[X]).groupby(wkey)
            dS2 = g.S.diff(2)
            dX2 = g.X.diff(2)
            v = pd.concat([dS2, dX2], axis=1).dropna()
            res[f"{m}m|{X}"] = {"resid_sd_usd": round(float(r.std()), 2),
                                "corr_d2s": round(float(np.corrcoef(v.iloc[:, 0], v.iloc[:, 1])[0, 1]), 3) if len(v) > 50 else None}
    out["track"] = res
    # blend: S_hat_m - Smid_m = beta (X - Smid_m); fit on < SPLIT, held-out R^2 >= SPLIT
    bl = {}
    for m in ("5", "15"):
        for X in ("cl1432", "cl2000", "ema3", "fut_cl"):
            y = D[f"S{m}"] - D[f"Smid{m}"]
            xx = D[X] - D[f"Smid{m}"]
            ok = y.notna() & xx.notna()
            tr, te = ok & (D.t < SPLIT), ok & (D.t >= SPLIT)
            if tr.sum() < 50 or te.sum() < 50:
                continue
            beta, c0 = np.polyfit(xx[tr], y[tr], 1)
            pred = c0 + beta * xx[te]
            r2 = 1 - np.sum((y[te] - pred) ** 2) / np.sum((y[te] - y[te].mean()) ** 2)
            bl[f"{m}m|{X}"] = {"beta": round(float(beta), 3), "icpt_usd": round(float(c0), 2), "r2_heldout": round(float(r2), 3),
                               "n": [int(tr.sum()), int(te.sum())]}
    out["blend"] = bl
    # common-S test with the blend: does one beta and one X make the two markets agree?
    for X in ("cl1432", "ema3", "fut_cl"):
        for beta in (0.0, 0.2, 0.5, 1.0):
            S5b = D.Smid5 + beta * (D[X] - D.Smid5)
            S15b = D.Smid15 + beta * (D[X] - D.Smid15)
            e5 = (D.S5 - S5b)
            e15 = (D.S15 - S15b)
            out.setdefault("blend_fit_abs_err_tick_equiv_median", {})[f"{X}|beta{beta}"] = [
                round(float((e5.abs() / D.tick5).median()), 2), round(float((e15.abs() / D.tick15).median()), 2)]
    out["h_median"] = {"5m": round(float(D.h5.median()), 3), "15m": round(float(D.h15.median()), 3)}
    (HERE.parent / "results" / f"iter8_m1_invert_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=str))
    D.to_parquet(C / "it6" / f"m1inv_{a}_{b}.parquet", index=False)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
