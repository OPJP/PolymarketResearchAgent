"""Iteration 7, panel iter6 information I2 / mechanics M1 (X44, X49): does the engine act on a Chainlink report before
or after the public RTDS relay publishes it?

Inputs (development blocks only): own streaming RTDS recorder dy_rtds (value stamp ts, server publish ms P, laptop
receive ms t), the exact-500 add events of code6/live6_extract.py (it6/ev_<a>_<b>.parquet, CLOB server ms s), the exam
recorder's trades dx_clob (server ms s and laptop receive ms t) for the clock check.

Measure: re-posts = exact-500 adds whose price changed vs the previous exact-500 add on the same market side within
1.5 s (|dp| <= 0.05). Their direction (Up terms) is compared with the Chainlink 1-s change of stamp S,
dCL_S = CL_S - CL_{S-1} (|dCL_S| > $3), as a function of (a) the post's time relative to the publish ms of stamp S,
x = s - P_S, and (b) relative to the stamp, y = s - 1000 S. Before the engine has seen dCL_S the agreement is below 0.5
(lag-1 autocorrelation of dCL is about -0.47); after, above. The switch point in x says whether the engine acts
before (direct source) or after (public relay) the publish.

  .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code7/i2_publish.py <a> <b>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
OUT = ROOT / "research/reverse_engineering/directional-maker/results"


def q(x, ps=(0.1, 0.5, 0.9)):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return [round(float(np.quantile(x, p)), 1) for p in ps] if len(x) else None


def step_fit(xc, ag, n):
    """least-squares step: agreement a0 below b, a1 at/above b (weighted by n)."""
    best = None
    for b in xc[2:-2]:
        lo, hi = xc < b, xc >= b
        a0 = np.average(ag[lo], weights=n[lo])
        a1 = np.average(ag[hi], weights=n[hi])
        sse = float(np.sum(n[lo] * (ag[lo] - a0) ** 2) + np.sum(n[hi] * (ag[hi] - a1) ** 2))
        if best is None or sse < best[0]:
            best = (sse, float(b), float(a0), float(a1))
    return {"switch_ms": best[1], "agree_before": round(best[2], 3), "agree_after": round(best[3], 3)}


def main(a, b):
    rows = []
    for r in iter_dm("dy_rtds", a - 30, b + 5):
        if r.get("k") == "u" and r.get("sy") == "btc" and r.get("tp") == "cl" and r.get("ts") and r.get("P"):
            rows.append((int(r["ts"]), int(r["P"]), int(r["t"]), float(r["v"])))
    rt = pd.DataFrame(rows, columns=["ts", "P", "t", "v"]).drop_duplicates("ts").sort_values("ts")
    rt["S"] = rt.ts // 1000
    res = {"period": [a, b], "rtds_updates": int(len(rt)),
           "publish_minus_stamp_ms_p10_50_90": q(rt.P - rt.ts),
           "recv_minus_publish_ms_p10_50_90": q(rt.t - rt.P),
           "stamp_steps": {str(k): int(v) for k, v in rt.S.diff().value_counts().head(5).items()}}
    clk = [r for r in iter_dm("dy_rtds", a - 30, b + 5) if r.get("k") == "clk"]
    res["laptop_offset_vs_binance_s"] = [c["off"] for c in clk]
    xs = []
    for r in iter_dm("dm_clob_raw", a, min(b, a + 600)):
        if r.get("s") and r.get("t"):
            xs.append((int(r["s"]), int(r["t"])))
    xs = np.array(xs, dtype=np.int64)
    if len(xs):
        res["clock"] = {"clob_recv_minus_server_ms_q01_q50": [float(np.quantile(xs[:, 1] - xs[:, 0], 0.01)), float(np.median(xs[:, 1] - xs[:, 0]))],
                        "rtds_recv_minus_publish_ms_q01_q50": [float(np.quantile(rt.t - rt.P, 0.01)), float(np.median(rt.t - rt.P))]}
        # relative offset of the two server clocks (RTDS P minus CLOB s at equal true time), from the lower envelopes
        res["clock"]["rtds_minus_clob_clock_ms_est"] = res["clock"]["clob_recv_minus_server_ms_q01_q50"][0] - res["clock"]["rtds_recv_minus_publish_ms_q01_q50"][0]
    cl = dict(zip(rt.S, rt.v))
    pub = dict(zip(rt.S, rt.P))
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet", columns=["s", "w", "side", "p", "d"])
    out = {}
    streams = {"c500": lambda d: d == 500, "o100": lambda d: d == 100,
               "osmall": lambda d: d.isin([5.0, 10.0, 20.0, 30.0, 40.0, 50.0])}
    for tag, pre in (("5m", "btc-updown-5m"), ("15m", "btc-updown-15m")):
        for sn, sel in streams.items():
            e = ev[ev.w.str.startswith(pre) & sel(ev.d)].copy()
            if len(e) < 50:
                out[f"{tag}_{sn}"] = {"reposts": 0}
                continue
            e["p"] = e.p.round(2)
            e = e.sort_values(["w", "side", "p", "s"], kind="stable")
            gp = e.groupby(["w", "side", "p"]).s
            e["nb"] = 1 + ((gp.diff() <= 20).astype(int) + (-gp.diff(-1) <= 20).astype(int))
            e = e.sort_values(["w", "side", "s"], kind="stable")
            e["dp"] = e.groupby(["w", "side"]).p.diff()
            e["dt"] = e.groupby(["w", "side"]).s.diff()
            E = e[(e.dt <= 1500) & (e.dp.abs() > 0) & (e.dp.abs() <= 0.05)].copy()
            sec = (E.s.to_numpy() // 1000).astype(np.int64)
            sg = np.sign(E.dp.to_numpy())
            recs = []
            for k in range(0, 5):
                S = sec - k
                d = np.array([cl.get(x, np.nan) - cl.get(x - 1, np.nan) for x in S])
                P = np.array([pub.get(x, np.nan) for x in S], dtype=float)
                ok = np.isfinite(d) & (np.abs(d) > 3) & np.isfinite(P)
                recs.append(pd.DataFrame({"k": k, "x": E.s.to_numpy()[ok] - P[ok], "y": E.s.to_numpy()[ok] - S[ok] * 1000,
                                          "agree": (np.sign(d[ok]) == sg[ok]).astype(float), "multi": (E.nb.to_numpy()[ok] >= 2)}))
            R = pd.concat(recs)
            prof = {}
            for col, lo, hi in (("x", -2500, 1500), ("y", 0, 4000)):
                R["bin"] = (R[col] // 100 * 100).astype(int)
                g = R[(R[col] >= lo) & (R[col] < hi)].groupby("bin").agree.agg(["mean", "size"])
                g = g[g["size"] >= 25]
                prof[col] = {"profile": {str(int(i)): [round(float(m), 3), int(n)] for i, (m, n) in g.iterrows()},
                             "step": step_fit(g.index.to_numpy(float), g["mean"].to_numpy(), g["size"].to_numpy(float)) if len(g) > 6 else None}
            fine = {}
            for nm, RR in (("all", R), ("multi", R[R.multi]), ("single", R[~R.multi])):
                RR = RR[(RR.x >= -500) & (RR.x < 600)].copy()
                RR["bin"] = (RR.x // 50 * 50).astype(int)
                g = RR.groupby("bin").agree.agg(["mean", "size"])
                fine[nm] = {str(int(i)): [round(float(m), 3), int(n)] for i, (m, n) in g.iterrows()}
            # agreement right after the publish (0-200 ms) vs just before it (-600..-100 ms), all lags pooled
            post = R[(R.x >= 0) & (R.x < 200)].agree
            pre_ = R[(R.x >= -600) & (R.x < -100)].agree
            out[f"{tag}_{sn}"] = {"reposts": int(len(E)), "multi_share": float((E.nb >= 2).mean()), "pairs": int(len(R)),
                                  "agree_post_0_200": [round(float(post.mean()), 3), int(len(post))] if len(post) else None,
                                  "agree_pre_600_100": [round(float(pre_.mean()), 3), int(len(pre_))] if len(pre_) else None,
                                  **prof, "fine_x_50ms": fine}
    res["agreement"] = out
    f = OUT / f"iter7_i2_publish_{a}_{b}.json"
    f.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "agreement"}, indent=1))
    for tag, v in out.items():
        if not v.get("reposts"):
            print(tag, "none")
            continue
        print(tag, v["reposts"], "multi", round(v["multi_share"], 3), "post", v["agree_post_0_200"], "pre", v["agree_pre_600_100"],
              "x-step", v["x"]["step"], "y-step", v["y"]["step"])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
