"""Is RN1 off the book before the first public price jump? (live lab, development units only)

Events: sports-ws score changes of soccer games (live block), each aligned on the FIRST >= 3-tick move of the book
midpoint (within 3 s) in the game's recorded markets inside [ws - 30 s, ws + 10 s] (from ws_vs_book_<a>.parquet's
inputs, recomputed here). Around t_jump: RN1's fills (block time) in the game's markets, in 2-s bins, and its
orders that were resting through the jump (signed before t_jump, filled within 10 s after it).
Writes results/live_jump_align_<a>.json.
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
from live_e3_screen import SOCCER, TENNIS  # noqa: E402


def main(a):
    b = a + 6 * 3600
    od = pd.read_parquet(C / "live" / f"orders_{a}.parquet")
    un = pd.read_parquet(C / "live" / f"units_{a}.parquet")
    first = {}
    for _, u in un.iterrows():
        try:
            tk = json.loads(u["clobTokenIds"])
        except (TypeError, ValueError):
            continue
        if len(tk) == 2:
            first[tk[0]] = u["conditionId"]
    rn = od[(od["maker"].str.lower() == W)].copy()
    rn["px"] = np.where(rn["side"] == 0, rn["maker_amount"] / rn["taker_amount"], rn["taker_amount"] / rn["maker_amount"])
    gmap = ls.game_ids(list(set(rn["cond"])))
    rn["gameId"] = rn["cond"].map(lambda c: (gmap.get(c) or {}).get("gameId"))
    toks = {t: c for t, c in first.items() if c in set(rn["cond"])}
    bk = lq.load_books(a, b, set(toks))
    bk["t"] = bk["s"].fillna(bk["t"]).astype(float) / 1000.0
    bk["mid"] = (bk["bb"] + bk["ba"]) / 2
    bk["gameId"] = bk["tok"].map(lambda t: (gmap.get(toks.get(t)) or {}).get("gameId"))
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
        lg = str(m.get("leagueAbbreviation") or "").lower()
        if g in last and sc is not None and last[g] is not None and sc != last[g]:
            ev.append((g, r["t"] / 1000.0 + off, lg))
        if sc is not None:
            last[g] = sc
    ev = pd.DataFrame(ev, columns=["gameId", "t", "league"])
    out = {"block": a}
    for fam, leagues in (("soccer", SOCCER), ("tennis", TENNIS)):
        e = ev[ev["league"].isin(leagues)]
        edges = np.arange(-60, 122, 2)
        h_all = np.zeros(len(edges) - 1)
        n_ev, resting, rest_adverse, jl = 0, 0, [], []
        for g, sub in e.groupby("gameId"):
            gb = bk[bk["gameId"] == g]
            if gb.empty:
                continue
            jt = []
            for tok, tb in gb.groupby("tok"):
                tb = tb.sort_values("t")
                t, mid = tb["t"].to_numpy(), tb["mid"].to_numpy()
                j = np.searchsorted(t, t - 3.0, side="left")
                big = np.abs(mid - mid[j]) >= 0.03 - 1e-9
                jt.append(t[big])
            jt = np.sort(np.concatenate(jt)) if jt else np.array([])
            fills = rn[(rn["gameId"] == g) & (rn["role"] == "maker")]
            for t0 in sub["t"]:
                w = jt[(jt >= t0 - 30) & (jt <= t0 + 10)]
                if not len(w):
                    continue
                tj = w.min()
                n_ev += 1
                jl.append(tj - t0)
                h_all += np.histogram(fills["bts"].to_numpy() - tj, edges)[0]
                hit = fills[(fills["sign_ms"] / 1000.0 < tj) & (fills["bts"] >= tj) & (fills["bts"] <= tj + 10)]
                resting += int(hit["salt"].nunique())
        out[fam] = {"events_aligned": n_ev, "jump_minus_ws_median_s": float(np.median(jl)) if jl else None,
                    "rn1_fill_counts_2s_bins_from_-60": h_all.astype(int).tolist(),
                    "rn1_orders_resting_through_jump_filled_within_10s": resting}
    print(json.dumps(out, indent=1))
    json.dump(out, open(R / "results" / f"live_jump_align_{a}.json", "w"), indent=1)


if __name__ == "__main__":
    main(int(sys.argv[1]))
