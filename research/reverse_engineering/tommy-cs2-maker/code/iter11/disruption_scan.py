"""X157 step 1-2 (assumptions panel iter-10 P5), development proxy: exchange-side disruptions in 16-22 Oct seen as
print droughts across every in-play CS2 match / map market we hold a windowed taker tape for (traded and untraded,
tapes/<cid>_tkw.parquet, [gs - 1 h, gs + 4 h 10 min]), and whether the wallet's process (merge loop, orders) ran through.

Per UTC minute: markets in play (gs <= t < gs + 150 min) and taker prints across them. A drought = a run of >= 3 minutes
with >= 8 markets in play and 0 prints in all of them; its expected print count from the median per-market rate.
For each drought: the wallet's maker orders signed in the drought and in the 30 min before / after, and its MERGE rows in
the same windows (activity_dev). Output: results/disruption_scan.json
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
C = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
T0, H = 1792108800, 1792713600


def main():
    u = pd.read_parquet(C / "universe.parquet", columns=["cid", "gs_ts", "smt"])
    gs = dict(zip(u.cid, u.gs_ts))
    nmin = (H - T0) // 60
    inplay = np.zeros(nmin, np.int32)
    prints = np.zeros(nmin, np.int32)
    n_mk = 0
    for f in glob.glob(str(C / "tapes/*_tkw.parquet")):
        cid = Path(f).name.split("_")[0]
        g = gs.get(cid)
        if g is None or not (T0 <= g < H):
            continue
        n_mk += 1
        a = max(0, int((g - T0) // 60))
        b = min(nmin, int((g + 9000 - T0) // 60))
        inplay[a:b] += 1
        t = pd.read_parquet(f, columns=["timestamp"]).timestamp.to_numpy(float)
        t = t[(t >= g) & (t < g + 9000) & (t >= T0) & (t < H)]
        idx = ((t - T0) // 60).astype(int)
        np.add.at(prints, idx, 1)
    busy = inplay >= 8
    rate = np.median(prints[busy] / np.maximum(inplay[busy], 1)) if busy.any() else np.nan
    dro = []
    i = 0
    while i < nmin:
        if busy[i] and prints[i] == 0:
            j = i
            while j < nmin and busy[j] and prints[j] == 0:
                j += 1
            if j - i >= 3:
                dro.append((i, j))
            i = j
        else:
            i += 1
    o = pd.read_parquet(C / "orders.parquet", columns=["sign_ts", "role"])
    st = np.sort(o[o.role == "maker"].sign_ts.to_numpy(float))
    act = pd.read_parquet(C / "activity_dev.parquet", columns=["timestamp", "type"])
    mg = np.sort(act[act.type == "MERGE"].timestamp.to_numpy(float))

    def cnt(arr, a, b):
        return int(np.searchsorted(arr, b) - np.searchsorted(arr, a))

    rows = []
    for a, b in dro:
        ta, tb = T0 + a * 60, T0 + b * 60
        rows.append({"start_utc": str(pd.to_datetime(ta, unit="s")), "minutes": int(b - a),
                     "markets_in_play_median": int(np.median(inplay[a:b])),
                     "expected_prints": round(float(rate * inplay[a:b].sum()), 1),
                     "wallet_maker_orders_during": cnt(st, ta, tb), "wallet_maker_orders_30min_before": cnt(st, ta - 1800, ta),
                     "wallet_maker_orders_30min_after": cnt(st, tb, tb + 1800),
                     "merges_during": cnt(mg, ta, tb), "merges_30min_before": cnt(mg, ta - 1800, ta), "merges_30min_after": cnt(mg, tb, tb + 1800)})
    out = {"markets": n_mk, "busy_minutes": int(busy.sum()), "median_prints_per_market_minute": round(float(rate), 3),
           "zero_print_busy_minutes": int((busy & (prints == 0)).sum()), "droughts_ge_3min": rows}
    (RES / "disruption_scan.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1)[:3000])


if __name__ == "__main__":
    main()
