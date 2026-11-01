"""directional-maker iteration 14, T1 out of sample (frozen 05:58 UTC 11-01, before the block existed): the quote-unit
side on the development block 11-01 06-12 (Sunday 01-07 ET, the off-session 62/250 configuration), full-depth
dm_clob_raw from code8/delayed_rawrec.py and dm_bnf.

Unit: every schedule-size add (62 / 250 / 500 / 1000) at the touch (Up bid p = best bid, or Up ask p = best ask) of a
BTC 5m / 15m window. Frozen scores: posture (Chainlink stamped <= t - 1.25 s, Gamma strike, 1.4 x futures sigma300)
against the Up mid just before the add; the move rules over [t - W, t - 50 ms] on the futures mid with theta $2 for
W 0.5 s and 1 s ("fell" = pre-registered, "rose" = the reverse found on 10-31); market-only: the outcome whose
Polymarket Up mid fell over 1 s, the token whose bid was hit by the last clean print. Also by size class and by pass
multiplicity (same-size adds at one price within +-25 ms).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/qu_oos.py 1793512800 <end_ts>
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
sys.path.insert(0, str(HERE))
from lagged_quote import fut_mid, at, sec_sigma, cl_source, live  # noqa: E402

RUNG = {62.0, 250.0, 500.0, 1000.0}


def main(a, b):
    book, adds, mids, xs, lastm = {}, [], [], [], {}
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
                    w = r["w"]; s = r["s"]; bw = book.get(w)
                    if bw is None:
                        continue
                    for row in r["c"]:
                        sd, p, z = row[0], round(row[1], 3), row[2]
                        if sd >= 2:
                            continue
                        old = bw[sd].get(p, 0.0)
                        bw[sd][p] = z
                        bb, ba = row[3], row[4]
                        mm = (bb + ba) / 2
                        if lastm.get(w) != mm:
                            lastm[w] = mm
                            mids.append((w, s, mm))
                        dz = round(z - old, 2)
                        if dz in RUNG and ((sd == 1 and abs(p - bb) < 1e-9) or (sd == 0 and abs(p - ba) < 1e-9)):
                            adds.append((w, s, sd, p, dz))
                elif k == "x":
                    xs.append((r["w"], r["s"], int(r.get("ai", -1)), str(r.get("d")), (r.get("h") or "").lower()))
        except (zlib.error, EOFError, OSError) as e:
            print("read stop in hour", h, repr(e)[:60])
    A = pd.DataFrame(adds, columns=["w", "s", "sd", "p", "dz"])
    Mi = pd.DataFrame(mids, columns=["w", "s", "mid"]).sort_values(["w", "s"], kind="stable")
    X = pd.DataFrame(xs, columns=["w", "s", "ai", "d", "h"]).sort_values("s", kind="stable").drop_duplicates("h")
    print("at-touch schedule adds", len(A), "book rows", len(Mi), "prints", len(X), "windows", A.w.nunique())
    out = {"span": [a, b], "n_adds": int(len(A)), "by_size": A.dz.value_counts().to_dict(),
           "by_family": A.w.str.extract(r"btc-updown-(\d+m)-")[0].value_counts().to_dict()}
    if len(A) == 0:
        print(json.dumps(out)); return
    ser = {w: (g.s.to_numpy(np.int64), g.mid.to_numpy(float)) for w, g in Mi.groupby("w")}
    X["hit_up"] = np.where(X.ai == 0, X.d.str.upper().str[0] == "S", X.d.str.upper().str[0] == "B").astype(float)
    xser = {w: (g.s.to_numpy(np.int64), g.hit_up.to_numpy(float)) for w, g in X.groupby("w")}
    t = A.s.to_numpy(np.int64); w_ = A.w.to_numpy(object)
    mid_prev = np.full(len(A), np.nan); mid_1 = np.full(len(A), np.nan); mid_50 = np.full(len(A), np.nan)
    hit = np.full(len(A), np.nan)
    for w in np.unique(w_):
        ix = np.where(w_ == w)[0]; s_, m_ = ser[w]
        mid_prev[ix] = at(s_, m_, t[ix] - 1); mid_1[ix] = at(s_, m_, t[ix] - 1000); mid_50[ix] = at(s_, m_, t[ix] - 50)
        if w in xser:
            hit[ix] = at(xser[w][0], xser[w][1], t[ix] - 1)
    E, M = fut_mid(a, b)
    sig = sec_sigma(E, M, 300)
    clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=True, max_requests=200)
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows(sorted(set(A.w)))
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
    en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300)
    cl = clv.reindex((t - 1250) // 1000).to_numpy(float)
    sg = sig.reindex(t // 1000).to_numpy(float) * 1.4
    F = norm.cdf((cl - A.w.map(K).to_numpy(float)) / (sg * np.sqrt(np.maximum(en - t / 1000, 1.0))))
    P = np.where(np.isfinite(F) & np.isfinite(mid_prev), (F > mid_prev).astype(float), np.nan)
    y = (A.sd == 1).to_numpy(float)
    f50 = at(E, M, t - 50)

    def acc(pred, mask=None):
        m = np.isfinite(pred) if mask is None else (np.isfinite(pred) & mask)
        return [float((pred[m] == y[m]).mean()) if m.sum() else None, int(m.sum())]
    res = {"posture": acc(P), "always_up": float(y.mean()), "bid_hit_last_print": acc(hit),
           "pm_mid_fell_1s": acc(np.where(np.abs(mid_50 - mid_1) >= 0.005, (mid_50 < mid_1).astype(float), np.nan))}
    for W in (500, 1000):
        dF = f50 - at(E, M, t - W); mv = np.abs(dF) >= 2.0
        res[f"W{W}_moving_share"] = float(np.mean(mv))
        res[f"W{W}_fell_on_moving"] = acc(np.where(mv, (dF < 0).astype(float), np.nan))
        res[f"W{W}_rose_on_moving"] = acc(np.where(mv, (dF > 0).astype(float), np.nan))
        res[f"W{W}_posture_on_moving"] = acc(np.where(mv, P, np.nan))
        res[f"W{W}_rose_else_posture"] = acc(np.where(mv, (dF > 0).astype(float), P))
    for nm, mask in (("size_500_1000", A.dz.isin([500.0, 1000.0]).to_numpy()), ("size_62_250", A.dz.isin([62.0, 250.0]).to_numpy()),
                     ("btc5m", A.w.str.contains("-5m-").to_numpy()), ("btc15m", A.w.str.contains("-15m-").to_numpy())):
        res[f"posture_{nm}"] = acc(P, mask)
    # pass multiplicity
    A2 = A.assign(p=A.p.round(3)).sort_values(["w", "sd", "p", "dz", "s"], kind="stable")
    grp = {k: g.s.to_numpy(np.int64) for k, g in A2.groupby(["w", "sd", "p", "dz"])}
    mult = np.array([int(np.searchsorted(grp[(w, sd, round(p, 3), dz)], s + 25, side="right") -
                         np.searchsorted(grp[(w, sd, round(p, 3), dz)], s - 25, side="left"))
                     for w, s, sd, p, dz in zip(A.w, A.s, A.sd, A.p, A.dz)])
    for m in (1, 2, 3):
        res[f"posture_mult{m}"] = acc(P, np.clip(mult, 1, 3) == m)
    out["T1_oos"] = res
    A.assign(mid_prev=mid_prev, hit=hit, mult=mult, F=F).to_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet", index=False)
    (HERE.parent / "results" / f"iter14_qu_oos_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
