"""iteration 16, T4 = X180 (assumptions panel P2 + mechanics panel P3): the ladder CENTER at each public publish pass.
For each public Chainlink BTC publish P_i (dy_rtds P, exact clock), take every exact 500 / 1000 / 2000 size increase at
ANY price (full-depth dm_clob_raw 'pc' rows) on each outcome of each BTC 5m / 15m window in (P_i, P_i + 300 ms]
(non-extreme bids 0.03-0.97). b_up = the highest Up-bid add, b_dn = the highest Down-bid add (an Up-ask add at p is a
Down bid at 1 - p). Units with both outcomes: c = (b_up + 1 - b_dn) / 2, h = (1 - b_dn - b_up) / 2.
Regress c - mid on F_k - mid (k 1.0 / 1.4 / 2.0 / 3.0, report i and its nowcast) and on (F_1 - mid, 0.5 - mid), per
block. Pre-registered readings (09:07 UTC): (i) k: best k for c moves by > 0.3 between blocks and the (0.5 - mid)
coefficient is ~0 on both; (ii) spread: best k within 0.3 on both blocks and the (0.5 - mid) coefficient changes sign.
    python ladder_center.py"""
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code14"))
from lagged_quote import fut_mid, at, sec_sigma, live  # noqa: E402

BLOCKS = [(1793467740, 1793469600), (1793516400, 1793524500)]
SIZES = {500.0, 1000.0, 2000.0}


def read(a, b):
    book, adds, mids, lastm = {}, [], [], {}
    for h in range(a - a % 3600, b, 3600):
        try:
            for r in live.iter_live("dm_clob_raw", max(h, a), min(h + 3600, b)):
                k = r.get("k")
                if k == "bk":
                    bw = {1: {}, 0: {}}
                    for p, z in r.get("b", []):
                        bw[1][round(p, 3)] = z
                    for p, z in r.get("o", []):
                        bw[0][round(p, 3)] = z
                    book[r["w"]] = bw
                elif k == "pc":
                    w = r["w"]
                    s = r["s"]
                    bw = book.get(w)
                    if bw is None:
                        continue
                    for row in r["c"]:
                        sd, p, z = row[0], round(row[1], 3), row[2]
                        if sd >= 2:
                            continue
                        old = bw[sd].get(p, 0.0)
                        bw[sd][p] = z
                        mm = (row[3] + row[4]) / 2
                        if lastm.get(w) != mm:
                            lastm[w] = mm
                            mids.append((w, s, mm))
                        dz = round(z - old, 2)
                        if dz in SIZES:
                            bid = p if sd == 1 else 1 - p
                            if 0.03 < bid < 0.97:
                                adds.append((w, s, sd, p))
        except (zlib.error, EOFError, OSError) as e:
            print("read stop in hour", h, repr(e)[:60])
    return pd.DataFrame(adds, columns=["w", "s", "sd", "p"]), pd.DataFrame(mids, columns=["w", "s", "mid"])


def fit(X, y):
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    res = y - X1 @ beta
    r2 = 1 - res.var() / y.var() if y.var() > 0 else np.nan
    return [round(float(v), 4) for v in beta], round(float(r2), 4)


