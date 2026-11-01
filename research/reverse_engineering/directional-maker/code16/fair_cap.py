"""iteration 16, X181 (mechanics panel P3, the fair cap on the main 500 ladder; derived from ladder_center.py, X180) (assumptions panel P2 + mechanics panel P3): the ladder CENTER at each public publish pass.
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
                            mids.append((w, s, mm, row[3], row[4]))
                        dz = round(z - old, 2)
                        if dz in SIZES:
                            bid = p if sd == 1 else 1 - p
                            if 0.03 < bid < 0.97:
                                adds.append((w, s, sd, p))
        except (zlib.error, EOFError, OSError) as e:
            print("read stop in hour", h, repr(e)[:60])
    return pd.DataFrame(adds, columns=["w", "s", "sd", "p"]), pd.DataFrame(mids, columns=["w", "s", "mid", "bb", "ba"])


def fit(X, y):
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    res = y - X1 @ beta
    r2 = 1 - res.var() / y.var() if y.var() > 0 else np.nan
    return [round(float(v), 4) for v in beta], round(float(r2), 4)



def tick_floor(x):
    return np.floor(np.round(x * 100, 6)) / 100


out = {}
for a, b in BLOCKS:
    A, Mi = read(a, b)
    Mi = Mi.sort_values(["w", "s"], kind="stable")
    ser = {w: (g.s.to_numpy(np.int64), g.bb.to_numpy(float), g.ba.to_numpy(float)) for w, g in Mi.groupby("w")}
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
    A["i"] = np.searchsorted(P, A.s.to_numpy(np.int64), side="left") - 1
    A = A[A.i >= 0]
    A["lag"] = A.s.to_numpy(np.int64) - P[A.i.to_numpy()]
    A = A[A.lag <= 300]
    A["bid"] = np.where(A.sd == 1, A.p, 1 - A.p)
    g = A.groupby(["w", "i", "sd"]).bid.max().reset_index()
    g["P"] = P[g.i.to_numpy()]
    g["v"] = Pb.v.to_numpy()[g.i.to_numpy()]
    g["ts"] = Pb.ts.to_numpy()[g.i.to_numpy()]
    tb = np.full(len(g), np.nan)
    for j, (w, p_, sd) in enumerate(zip(g.w, g.P, g.sd)):
        if w not in ser:
            continue
        s_, bb_, ba_ = ser[w]
        k = np.searchsorted(s_, p_, side="right") - 1
        if k >= 0:
            tb[j] = bb_[k] if sd == 1 else 1 - ba_[k]  # the touch bid of this outcome just before the publish
    g["touch"] = tb
    st = g.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
    en = st + np.where(g.w.str.contains("-15m-").to_numpy(), 900, 300)
    t = g.P.to_numpy(np.int64)
    tau = np.maximum(en - t / 1000, 1.0)
    s0 = sig.reindex(t // 1000).to_numpy(float)
    kk = g.w.map(K).to_numpy(float)
    now = g.v.to_numpy() + at(E, M, t - 50) - at(E, M, g.ts.to_numpy(np.int64))
    ok = np.isfinite(g.touch.to_numpy()) & np.isfinite(s0) & np.isfinite(kk)
    g = g[ok].reset_index(drop=True)
    tau, s0, kk, now, t = tau[ok], s0[ok], kk[ok], now[ok], t[ok]
    half = t < (a + (b - a) // 2) * 1000
    blk = {"units": int(len(g))}
    bt = g.bid.to_numpy()
    tch = g.touch.to_numpy()
    upm = (g.sd == 1).to_numpy()
    blk["join_touch"] = round(float((np.abs(bt - tch) <= 0.0101).mean()), 3)
    blk["touch_m1"] = round(float((np.abs(bt - (tch - 0.01)) <= 0.0101).mean()), 3)
    blk["at_or_above_touch"] = round(float((bt >= tch - 1e-9).mean()), 3)
    for nm, S in (("report", g.v.to_numpy()), ("nowcast", now)):
        for k in (1.0, 2.0):
            Fu = norm.cdf((S - kk) / (k * s0 * np.sqrt(tau)))
            Fs = np.where(upm, Fu, 1 - Fu)
            for h in (0.03, 0.05, 0.075, 0.10):
                cap = tick_floor(Fs - h)
                pred = np.minimum(tch, cap)
                hit = np.abs(bt - pred) <= 0.0101
                capb = cap < tch - 1e-9
                blk[f"{nm}_k{k}_h{h}"] = {"all": round(float(hit.mean()), 3), "first_half": round(float(hit[half].mean()), 3) if half.any() else None,
                                          "second_half": round(float(hit[~half].mean()), 3) if (~half).any() else None,
                                          "cap_binding_share": round(float(capb.mean()), 3),
                                          "when_capped": round(float(hit[capb].mean()), 3) if capb.any() else None,
                                          "when_uncapped": round(float(hit[~capb].mean()), 3) if (~capb).any() else None}
    out[f"{a}_{b}"] = blk
    print(a, b, json.dumps({k: v for k, v in blk.items() if not isinstance(v, dict) or k.endswith(("h0.075", "h0.05"))})[:2500])
(HERE.parent / "results/iter16_fair_cap.json").write_text(json.dumps(out, indent=1))
