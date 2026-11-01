"""X2: latency of the Polymarket sports websocket against the public book (live lab, development units only).

For every score change of a game (sports ws, receive time + recorder clock offset), the first large move of the
book midpoint (>= 3 ticks within 3 s) in any recorded market of that game within [-60, +60] s.
Negative = the book moved before the websocket reported the score change.
Also: RN1's inside presence around score changes, i.e. whether RN1's resting levels are pulled before the move
(proxy: total size at the inside on both sides, from the book, -10..+10 s).
Writes results/live_ws_vs_book_<a>.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_quotes as lq  # noqa: E402
import live_sports as ls  # noqa: E402
from common import C, R, W  # noqa: E402


def main(a):
    b = a + 6 * 3600
    od = pd.read_parquet(C / "live" / f"orders_{a}.parquet")
    un = pd.read_parquet(C / "live" / f"units_{a}.parquet")
    toks = {}
    for _, u in un.iterrows():
        try:
            tk = json.loads(u["clobTokenIds"])
        except (TypeError, ValueError):
            continue
        if len(tk) == 2:
            toks[u["conditionId"]] = tk[0]
    rn_c = set(od.loc[od["maker"].str.lower() == W, "cond"])
    gmap = ls.game_ids(list(rn_c))
    first = {toks[c]: c for c in rn_c if c in toks}
    bk = lq.load_books(a, b, set(first))
    bk["t"] = bk["s"].fillna(bk["t"]).astype(float) / 1000.0
    bk["mid"] = (bk["bb"] + bk["ba"]) / 2
    bk["cond"] = bk["tok"].map(first)
    bk["gameId"] = bk["cond"].map(lambda c: (gmap.get(c) or {}).get("gameId"))
    # ws score changes
    offs = []
    for k, r in enumerate(ls.gen("clob_wallets", a, a + 3 * 3600)):
        if r.get("s"):
            offs.append(r["s"] - r["t"])
        if k > 20000:
            break
    off = (float(np.median(offs)) + 50.0) / 1000.0 if offs else 0.0
    last, ev = {}, []
    for r in ls.gen("sports", a, b):
        try:
            m = json.loads(r["m"])
        except (TypeError, ValueError):
            continue
        if not isinstance(m, dict) or "gameId" not in m:
            continue
        g, sc = m["gameId"], m.get("score")
        if g in last and sc is not None and last[g] is not None and sc != last[g]:
            ev.append((g, r["t"] / 1000.0 + off, m.get("leagueAbbreviation")))
        if sc is not None:
            last[g] = sc
    ev = pd.DataFrame(ev, columns=["gameId", "t", "league"])
    lat, rows = [], []
    for g, sub in ev.groupby("gameId"):
        gb = bk[bk["gameId"] == g]
        if gb.empty:
            continue
        jumps = []
        for tok, tb in gb.groupby("tok"):
            tb = tb.sort_values("t")
            t, mid = tb["t"].to_numpy(), tb["mid"].to_numpy()
            j = np.searchsorted(t, t - 3.0, side="left")
            big = np.abs(mid - mid[j]) >= 0.03 - 1e-9
            jumps.append(t[big])
        jt = np.sort(np.concatenate(jumps)) if jumps else np.array([])
        for t0, lg in zip(sub["t"], sub["league"]):
            w = jt[(jt >= t0 - 60) & (jt <= t0 + 60)]
            if len(w):
                d = w[np.argmin(np.abs(w - t0))]
                first_move = w.min()
                rows.append((g, lg, t0, d - t0, first_move - t0))
    df = pd.DataFrame(rows, columns=["gameId", "league", "t", "nearest_jump_minus_ws", "first_jump_minus_ws"])
    out = {"block": a, "clock_offset_s": off, "games_with_books": int(bk["gameId"].nunique()), "ws_events": int(len(ev)),
           "events_with_jump_within_60s": int(len(df))}
    if len(df):
        out["first_jump_minus_ws_q"] = {str(q): round(float(df["first_jump_minus_ws"].quantile(q)), 2) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
        out["nearest_jump_minus_ws_q"] = {str(q): round(float(df["nearest_jump_minus_ws"].quantile(q)), 2) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
        out["share_book_moved_first"] = float((df["nearest_jump_minus_ws"] < 0).mean())
        out["by_league"] = {lg: {"n": int(len(s)), "median_nearest": round(float(s["nearest_jump_minus_ws"].median()), 2)}
                            for lg, s in df.groupby("league") if len(s) >= 5}
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(R / "results" / f"live_ws_vs_book_{a}.json", "w"), indent=1, default=str)
    df.to_parquet(C / "live" / f"ws_vs_book_{a}.parquet", index=False)


if __name__ == "__main__":
    main(int(sys.argv[1]))
