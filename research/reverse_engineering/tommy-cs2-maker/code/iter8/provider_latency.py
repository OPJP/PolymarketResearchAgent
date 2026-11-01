"""Iteration 8, X103 (information panel iter7 P3): Polymarket's own data provider as a latency yardstick.

For every map end of the CS2 / Dota 2 events whose game start is in the 10-31 12-18 development block (development
units only): market time = the first print of the map's winner token at >= 0.985 with no later print below 0.95
(data-api trades, block-time stamps); socket time = the first sports-socket message (shared recorder, receive clock)
whose map score shows that map decided (sum of the map score >= map number). lag = socket - market. Lower envelope
(min, p10, median) by GRID / non-GRID, with an event bootstrap of the p10. The socket re-sends each game about every
20 s, so the envelope bounds the provider's own delay. Output: results/provider_latency.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
KEY = "tommy-cs2-maker"
A, B = 1793448000, 1793469600


def main():
    u = pd.read_parquet(OUT / "universe_t0.parquet")
    u = u[(u.gs_ts >= A) & (u.gs_ts < B)]
    u = u[u.gs_ts.map(lambda g: not sealed.is_sealed(int(g), KEY))]
    u = u[u.smt == "child_moneyline"].copy()
    # map number from the market slug ("-gameN"); development units only, so the Gamma record may be read
    mk, _ = PolymarketData().markets_by_condition(sorted(u.cid))
    u["map_no"] = u.cid.map(lambda c: (lambda m: int(m.group(1)) if m else None)(re.search(r"-game(\d)$", str((mk.get(c) or {}).get("slug", "")))))
    u = u[u.map_no.notna()].copy()
    pid = {}
    for r in u.drop_duplicates("event_slug").itertuples():
        try:
            pid[int(float(r.pandascore_id))] = r.event_slug
        except Exception:  # noqa: BLE001
            pass
    # socket: per gameId, (recv ms, map score sum)
    sock = {}
    for h0 in range(A, B, 3600):  # hour by hour: a damaged hour file must not end the read (tool bug, NOTES)
      try:
        for r in live.iter_live("sports", h0, h0 + 3600):
            try:
                m = json.loads(r["m"])
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(m, dict):
                continue
            g = m.get("gameId")
            if g not in pid:
                continue
            sc = str(m.get("score") or "")
            parts = sc.split("|")
            ms = None
            for p_ in parts:
                mm = re.fullmatch(r"(\d)-(\d)", p_.strip())
                if mm:
                    ms = int(mm.group(1)) + int(mm.group(2))
            if ms is None:
                continue
            sock.setdefault(pid[g], []).append((int(r["t"]), ms))
      except Exception as e:  # noqa: BLE001
        print("feed", h0, type(e).__name__)
    pm = PolymarketData()
    rows = []
    for r in u.itertuples():
        x, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 600, end=int(min(r.gs_ts + 6 * 3600, B + 6 * 3600)), taker_only=False)
        if not x:
            continue
        d = pd.DataFrame(x)
        d["p0"] = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        d = d.sort_values("timestamp")
        for w in (0, 1):
            pw = d.p0.to_numpy() if w == 0 else 1 - d.p0.to_numpy()
            ts = d.timestamp.to_numpy(float)
            later_min = np.minimum.accumulate(pw[::-1])[::-1]
            ok = np.where((pw >= 0.985) & (later_min >= 0.95))[0]
            if len(ok):
                tm = ts[ok[0]]
                if tm > B:  # the decision falls after the block: the socket record is cut there
                    continue
                s = sock.get(r.event_slug, [])
                after = [t for t, ms in s if ms >= r.map_no and t / 1000 >= tm - 600]
                ts_ = min(after) / 1000 if after else None
                rows.append({"event": r.event_slug, "cid": r.cid, "map_no": int(r.map_no), "grid": r.grid_series_id is not None and r.grid_series_id == r.grid_series_id,
                             "series": r.series, "market_t": tm, "socket_t": ts_, "lag_s": (ts_ - tm) if ts_ else None,
                             "socket_msgs": len(s)})
                break
    R = pd.DataFrame(rows)
    res = {"map_ends": int(len(R)), "with_socket": int(R.lag_s.notna().sum()) if len(R) else 0}
    if len(R):
        rng = np.random.default_rng(2)
        for gname, g in R[R.lag_s.notna()].groupby("grid"):
            v = g.lag_s.to_numpy(float)
            o = {"n": int(len(v)), "events": int(g.event.nunique()), "min_s": round(float(v.min()), 1),
                 "p10_s": round(float(np.percentile(v, 10)), 1), "median_s": round(float(np.median(v)), 1),
                 "max_s": round(float(v.max()), 1)}
            ev = g.event.unique()
            bs = [np.percentile(np.concatenate([g[g.event == e].lag_s.to_numpy(float) for e in rng.choice(ev, len(ev))]), 10) for _ in range(1000)]
            o["p10_ci95"] = [round(float(x), 1) for x in np.percentile(bs, [2.5, 97.5])]
            res["grid" if gname else "non_grid"] = o
        res["rows"] = R[["event", "map_no", "grid", "series", "lag_s"]].round(1).to_dict("records")
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(RES / "provider_latency.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
