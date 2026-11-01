"""X158 (information panel iter-11 P1, steps 1-2 on BUILD-live): the ~504-ms loop as the decision clock.

Own bursts on the server receive clock (own_bursts_dev: validated own adds / pulls, 10-31 14:50-18:00) and every
non-own level change of the recorded books (level_events_dev; own changes removed by matching own bursts on (a, side,
p, s within 3 ms)).
Step 1 (phase): global loop, period P = 504.0 ms (panel estimate). Each own burst gets the residual to the tick
predicted by the most recent earlier UNTRIGGERED own burst within 60 s (any event): on-tick iff |r| <= 15 ms (uniform
6.0%). Validation: takes (calldata) must be at the uniform rate.
Step 2 (attribution): for each untriggered own burst, the most recent non-own level change (a) on the same book and
(b) on any sibling book of the same event within (t - 504, t - 3] ms; lag distribution and the share with any change,
against control instants t + k P (k = +-2..+-6, the same loop phase, no own burst on the event within 100 ms).
Tick-sampling predicts lags spread over 0-504 ms for on-tick bursts; event-driven reaction predicts lags < 40 ms.
Output: results/loop_attribution.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
P = 504.0
TOL = 15.0
import os as _os
SUF = _os.environ.get("TOMMY_BLOCK_SUFFIX", "")
OWN0, END = int(_os.environ.get("TOMMY_BLOCK_START", 1793458232)), int(_os.environ.get("TOMMY_BLOCK_END", 1793469600))


def main():
    OB = pd.read_parquet(OUT / f"own_bursts_dev{SUF}.parquet").sort_values("s").reset_index(drop=True)
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    ev_of = {str(r.tok0): r.event for r in dm.itertuples()}
    OB["event"] = OB.a.map(ev_of)
    LE = pd.read_parquet(OUT / f"level_events_dev{SUF}.parquet", columns=["a", "s", "side", "p", "kind"])
    LE = LE[(LE.s >= OWN0 * 1000) & (LE.s < END * 1000)].copy()
    LE["event"] = LE.a.map(ev_of)
    # remove own changes: any level event at (a, side) within 3 ms of an own burst on that (a, side)
    own_key = {}
    for r in OB.itertuples():
        own_key.setdefault((r.a, r.side), []).append(r.s)
    for k in own_key:
        own_key[k] = np.sort(np.array(own_key[k]))
    keep = np.ones(len(LE), bool)
    for (a, sd), g in LE.groupby(["a", "side"]):
        arr = own_key.get((a, sd))
        if arr is None:
            continue
        s = g.s.to_numpy(float)
        j = np.searchsorted(arr, s)
        d1 = np.abs(s - arr[np.clip(j - 1, 0, len(arr) - 1)]); d2 = np.abs(s - arr[np.clip(j, 0, len(arr) - 1)])
        keep[LE.index.get_indexer(g.index)] = np.minimum(d1, d2) > 3
    NO = LE[keep]
    by_a = {a: np.sort(g.s.to_numpy(float)) for a, g in NO.groupby("a")}
    by_ev = {e: np.sort(g.s.to_numpy(float)) for e, g in NO.groupby("event")}
    by_ev_a = {e: g for e, g in NO.groupby("event")}
    # step 1: phase residual from the latest earlier untriggered own burst within 60 s
    s = OB.s.to_numpy(float); untr = (OB.trig_code == 0).to_numpy()
    ref = np.full(len(OB), np.nan)
    last = np.nan
    for i in range(len(OB)):
        if np.isfinite(last) and s[i] - last <= 60000:
            ref[i] = last
        if untr[i]:
            last = s[i]
    r = ((s - ref + P / 2) % P) - P / 2
    OB["phase_res"] = r
    OB["on_tick"] = np.abs(r) <= TOL
    out = {"own_bursts": int(len(OB)), "P_ms": P, "tol_ms": TOL, "uniform_rate": round(2 * TOL / P, 3)}
    out["on_tick_rate"] = {k: [round(float(g.on_tick[np.isfinite(g.phase_res)].mean()), 3), int(np.isfinite(g.phase_res).sum())]
                           for k, g in OB.groupby(np.where(OB.trig_code == 0, "untriggered_" + OB.kind, "triggered_" + OB.kind))}
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    tk = cd[(cd.idx == -1) & (cd.maker.str.lower() == WALLET)]
    tk = tk[(tk.sign_ms >= OWN0 * 1000) & (tk.sign_ms < END * 1000)].sign_ms.to_numpy(float) + 24.0
    j = np.searchsorted(s[untr], tk) - 1
    su = s[untr]
    okk = (j >= 0) & (tk - su[np.clip(j, 0, None)] <= 60000)
    rt = ((tk[okk] - su[j[okk]] + P / 2) % P) - P / 2
    out["takes_on_tick"] = [round(float((np.abs(rt) <= TOL).mean()), 3), int(okk.sum())]

    # step 2: lag from the latest non-own change in (t - P, t - 3] on the same book / sibling books
    def lag(arr, t):
        if arr is None:
            return np.nan
        k = np.searchsorted(arr, t - 3, side="right") - 1
        if k < 0:
            return np.nan
        d = t - arr[k]
        return d if d <= P else np.nan

    def sib_lag(ev, a, t):
        g = by_ev_a.get(ev)
        if g is None:
            return np.nan
        arr = np.sort(g.s[g.a != a].to_numpy(float))
        return lag(arr, t)

    sib_arr = {}
    for ev, g in by_ev_a.items():
        for a in g.a.unique():
            sib_arr[(ev, a)] = np.sort(g.s[g.a != a].to_numpy(float))
    import sys as _sys
    ALLB = "--all" in _sys.argv
    U = OB[(np.isfinite(OB.phase_res)) & ((OB.trig_code == 0) | ALLB)].copy()
    own_by_ev = {e: np.sort(g.s.to_numpy(float)) for e, g in OB.groupby("event")}
    rows = []
    for rr in U.itertuples():
        same = lag(by_a.get(rr.a), rr.s); sib = lag(sib_arr.get((rr.event, rr.a)), rr.s)
        rows.append({"cls": "on" if rr.on_tick else "off", "kind": rr.kind, "same": same, "sib": sib, "ctrl": 0})
        for k in (-6, -5, -4, -3, -2, 2, 3, 4, 5, 6):
            tc = rr.s + k * P
            oe = own_by_ev.get(rr.event)
            if oe is not None:
                jj = np.searchsorted(oe, tc)
                near = min(abs(tc - oe[min(jj, len(oe) - 1)]), abs(tc - oe[max(jj - 1, 0)]))
                if near <= 100:
                    continue
            rows.append({"cls": "on" if rr.on_tick else "off", "kind": rr.kind, "same": lag(by_a.get(rr.a), tc),
                         "sib": lag(sib_arr.get((rr.event, rr.a)), tc), "ctrl": 1})
    D = pd.DataFrame(rows)
    res2 = {}
    for (cls, ctrl), g in D.groupby(["cls", "ctrl"]):
        o = {"n": int(len(g))}
        for col in ("same", "sib"):
            x = g[col]
            o[f"{col}_any_in_tick"] = round(float(np.isfinite(x).mean()), 3)
            xf = x[np.isfinite(x)]
            o[f"{col}_lag_le_40ms"] = round(float((x <= 40).mean()), 3)
            o[f"{col}_lag_40_504ms"] = round(float(((x > 40) & (x <= P)).mean()), 3)
            o[f"{col}_lag_median_ms"] = round(float(xf.median()), 1) if len(xf) else None
        res2[f"{cls}_tick_{'control' if ctrl else 'own'}"] = o
    out["attribution"] = res2
    # lag histograms for own on/off-tick bursts (sibling books), 8 bins of 63 ms
    hist = {}
    for cls in ("on", "off"):
        x = D[(D.cls == cls) & (D.ctrl == 0)].sib.dropna().to_numpy()
        hist[cls] = np.histogram(x, bins=np.linspace(0, P, 9))[0].tolist()
        xc = D[(D.cls == cls) & (D.ctrl == 1)].sib.dropna().to_numpy()
        hist[cls + "_control_per_own"] = (np.histogram(xc, bins=np.linspace(0, P, 9))[0] / 10.0).round(1).tolist()
    out["sib_lag_hist_63ms_bins"] = hist
    out["population"] = "all own bursts (uncensored window)" if ALLB else "untriggered own bursts (no public event in [-300, 0] ms by definition)"
    for cls in ("on", "off"):
        x = D[(D.cls == cls) & (D.ctrl == 0)].same.dropna().to_numpy()
        hist[cls + "_same"] = np.histogram(x, bins=np.linspace(0, P, 9))[0].tolist()
        xc = D[(D.cls == cls) & (D.ctrl == 1)].same.dropna().to_numpy()
        hist[cls + "_same_control_per_own"] = (np.histogram(xc, bins=np.linspace(0, P, 9))[0] / 10.0).round(1).tolist()
    out["sib_lag_hist_63ms_bins"] = hist
    (RES / ((f"loop_attribution_all{SUF}.json") if ALLB else (f"loop_attribution{SUF}.json"))).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