out = {}
for a, b in BLOCKS:
    A, Mi = read(a, b)
    Mi = Mi.sort_values(["w", "s"], kind="stable")
    ser = {w: (g.s.to_numpy(np.int64), g.mid.to_numpy(float)) for w, g in Mi.groupby("w")}
    pub = []
    for r in live.iter_live("dy_rtds", a - 120, b):
        if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
            pub.append((int(r["P"]), int(r["ts"]), float(r["v"])))
    Pb = pd.DataFrame(pub, columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts").sort_values("P")
    Pb = Pb[(Pb.P >= a * 1000) & (Pb.P < b * 1000)].reset_index(drop=True)
    E, M = fut_mid(a - 900, b)
    sig = sec_sigma(E, M, 300)
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows(sorted(set(A.w)))
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    P = Pb.P.to_numpy(np.int64)
    A = A.sort_values("s", kind="stable")
    A["i"] = np.searchsorted(P, A.s.to_numpy(np.int64), side="left") - 1  # last publish strictly before the add
    A = A[A.i >= 0]
    A["lag"] = A.s.to_numpy(np.int64) - P[A.i.to_numpy()]
    A = A[A.lag <= 300]
    A["bid"] = np.where(A.sd == 1, A.p, 1 - A.p)
    g = A.groupby(["w", "i", "sd"]).bid.max().unstack("sd")
    g = g.dropna().reset_index().rename(columns={1: "b_up", 0: "b_dn"})
    g["P"] = P[g.i.to_numpy()]
    g["v"] = Pb.v.to_numpy()[g.i.to_numpy()]
    g["ts"] = Pb.ts.to_numpy()[g.i.to_numpy()]
    g["mid"] = [at(*ser[w], np.array([p]))[0] if w in ser else np.nan for w, p in zip(g.w, g.P)]
    g["c"] = (g.b_up + 1 - g.b_dn) / 2
    g["h"] = (1 - g.b_dn - g.b_up) / 2
    st = g.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
    en = st + np.where(g.w.str.contains("-15m-").to_numpy(), 900, 300)
    t = g.P.to_numpy(np.int64)
    tau = np.maximum(en - t / 1000, 1.0)
    s0 = sig.reindex(t // 1000).to_numpy(float)
    kk = g.w.map(K).to_numpy(float)
    now = g.v.to_numpy() + at(E, M, t - 50) - at(E, M, g.ts.to_numpy(np.int64))
    ok = np.isfinite(g.mid.to_numpy()) & np.isfinite(s0) & np.isfinite(kk) & (g.h > -0.005)
    g = g[ok].reset_index(drop=True)
    tau, s0, kk, now = tau[ok], s0[ok], kk[ok], now[ok]
    mid = g.mid.to_numpy()
    yc = g.c.to_numpy() - mid
    blk = {"units": int(len(g)), "publishes": int(len(Pb)), "windows": int(g.w.nunique()),
           "h_median": round(float(g.h.median()), 4), "h_iqr": [round(float(g.h.quantile(q)), 4) for q in (0.25, 0.75)],
           "c_minus_mid_sd": round(float(yc.std()), 4)}
    for nm, S in (("report", g.v.to_numpy()), ("nowcast", now)):
        for k in (1.0, 1.4, 2.0, 3.0):
            Fk = norm.cdf((S - kk) / (k * s0 * np.sqrt(tau)))
            x = Fk - mid
            beta, r2 = fit(x[:, None], yc)
            blk[f"{nm}_k{k}"] = {"slope_intercept": [beta[1], beta[0]], "r2": r2,
                                 "side_agree": round(float(((g.c.to_numpy() > mid) == (Fk > mid)).mean()), 3)}
        F1 = norm.cdf((S - kk) / (s0 * np.sqrt(tau)))
        beta, r2 = fit(np.column_stack([F1 - mid, 0.5 - mid]), yc)
        blk[f"{nm}_two_feature_k1.0"] = {"const_edge_cheapness": beta, "r2": r2}
        # favourite / underdog distance asymmetry relative to F1: a = (F_fav - b_fav) - (F_und - b_und) = 2 (F1 - c) signed to the favourite
        fav_up = mid > 0.5
        a_ = np.where(fav_up, 2 * (F1 - g.c.to_numpy()), -2 * (F1 - g.c.to_numpy()))
        blk[f"{nm}_asym_fav_minus_und_median"] = round(float(np.nanmedian(a_)), 4)
        blk[f"{nm}_asym_fav_minus_und_mean"] = round(float(np.nanmean(a_)), 4)
    # center side vs cheaper token
    blk["center_side_cheaper"] = round(float(((g.c.to_numpy() > mid) == (mid < 0.5)).mean()), 3)
    blk["center_above_mid_share"] = round(float((g.c.to_numpy() > mid).mean()), 3)
    out[f"{a}_{b}"] = blk
    g.assign(F1_now=norm.cdf((now - kk) / (s0 * np.sqrt(tau))), F1_rep=norm.cdf((g.v.to_numpy() - kk) / (s0 * np.sqrt(tau)))).to_parquet(
        ROOT / ".cache/re/directional-maker" / f"it16_center_units_{a}_{b}.parquet", index=False)
    print(a, b, json.dumps(blk)[:2500])
(HERE.parent / "results/iter16_ladder_center.json").write_text(json.dumps(out, indent=1))
