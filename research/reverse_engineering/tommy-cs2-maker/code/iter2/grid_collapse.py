"""R8 mechanism test on the own recorder (tommy_cs2_near, all CS2 match/map markets): do depth collapses happen in GRID
events too, and how much stale depth is left after them? Only units whose gameStartTime is in a development block are
read (games that started in a sealed block are dropped by start time, whatever the receive time of their records)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from polyrea.adapters.http import shared_client  # noqa: E402
import live  # noqa: E402
import sealed  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker"
KEY = "tommy-cs2-maker"
T0 = 1793404800


def main():
    end = time.time() - 30
    start = 1793458232
    subs, recs, trades = {}, [], []
    state, last = {}, {}
    for r in live.iter_live("tommy_cs2_near", start, end):
        k = r.get("k")
        if k == "sub":
            for cid, v in r["m"].items():
                subs[v[0]] = (cid, int(v[2]), v[3])
            continue
        a = r.get("a")
        if a not in subs:
            continue
        gs = subs[a][1]
        if gs < T0 or sealed.is_sealed(gs, KEY):
            continue  # sealed unit: never read further
        if k == "f":
            state[a] = ({float(p): float(z) for p, z in r["b"]}, {float(p): float(z) for p, z in r["o"]})
        elif k == "pc" and a in state:
            bd, od = state[a]
            for sd, p, z in r["c"]:
                bk = bd if sd == "BUY" else od
                if float(z) == 0:
                    bk.pop(float(p), None)
                else:
                    bk[float(p)] = float(z)
        elif k == "x":
            trades.append((r["t"], a))
            continue
        else:
            continue
        if r["t"] - last.get(a, 0) < 100 or a not in state:
            continue
        last[a] = r["t"]
        bd, od = state[a]
        bb = max(bd) if bd else np.nan
        ba = min(od) if od else np.nan
        recs.append((r["t"], a, sum(z for p, z in bd.items() if p >= bb - 0.03 - 1e-9), sum(z for p, z in od.items() if p <= ba + 0.03 + 1e-9)))
    bk = pd.DataFrame(recs, columns=["t", "a", "Db", "Do"]).sort_values("t")
    tr = pd.DataFrame(trades, columns=["t", "a"]).sort_values("t")
    slugs = sorted({subs[a][2].rsplit("-game", 1)[0] for a in bk.a.unique()})
    h = shared_client()
    grid = {}
    for s in slugs:
        try:
            d, _ = h.get_json("https://gamma-api.polymarket.com/events", {"slug": s}, adapter="gamma.events.slug", max_age=3600)
            md = (d[0].get("eventMetadata") or {}) if d else {}
            if isinstance(md, str):
                md = json.loads(md)
            grid[s] = md.get("gridSeriesId") is not None
        except Exception:  # noqa: BLE001
            grid[s] = None
    rows = []
    for a, b in bk.groupby("a"):
        tt = b.t.to_numpy()
        if len(tt) < 50:
            continue
        trt = tr[tr.a == a].t.to_numpy()
        hours = (tt[-1] - tt[0]) / 3.6e6
        for col in ("Do", "Db"):
            D = b[col].to_numpy()
            n_ev, rem = 0, []
            lastev = -1e18
            for i in range(len(tt)):
                lo, hi = np.searchsorted(tt, tt[i] - 1500), np.searchsorted(tt, tt[i] - 400, side="right")
                if hi <= lo:
                    continue
                ref = D[lo:hi].max()
                if ref < 200 or D[i] > 0.5 * ref:
                    continue
                k = np.searchsorted(trt, tt[i] - 1500)
                if k < len(trt) and trt[k] <= tt[i]:
                    continue
                if tt[i] - lastev < 3000:
                    continue
                lastev = tt[i]
                n_ev += 1
                rem.append(D[i] / ref)
            rows.append({"a": a, "slug": subs[a][2], "grid": grid.get(subs[a][2].rsplit("-game", 1)[0]), "hours": hours, "events": n_ev,
                         "deep_share": float(np.mean(np.array(rem) <= 0.1)) if rem else np.nan})
    x = pd.DataFrame(rows)
    res = {"tokens": int(x.a.nunique()), "events_by_grid": {}}
    for g, s in x.groupby("grid", dropna=False):
        res["events_by_grid"][str(g)] = {"markets": int(s.a.nunique()), "market_hours": round(float(s.drop_duplicates("a").hours.sum()), 2),
                                         "collapses_per_market_hour": round(float(s.events.sum() / max(s.drop_duplicates("a").hours.sum(), 1e-9)), 1),
                                         "deep_share": round(float((s.deep_share * s.events).sum() / max(s.events.sum(), 1)), 3)}
    json.dump(res, open(RES / "results/grid_collapse.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
