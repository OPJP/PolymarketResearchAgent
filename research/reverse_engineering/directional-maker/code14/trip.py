"""directional-maker iteration 14, X152 (panel iter13 mechanics P2, light form): are the module switch-offs drawdown trips?

See NOTES iteration 14 T7 for the pre-registration. Own-state description, reported, never counted.
    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/trip.py
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
NAMES = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
         "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
DEV = [(1791417600, 1793426400), (1793448000, 1793469600)]   # 10-08 .. 10-31 06:00, 10-31 12-18
FOLDS = {"build": (1791417600, 1792713600), "study": (1792713600, 1793059200), "validate_agg": (1793059200, 1793404800),
         "live_1031": (1793404800, 1793469600)}
COLS = ["timestamp", "type", "slug", "usdcSize", "side", "transactionHash", "asset", "size", "price"]


def load():
    parts = []
    for n in ("bosona", "almach", "momoney"):
        for p in (C / f"activity_{n}.parquet", C / "exam" / f"activity_{n}.parquet"):
            d = pd.read_parquet(p, columns=COLS); d["wallet"] = n; parts.append(d)
    a = pd.read_parquet(C / "live_activity_1793404800_1793426400.parquet")
    b = pd.read_parquet(C / "it9" / "act_1793448000_1793469600.parquet")
    for x in (a, b):
        if "wallet" not in x.columns:
            x["wallet"] = x.get("w", "x")
        x["wallet"] = x["wallet"].map(lambda v: NAMES.get(str(v).lower(), str(v)))
        parts.append(x[[c for c in COLS if c in x.columns] + ["wallet"]])
    D = pd.concat(parts, ignore_index=True)
    D = D.drop_duplicates(subset=["wallet", "type", "transactionHash", "asset", "size", "price", "timestamp"])
    D = D[D.type.isin(["TRADE", "MERGE", "REDEEM", "SPLIT"])]
    return D


def end_of(slug, last_ts):
    m = re.search(r"-updown-(5m|15m|4h)-(\d+)$", str(slug))
    if m:
        return int(m.group(2)) + {"5m": 300, "15m": 900, "4h": 14400}[m.group(1)]
    return int(last_ts)


def main():
    D = load()
    cf = np.where(D.type == "TRADE", np.where(D.side == "BUY", -1.0, 1.0) * D.usdcSize, np.where(D.type == "SPLIT", -D.usdcSize, D.usdcSize))
    D["cf"] = cf
    g = D.groupby("slug").agg(cf=("cf", "sum"), last=("timestamp", "max"))
    g["end"] = [end_of(s, l) for s, l in zip(g.index, g["last"])]
    book = g.groupby("end").cf.sum().sort_index()
    bt, bv = book.index.to_numpy(np.int64), np.cumsum(book.to_numpy())
    # module activity on the 5m / 15m grids
    tr = D[D.type == "TRADE"]
    res = {"rows": int(len(D)), "markets": int(len(g))}
    for fam, L, runmin in (("btc_5m", 300, 12), ("btc_15m", 900, 4)):
        st = tr.slug.str.extract(rf"^btc-updown-{fam[4:]}-(\d+)$")[0].dropna().astype(np.int64)
        act = set(st.unique())
        grid = np.arange(1791417600, 1793469600, L)
        dev = np.zeros(len(grid), bool)
        for a, b in DEV:
            dev |= (grid >= a) & (grid + L <= b)
        on = np.array([s in act for s in grid])
        # off-run starts: first inactive after an active window with >= runmin consecutive inactive windows (all dev)
        label = np.zeros(len(grid), int); risk = np.zeros(len(grid), bool); since_on = np.full(len(grid), -1, np.int64)
        cur_on_start = -1
        for i in range(1, len(grid)):
            if on[i] and not on[i - 1]:
                cur_on_start = grid[i]
            if on[i - 1] and dev[i] and dev[i - 1]:
                risk[i] = True
                since_on[i] = cur_on_start
                if not on[i]:
                    j = i
                    while j < len(grid) and not on[j] and dev[j]:
                        j += 1
                    if j - i >= runmin:
                        label[i] = 1
        idx = np.where(risk)[0]
        s = grid[idx]
        # cumulative PnL booked by s (windows ended <= s)
        k = np.searchsorted(bt, s, side="right") - 1
        cum = np.where(k >= 0, bv[np.clip(k, 0, None)], 0.0)
        day0 = (s - 3600) // 86400 * 86400 + 3600   # last 01:00 UTC at or before s
        k0 = np.searchsorted(bt, day0, side="right") - 1
        base0 = np.where(k0 >= 0, bv[np.clip(k0, 0, None)], 0.0)
        lvl = cum - base0
        # running peak since day0: max of bv over (day0, s]
        peak = np.array([max(0.0, float(bv[k0i + 1:ki + 1].max() - b0) if ki > k0i else 0.0)
                         for k0i, ki, b0 in zip(k0, k, base0)])
        dd = np.maximum(peak - lvl, 0.0)
        ro = since_on[idx]
        kr = np.searchsorted(bt, ro, side="right") - 1
        baser = np.where(kr >= 0, bv[np.clip(kr, 0, None)], 0.0)
        lvl_r = cum - baser
        peak_r = np.array([max(0.0, float(bv[a + 1:b + 1].max() - c) if b > a else 0.0) for a, b, c in zip(kr, k, baser)])
        dd_r = np.maximum(peak_r - lvl_r, 0.0)
        et = pd.to_datetime(s - 4 * 3600, unit="s")
        dw, hr = np.asarray(et.day_of_week), np.asarray(et.hour)
        gate = (np.isin(dw, [4, 5, 6]) & (hr >= 18)) | (np.isin(dw, [5, 6, 0]) & (hr < 9))
        y = label[idx]
        X = pd.DataFrame({"s": s, "y": y, "M1_dd_day": dd, "M2_lvl_day": -lvl, "M3_dd_on": dd_r, "M4_lvl_on": -lvl_r, "gate": gate.astype(float)})
        r = {"events_total": int(y.sum()), "at_risk": int(len(y))}
        bu = X[(X.s >= FOLDS["build"][0]) & (X.s < FOLDS["build"][1])]
        for fo, (a, b) in FOLDS.items():
            gg = X[(X.s >= a) & (X.s < b)]
            rr = {"events": int(gg.y.sum()), "at_risk": int(len(gg))}
            if gg.y.nunique() == 2:
                for m in ("M1_dd_day", "M2_lvl_day", "M3_dd_on", "M4_lvl_on", "gate"):
                    rr[m + "_auc"] = round(float(roc_auc_score(gg.y, gg[m])), 3)
                    if m != "gate" and bu.y.sum():
                        D_ = float(bu.loc[bu.y == 1, m].median())
                        hi = gg[m] >= D_
                        rr[m + "_rate_above_vs_below_buildmedian"] = [round(float(gg.y[hi].mean()), 4) if hi.any() else None,
                                                                      round(float(gg.y[~hi].mean()), 4) if (~hi).any() else None, round(D_, 1)]
            r[fo] = rr
        if fam == "btc_5m":
            ev = X[X.y == 1]
            r["build_study_live_event_values"] = [
                {"t": pd.to_datetime(int(t), unit="s").strftime("%a %m-%d %H:%M"), "dd_day": round(float(a1), 0), "lvl_day": round(float(-a2), 0),
                 "dd_on": round(float(a3), 0)} for t, a1, a2, a3 in zip(ev.s, ev.M1_dd_day, ev.M2_lvl_day, ev.M3_dd_on)
                if not (FOLDS["validate_agg"][0] <= t < FOLDS["validate_agg"][1])]
        res[fam] = r
    (HERE.parent / "results" / "iter14_trip.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
