"""Iteration 9, X120 step 3 (information panel iter8 P3): on which game clock does the PUBLIC market move in GRID-flagged
Dota 2 events (official data) vs non-GRID events? Per map market of development events (game start 10-16..10-22):
OpenDota match found in /proMatches by team names and start time (map order by start time); public anchors = first print
of each >= 3c move in 10 s (block time, taker tapes); D-scan as dota_market_align.py (anchor 0-10 s after a kill of the
gaining team minus the other team, side-label null, 200 draws). D_market - pre-game (start_time -> horn ~ 90-150 s) is the
market's lag behind the game: near 0-20 s = real-time (server / official) data; >= 100 s = the broadcast delay. The
PARI Universe maps (non-GRID, the wallet's) sat at D_market ~1040-1060 s (900-s spectator delay).
Output: results/dota_grid_market_clock.json"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import shared_client  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
B0, H = 1792108800, 1792713600


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def scan(anchors, kt, ks, edges, win):
    sb, so = np.zeros(len(edges)), np.zeros(len(edges))
    for rel, sd in anchors:
        for arr, sel in ((sb, ks == sd), (so, ks != sd)):
            hit = np.zeros(len(edges), bool)
            for L in rel - kt[sel]:
                lo, hi = np.searchsorted(edges, L - win), np.searchsorted(edges, L, side="right")
                hit[lo:hi] = True
            arr += hit
    return sb, so


def main():
    h = shared_client()
    pm = PolymarketData()
    # pro matches started in the development window (OpenDota pages are cached; only matches before H are kept)
    pro, last = [], None
    for _ in range(60):
        d, _ = h.get_json("https://api.opendota.com/api/proMatches", {} if last is None else {"less_than_match_id": last},
                          adapter="opendota.pro", max_age=None if last else 86400)
        if not d:
            break
        pro += [m for m in d if B0 - 86400 <= m.get("start_time", 0) < H]
        last = d[-1]["match_id"]
        if d[-1].get("start_time", 0) < B0 - 86400:
            break
    P = pd.DataFrame(pro)
    P["rn"], P["dn"] = P.radiant_name.map(norm), P.dire_name.map(norm)
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    ud = ud[(ud.gs_ts >= B0) & (ud.gs_ts < H) & (ud.smt == "child_moneyline") & (ud.league != "PARI Universe")]
    mk, _ = pm.markets_by_condition(sorted(ud.cid))
    edges = np.arange(-300, 1801, 1)
    rng = np.random.default_rng(6)
    res = {}
    for ev, g_ev in ud.groupby("event_slug"):
        grid = bool(g_ev.grid_series_id.notna().any())
        lg = g_ev.league.iloc[0]
        rows = []
        for r in g_ev.itertuples():
            x = mk.get(r.cid) or {}
            mm = re.search(r"Game (\d)", x.get("question", ""))
            if mm:
                rows.append((int(mm.group(1)), r.cid, x))
        if not rows:
            continue
        outs = json.loads(rows[0][2]["outcomes"]) if isinstance(rows[0][2].get("outcomes"), str) else rows[0][2].get("outcomes")
        a5, b5 = norm(outs[0])[:5], norm(outs[1])[:5]
        gs = float(g_ev.gs_ts.min())
        cand = P[((P.rn.str.contains(a5, regex=False) & P.dn.str.contains(b5, regex=False)) |
                  (P.rn.str.contains(b5, regex=False) & P.dn.str.contains(a5, regex=False))) &
                 (P.start_time >= gs - 3600) & (P.start_time <= gs + 6 * 3600)].sort_values("start_time")
        for gno, cid, x in sorted(rows):
            if gno > len(cand):
                continue
            mid = int(cand.iloc[gno - 1].match_id)
            g, _ = h.get_json(f"https://api.opendota.com/api/matches/{mid}", {}, adapter="opendota.match", max_age=None)
            rn, dn = norm(g.get("radiant_name") or ""), norm(g.get("dire_name") or "")
            K = [(k["time"], "r" if p.get("player_slot", 0) < 128 else "d") for p in g.get("players") or [] for k in (p.get("kills_log") or [])]
            if not K:
                continue
            kt = np.array([k[0] for k in K], float)
            ks = np.array([k[1] for k in K])
            keep = kt <= 1200
            kt, ks = kt[keep], ks[keep]
            n0 = norm(outs[0])[:5]
            s0 = "r" if n0 and n0 in rn else ("d" if n0 and n0 in dn else None)
            if s0 is None:
                continue
            st = float(g["start_time"])
            tr, _, _ = pm.market_trades(cid, start=int(st) - 600, end=int(min(st + 1200 + 2400, H - 1)), taker_only=True)
            t = pd.DataFrame(tr)
            if t.empty:
                continue
            t = t.sort_values("timestamp")
            ts = t.timestamp.to_numpy(float)
            p0 = np.where(t.outcomeIndex.astype(int) == 0, t.price.astype(float), 1 - t.price.astype(float))
            j = np.searchsorted(ts, ts - 10)
            mv = p0 - p0[np.maximum(j, 0)]
            an, lastt = [], -1e9
            for tt, v in zip(ts, mv):
                if abs(v) >= 0.03 and tt - lastt > 10:
                    an.append((tt - st, s0 if v > 0 else ("d" if s0 == "r" else "r")))
                    lastt = tt
            if len(an) < 8:
                continue
            sb, so = scan(an, kt, ks, edges, 10)
            diff = sb - so
            k = int(np.argmax(diff))
            nul = []
            for _ in range(200):
                an2 = [(rel, sd if rng.random() < 0.5 else ("d" if sd == "r" else "r")) for rel, sd in an]
                b2, o2 = scan(an2, kt, ks, edges, 10)
                nul.append(float((b2 - o2).max()))
            res[f"{ev} game {gno}"] = {"league": lg, "grid": grid, "match_id": mid, "anchors": len(an), "pre_game_duration": g.get("pre_game_duration"),
                                       "best_D_s": int(edges[k]), "bought_hits": int(sb[k]), "other_hits": int(so[k]),
                                       "p_max": round(float(np.mean(np.array(nul) >= diff[k])), 3)}
    R = pd.DataFrame(res).T
    out = {"maps": res}
    if len(R):
        R["sig"] = R.p_max.astype(float) <= 0.05
        for gflag, g in R.groupby("grid"):
            gs_ = g[g.sig]
            out[f"grid_{gflag}"] = {"maps": int(len(g)), "significant_maps": int(len(gs_)),
                                    "D_significant": sorted(int(v) for v in gs_.best_D_s),
                                    "D_all_median": float(np.median(g.best_D_s.astype(float)))}
    print(json.dumps({k: v for k, v in out.items() if k != "maps"}, indent=1))
    print(R[["league", "grid", "anchors", "best_D_s", "bought_hits", "other_hits", "p_max"]].to_string())
    json.dump(out, open(RES / "dota_grid_market_clock.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
