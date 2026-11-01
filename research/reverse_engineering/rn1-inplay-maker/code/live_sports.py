"""X2 / A5a: Polymarket sports websocket score changes against RN1's order signing times (live lab, development
units only). Pre-registered (NOTES.md, iteration 1): decisions = RN1 filled-order signing times (B1, censored to
filled orders); events = score changes per game from the sports websocket, receive time corrected by the recorder
clock offset (median server - receive time of the clob records of the same block); units = games (first to last
sports message within the block); lags: max_lag_s 120 (core +-60 s) and 20 (core +-10 s); swap null.
Writes results/live_sports_<a>.json.
"""
from __future__ import annotations

import json
import sys
import time
import zlib
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import indicators as ind  # noqa: E402
import live  # noqa: E402
from common import C, R, W  # noqa: E402

ALLOW_SEALED = False


def gen(feed, a, b):
    for h in range(a, b, 3600):
        try:
            yield from live.iter_live(feed, h, h + 3600, allow_sealed=ALLOW_SEALED)
        except zlib.error:
            continue


def game_ids(cids):
    out = {}
    cli = httpx.Client(timeout=30)
    cids = sorted(set(cids))
    for i in range(0, len(cids), 20):
        part = cids[i:i + 20]
        for closed in (False, True):
            miss = [c for c in part if c not in out]
            if not miss:
                break
            params = [("condition_ids", c) for c in miss] + [("limit", 40)] + ([("closed", "true")] if closed else [])
            try:
                data = cli.get("https://gamma-api.polymarket.com/markets", params=params).json()
            except Exception:  # noqa: BLE001
                data = []
            for m in data or []:
                ev = (m.get("events") or [{}])[0]
                out[m.get("conditionId")] = {"gameId": ev.get("gameId"), "event_slug": ev.get("slug")}
            time.sleep(0.25)
    return out


def main(a):
    b = a + 6 * 3600
    od = pd.read_parquet(C / "live" / f"orders_{a}.parquet")
    od["is_rn1"] = od["maker"].str.lower() == W
    rn = od[od["is_rn1"]].drop_duplicates("salt").copy()
    gmap = game_ids(rn["cond"].unique())
    rn["gameId"] = rn["cond"].map(lambda c: (gmap.get(c) or {}).get("gameId"))
    # clock offset of the recorder: median(server - receive) of clob records, plus ~50 ms of network latency
    offs = []
    for k, r in enumerate(gen("clob_wallets", a, a + 3 * 3600)):
        if r.get("s"):
            offs.append(r["s"] - r["t"])
        if k > 20000:
            break
    off_ms = float(np.median(offs)) + 50.0 if offs else 0.0
    # score changes per game
    last = {}
    ev_rows, span = [], {}
    for r in gen("sports", a, b):
        try:
            m = json.loads(r["m"])
        except (TypeError, ValueError):
            continue
        if not isinstance(m, dict) or "gameId" not in m:
            continue
        g = m["gameId"]
        t = (r["t"] + off_ms) / 1000.0
        sp = span.setdefault(g, [t, t, m.get("leagueAbbreviation")])
        sp[1] = t
        sc = m.get("score")
        if g in last and sc is not None and last[g] is not None and sc != last[g]:
            ev_rows.append((g, t, last[g], sc, m.get("leagueAbbreviation"), m.get("period")))
        if sc is not None:
            last[g] = sc
    ev = pd.DataFrame(ev_rows, columns=["gameId", "t", "old", "new", "league", "period"])
    rn_g = rn[rn["gameId"].notna()].copy()
    rn_g["gameId"] = rn_g["gameId"].astype(int)
    games = sorted(set(rn_g["gameId"]) & set(span))
    out = {"block": a, "clock_offset_ms": off_ms, "rn1_orders": int(len(rn)), "rn1_orders_with_gameid": int(len(rn_g)),
           "games_rn1": int(rn_g["gameId"].nunique()), "games_in_sports_ws": int(len(games)),
           "score_changes_in_those_games": int(ev["gameId"].isin(games).sum()),
           "leagues": ev[ev["gameId"].isin(games)]["league"].value_counts().head(10).to_dict()}
    if games:
        # concurrent games overlap in time: put each game on its own time axis (offset k * 1e5 s) so that units do
        # not overlap and a game's decisions are only compared with that game's events
        units, dec, evt = [], [], []
        for k, g in enumerate(games):
            o = k * 1e5 - span[g][0]
            units.append((span[g][0] + o, span[g][1] + 1.0 + o))
            dec.append(rn_g.loc[rn_g["gameId"] == g, "sign_ms"].to_numpy() / 1000.0 + o)
            evt.append(ev.loc[ev["gameId"] == g, "t"].to_numpy() + o)
        dec, evt = np.concatenate(dec), np.concatenate(evt)
        keep = np.zeros(len(dec), bool)
        for u0, u1 in units:
            keep |= (dec >= u0) & (dec < u1)
        dec = dec[keep]
        for mx in (120.0, 20.0):
            try:
                res = ind.event_study(dec, evt, units, max_lag_s=mx, bin_s=1.0, n_null=500)
                out[f"event_study_maxlag{int(mx)}"] = {k: res.get(k) for k in ("null", "units_in_null", "n_units", "n_events",
                                                       "shape_peak_lag_s", "shape_width_s", "shape_lift", "peak_lag_s", "peak_lift",
                                                       "median_lift", "p_level", "p_shape", "p_link", "level_peak_in_flank")}
            except Exception as e:  # noqa: BLE001
                out[f"event_study_maxlag{int(mx)}"] = {"error": str(e)[:200]}
        # raw counts of RN1 signings (filled orders) and fills around score changes, per 5-s bin
        fills = od[od["is_rn1"] & od["cond"].isin(rn_g["cond"])].copy()
        fills["gameId"] = fills["cond"].map(lambda c: (gmap.get(c) or {}).get("gameId"))
        edges = np.arange(-60, 65, 5)
        hs, hf = np.zeros(len(edges) - 1), np.zeros(len(edges) - 1)
        for g, sub in ev[ev["gameId"].isin(games)].groupby("gameId"):
            s_g = rn_g.loc[rn_g["gameId"] == g, "sign_ms"].to_numpy() / 1000.0
            f_g = fills.loc[fills["gameId"] == g, "bts"].to_numpy()
            for t in sub["t"]:
                hs += np.histogram(s_g - t, edges)[0]
                hf += np.histogram(f_g - t, edges)[0]
        out["sign_counts_5s_bins_-60_60"] = hs.astype(int).tolist()
        out["fill_counts_5s_bins_-60_60"] = hf.astype(int).tolist()
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(R / "results" / f"live_sports_{a}.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main(int(sys.argv[1]))
