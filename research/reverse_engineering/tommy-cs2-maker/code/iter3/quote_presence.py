"""Iteration 3, assumptions panel P2 step 4 (X31): does the wallet quote in non-GRID events where it never gets filled?

Own recorder tommy_cs2_near (every CS2 match / map-winner market in play, 10-31 14:50 UTC on, server clock), dev-unit
markets only (dev_markets.parquet). Its quoting fingerprint: 100-share BUY levels at whole cents, added and pulled in
bursts. Per market: the rate per in-play hour of level changes of exactly +100 / -100 shares at whole-cent prices
within 5c of the touch, and of +100 changes that coincide (same server ms) with a +100 change on the mirrored side
(both tokens quoted together). Groups: markets the wallet traded, untraded non-GRID markets, untraded GRID markets
(gridSeriesId from the Gamma listing projection of each event: development units only). Output:
results/quote_presence.json
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, read  # noqa: E402
from polyrea.adapters.http import shared_client  # noqa: E402

OWN0 = 1793458232000


def grid_flags(events):
    h = shared_client()
    out = {}
    for ev in events:
        d, _ = h.get_json("https://gamma-api.polymarket.com/events", {"slug": ev}, adapter="gamma.events", max_age=3600)
        meta = (d[0].get("eventMetadata") if d else None) or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:  # noqa: BLE001
                meta = {}
        out[ev] = {"grid": bool(meta.get("gridSeriesId")), "league": meta.get("league")}
    return out


def main():
    m = pd.read_parquet(OUT / "dev_markets.parquet")
    gf = grid_flags(sorted(m.event.unique()))
    m["grid"] = m.event.map(lambda e: gf[e]["grid"])
    m["league"] = m.event.map(lambda e: gf[e]["league"])
    tok0 = set(m.tok0)
    ow = read("tommy_cs2_near", tok0, OWN0 / 1000, time.time())
    books, span = {}, defaultdict(lambda: [np.inf, -np.inf])
    cnt = defaultdict(lambda: {"add100": 0, "rem100": 0, "add100_pair": 0, "changes": 0})
    for r in sorted([r for r in ow if r["k"] in ("f", "pc")], key=lambda r: (r["s"], r["t"])):
        a = r["a"]
        sp = span[a]
        sp[0], sp[1] = min(sp[0], r["s"]), max(sp[1], r["s"])
        if r["k"] == "f":
            books[a] = ({float(p): float(z) for p, z in r["b"]}, {float(p): float(z) for p, z in r["o"]})
            continue
        if a not in books:
            continue
        bd, od = books[a]
        adds = {"BUY": 0, "SELL": 0}
        for side, p, z in r["c"]:
            bk = bd if side == "BUY" else od
            p, z = float(p), float(z)
            old = bk.get(p, 0.0)
            dz = round(z - old, 2)
            whole = abs(p * 100 - round(p * 100)) < 1e-6
            cnt[a]["changes"] += 1
            if whole and dz == 100:
                cnt[a]["add100"] += 1
                adds[side] += 1
            if whole and dz == -100:
                cnt[a]["rem100"] += 1
            if z == 0:
                bk.pop(p, None)
            else:
                bk[p] = z
        if adds["BUY"] and adds["SELL"]:
            cnt[a]["add100_pair"] += 1
    rows = []
    for r in m.itertuples():
        a = r.tok0
        if a not in span or not np.isfinite(span[a][0]):
            continue
        hrs = max((span[a][1] - span[a][0]) / 3.6e6, 1e-6)
        if hrs < 0.25:
            continue
        c = cnt[a]
        rows.append({"event": r.event, "league": r.league, "grid": r.grid, "traded": r.wallet_trades > 0, "hours": hrs,
                     "add100_per_h": c["add100"] / hrs, "rem100_per_h": c["rem100"] / hrs, "pair_per_h": c["add100_pair"] / hrs,
                     "changes_per_h": c["changes"] / hrs})
    x = pd.DataFrame(rows)
    x["grp"] = np.where(x.traded, "traded", np.where(x.grid, "untraded_GRID", "untraded_nonGRID"))
    res = {"markets": int(len(x)),
           "by_group": x.groupby("grp").agg(markets=("event", "size"), hours=("hours", "sum"), add100_per_h_median=("add100_per_h", "median"),
                                            add100_per_h_mean=("add100_per_h", "mean"), pair_per_h_median=("pair_per_h", "median"),
                                            changes_per_h_median=("changes_per_h", "median")).round(2).reset_index().to_dict("records"),
           "per_market": x.sort_values(["grp", "add100_per_h"], ascending=[True, False]).round(2)[
               ["grp", "event", "league", "hours", "add100_per_h", "pair_per_h", "changes_per_h"]].to_dict("records")}
    json.dump(res, open(RES / "quote_presence.json", "w"), indent=1, default=str)
    print(json.dumps(res["by_group"], indent=1, default=str))
    print(x.sort_values(["grp", "add100_per_h"], ascending=[True, False]).round(2)[["grp", "event", "league", "hours", "add100_per_h", "pair_per_h"]].to_string())


if __name__ == "__main__":
    main()
