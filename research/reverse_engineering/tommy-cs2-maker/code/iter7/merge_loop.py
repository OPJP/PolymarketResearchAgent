"""Iteration 7, X95 (mechanics panel iter6 P4): the 300-s merge loop as the maker process's clock.

MERGE activity of the wallet (data-api, cached: activity_dev 10-15..H, activity_taker 06-16..10-15, activity_devblocks
10-31 dev block). Passes = consecutive merges <= 20 s apart. Law (panel): next pass start = previous pass end + 307 s +
300 s x k (k = empty passes). Phase residual r = gap - 307 - 300 k. A pass pair is phase-continuous if |r| <= 10 s;
runs = maximal continuous chains; restarts = breaks. Compared with:
  (a) the taker regime (any MERGE before 10-16?);
  (b) the wallet's order gaps (no maker / taker order signed anywhere for >= 30 min: downtime) from orders.parquet;
  (c) the starts of event-wide size ramps (first maker order of an event at < 100 shares), and the event's in-play span
      inside / outside runs;
  (d) selection labels: events with game start inside a run vs not (diagnostic only; uptime is own activity).
Output: results/merge_loop.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def passes(ts):
    ts = np.sort(ts)
    P = []
    cur = [ts[0]]
    for t in ts[1:]:
        if t - cur[-1] <= 20:
            cur.append(t)
        else:
            P.append(cur)
            cur = [t]
    P.append(cur)
    return [(p[0], p[-1], len(p)) for p in P]


def runs_of(P, tol=10):
    rows = []
    for (s0, e0, n0), (s1, e1, n1) in zip(P[:-1], P[1:]):
        gap = s1 - e0
        k = int(round((gap - 307) / 300))
        r = gap - 307 - 300 * k
        rows.append({"end0": e0, "start1": s1, "gap": gap, "k": k, "resid": r, "n0": n0,
                     "cont": bool(k >= 0 and abs(r) <= tol), "step": (s1 - s0) if k == 0 else None})
    return pd.DataFrame(rows)


def main():
    res = {}
    at = pd.read_parquet(OUT / "activity_taker.parquet", columns=["type", "timestamp"])
    res["merges_taker_regime"] = int((at.type == "MERGE").sum())
    ad = pd.read_parquet(OUT / "activity_dev.parquet", columns=["type", "timestamp", "size", "conditionId"])
    m = ad[ad.type == "MERGE"]
    res["merges_maker_regime"] = int(len(m))
    res["first_merge_utc"] = str(pd.to_datetime(m.timestamp.min(), unit="s"))
    res["min_merge_size"] = round(float(m["size"].min()), 2)
    P = passes(m.timestamp.to_numpy())
    D = runs_of(P)
    res["passes"] = len(P)
    res["pass_size_p50_p90_max"] = [int(np.median([p[2] for p in P])), int(np.percentile([p[2] for p in P], 90)), int(max(p[2] for p in P))]
    # within-pass spacing and the k = 0 step law
    within = np.concatenate([np.diff(np.sort(m.timestamp.to_numpy()))])
    within = within[within <= 20]
    res["within_pass_spacing_s_p10_p50_p90"] = [float(x) for x in np.percentile(within, [10, 50, 90])]
    k0 = D[(D.k == 0) & D.cont]
    if len(k0) > 10:
        sl, ic = np.polyfit(k0.n0, k0.step, 1)
        res["law_k0"] = {"n": int(len(k0)), "intercept_s": round(float(ic), 2), "per_merge_s": round(float(sl), 2),
                         "resid_sd_s": round(float(np.std(k0.step - (ic + sl * k0.n0))), 2)}
    res["pairs"] = int(len(D))
    res["continuous_share"] = round(float(D.cont.mean()), 3)
    res["resid_abs_p50_p90_continuous"] = [round(float(x), 1) for x in np.percentile(D[D.cont].resid.abs(), [50, 90])]
    br = D[~D.cont]
    res["restarts"] = [{"after": str(pd.to_datetime(r.end0, unit="s")), "next": str(pd.to_datetime(r.start1, unit="s")),
                        "gap_s": int(r.gap), "resid_s": round(float(r.resid), 1)} for r in br.itertuples()]
    # runs
    bounds = [P[0][0]]
    for r in br.itertuples():
        bounds += [r.end0, r.start1]
    bounds.append(P[-1][1])
    runs = [(bounds[i], bounds[i + 1]) for i in range(0, len(bounds), 2)]
    res["runs"] = [{"start": str(pd.to_datetime(a, unit="s")), "end": str(pd.to_datetime(b, unit="s")),
                    "hours": round((b - a) / 3600, 2)} for a, b in runs]
    # (b) downtime: order gaps >= 30 min in its signed orders
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "event", "shares", "role", "gs_ts", "cid"])
    o = o[(o.sign_ms > 1.79e12)]
    s = np.sort(o.sign_ms.to_numpy() / 1000)
    gaps = [(a, b) for a, b in zip(s[:-1], s[1:]) if b - a >= 1800 and a >= m.timestamp.min() - 3600]

    def in_run(t, pad=310):
        return any(a - pad <= t <= b + pad for a, b in runs)

    res["order_gaps_ge30min"] = len(gaps)
    res["order_gaps_with_merge_loop_running"] = int(sum(1 for a, b in gaps if in_run(a) and in_run(b) and
                                                     any(a <= x <= b for x, _, _ in P)))
    # restart -> first orders after it
    rs = []
    for r in br.itertuples():
        nxt = s[np.searchsorted(s, r.start1 - 3600):np.searchsorted(s, r.start1 + 3600)]
        prv = s[s < r.end0]
        rs.append({"restart_at": str(pd.to_datetime(r.start1, unit="s")),
                   "last_order_before_s": round(float(r.start1 - prv[-1]), 0) if len(prv) else None,
                   "first_order_after_s": round(float(s[np.searchsorted(s, r.start1)] - r.start1), 0) if np.searchsorted(s, r.start1) < len(s) else None})
    res["restart_vs_orders"] = rs
    # (c) size ramps: events whose first maker orders are < 100 shares
    mk = o[o.role == "maker"].sort_values("sign_ms")
    ev_first = mk.groupby("event").agg(t0=("sign_ms", "min"), first_size=("shares", "first"))
    ev_first["ramp"] = ev_first.first_size < 99.5
    ev_first["t0s"] = ev_first.t0 / 1000
    rst = np.array([r.start1 for r in br.itertuples()] + [P[0][0]], float)

    def since_restart(t):
        d = t - rst[rst <= t + 600]
        return float(d.min()) if len(d) else np.nan

    ev_first["since_restart_h"] = [since_restart(t) / 3600 for t in ev_first.t0s]
    res["ramp_events"] = int(ev_first.ramp.sum())
    res["events"] = int(len(ev_first))
    res["since_restart_h_median_ramp_vs_not"] = [round(float(ev_first[ev_first.ramp].since_restart_h.median()), 2),
                                                round(float(ev_first[~ev_first.ramp].since_restart_h.median()), 2)]
    res["ramp_share_first_event_after_restart"] = None
    # first event after each restart: ramp?
    firsts = []
    for t in rst:
        sub = ev_first[ev_first.t0s >= t - 600].sort_values("t0s")
        if len(sub):
            firsts.append(bool(sub.iloc[0].ramp))
    if firsts:
        res["ramp_share_first_event_after_restart"] = [int(sum(firsts)), len(firsts)]
    res["ramp_share_all_events"] = round(float(ev_first.ramp.mean()), 3)
    # (d) selection labels vs runs (diagnostic)
    es = pd.read_parquet(OUT / "events_sel.parquet", columns=["event_slug", "y", "gs", "grid"])
    es = es[(es.gs >= 1792108800) & (es.gs < 1792713600) & (~es.grid.astype(bool))]
    es["in_run"] = [in_run(g, pad=0) for g in es.gs]
    res["selection_by_run"] = es.groupby("in_run").y.agg(["count", "mean"]).round(3).reset_index().to_dict("records")
    # 10-31 dev block merges (development data): same law?
    ab = pd.read_parquet(OUT / "activity_devblocks.parquet", columns=["type", "timestamp"])
    mb = ab[ab.type == "MERGE"].timestamp.to_numpy()
    if len(mb) > 3:
        Pb = passes(mb)
        Db = runs_of(Pb)
        res["devblock_10_31"] = {"merges": int(len(mb)), "passes": len(Pb), "continuous_share": round(float(Db.cont.mean()), 3),
                                 "resid_s": [round(float(x), 1) for x in Db.resid]}
    (RES / "merge_loop.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str)[:7000])


if __name__ == "__main__":
    main()
