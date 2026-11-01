"""E3 screen (pre-registered in NOTES.md, iteration 1), event-state family, live BUILD block(s), part (a):
decisions = B1 signing times of RN1's filled orders; events from the sports websocket per game:
 score_any, score_soccer, score_tennis, score_cs2, score_usfb, period_change, first_live.
Lag ranges: max_lag_s 20, 120, 1200; swap null with league-class strata; units = games on separate time axes.
BH over the whole family (indicators.screen). Writes results/e3_screen_live_<a>.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_sports as ls  # noqa: E402
from common import C, R, W  # noqa: E402

ind = ls.ind
SOCCER = {"epl", "lal", "bun", "sea", "fl1", "ucl", "uel", "elc", "el1", "el2", "bl2", "ere", "tur", "es2", "cze1", "svk1",
          "enl", "itsb", "por", "sco", "bra", "arg", "mex", "mls", "jap", "kor", "aus", "den", "nor", "swe", "bel", "aut", "sui", "gre", "pol"}
TENNIS = {"atp", "wta", "challenger", "wta challenger", "itf"}


def main(a):
    b = a + 6 * 3600
    od = pd.read_parquet(C / "live" / f"orders_{a}.parquet")
    rn = od[od["maker"].str.lower() == W].drop_duplicates("salt").copy()
    gmap = ls.game_ids(rn["cond"].unique())
    rn["gameId"] = rn["cond"].map(lambda c: (gmap.get(c) or {}).get("gameId"))
    rn = rn[rn["gameId"].notna()]
    rn["gameId"] = rn["gameId"].astype(int)
    offs = []
    for k, r in enumerate(ls.gen("clob_wallets", a, a + 3 * 3600)):
        if r.get("s"):
            offs.append(r["s"] - r["t"])
        if k > 20000:
            break
    off = (float(np.median(offs)) + 50.0) / 1000.0 if offs else 0.0
    last, span, ev = {}, {}, []
    for r in ls.gen("sports", a, b):
        try:
            m = json.loads(r["m"])
        except (TypeError, ValueError):
            continue
        if not isinstance(m, dict) or "gameId" not in m:
            continue
        g = m["gameId"]
        t = r["t"] / 1000.0 + off
        lg = str(m.get("leagueAbbreviation") or "").lower()
        sp = span.setdefault(g, [t, t, lg])
        sp[1] = t
        prev = last.get(g)
        cur = (m.get("score"), m.get("period"), bool(m.get("live")))
        if prev is not None:
            if cur[0] is not None and prev[0] is not None and cur[0] != prev[0]:
                ev.append((g, t, "score", lg))
            if cur[1] is not None and prev[1] is not None and cur[1] != prev[1]:
                ev.append((g, t, "period", lg))
            if cur[2] and not prev[2]:
                ev.append((g, t, "live_on", lg))
        elif cur[2]:
            pass  # already live at the first message: not a first occurrence inside the block
        last[g] = cur
    ev = pd.DataFrame(ev, columns=["gameId", "t", "kind", "league"])
    games = sorted(set(rn["gameId"]) & set(span))
    pos = {g: k * 1e5 - span[g][0] for k, g in enumerate(games)}
    units = [(span[g][0] + pos[g], span[g][1] + 1.0 + pos[g]) for g in games]
    strata = [("soccer" if span[g][2] in SOCCER else "tennis" if span[g][2] in TENNIS else span[g][2]) for g in games]
    dec = np.concatenate([rn.loc[rn["gameId"] == g, "sign_ms"].to_numpy() / 1000.0 + pos[g] for g in games])
    keep = np.zeros(len(dec), bool)
    for u0, u1 in units:
        keep |= (dec >= u0) & (dec < u1)
    dec = dec[keep]
    e = ev[ev["gameId"].isin(games)].copy()
    e["tt"] = e["t"] + e["gameId"].map(pos)
    defs = {
        "score_any": e["kind"] == "score",
        "score_soccer": (e["kind"] == "score") & e["league"].isin(SOCCER),
        "score_tennis": (e["kind"] == "score") & e["league"].isin(TENNIS),
        "score_cs2": (e["kind"] == "score") & (e["league"] == "cs2"),
        "score_usfb": (e["kind"] == "score") & e["league"].isin({"cfb", "nfl"}),
        "period_change": e["kind"] == "period",
        "first_live": e["kind"] == "live_on",
    }
    indicators = {}
    for name, msk in defs.items():
        tt = np.sort(e.loc[msk, "tt"].to_numpy())
        if len(tt) >= 5:
            indicators[name] = tt
    out = {"block": a, "games": len(games), "decisions": int(len(dec)), "n_events": {k: int(len(v)) for k, v in indicators.items()}}
    rows = []
    for mx in (20.0, 120.0, 1200.0):
        try:
            sc = ind.screen(dec, {f"{k}@{int(mx)}": (v, None) for k, v in indicators.items()}, units, max_lag_s=mx, bin_s=1.0 if mx <= 120 else 5.0,
                            n_null=500, strata=strata)
        except Exception as ex:  # noqa: BLE001
            out[f"error_{int(mx)}"] = str(ex)[:300]
            continue
        for r in sc:
            rows.append({k: r.get(k) for k in ("name", "n_events", "null", "units_in_null", "shape_peak_lag_s", "shape_width_s", "shape_lift",
                                               "peak_lag_s", "peak_lift", "median_lift", "p_level", "p_shape", "p_link", "q_bh",
                                               "level_peak_in_flank")})
    # one BH over the whole family (all lag ranges)
    if rows:
        q = ind.bh(np.array([r["p_link"] if r["p_link"] is not None else 1.0 for r in rows]))
        for r, qq in zip(rows, q):
            r["q_family"] = float(qq)
    out["rows"] = rows
    out["survivors_q10"] = [r["name"] for r in rows if r.get("q_family", 1) <= 0.10]
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(R / "results" / f"e3_screen_live_{a}.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main(int(sys.argv[1]))
