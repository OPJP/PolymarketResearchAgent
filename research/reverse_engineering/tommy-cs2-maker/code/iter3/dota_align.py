"""Iteration 3, X24 (retrospective variant of the information panel's Dota 2 natural experiment).

Dota 2 replays are parsed publicly (OpenDota /api/matches/<id>: kills_log in game seconds, start_time, pre_game
duration). For the wallet's Dota 2 map markets (development units: 10-22 PARI Universe; 10-31 12-18 block), compare its
taker orders with the kills of the team it buys: d = sign_s - start_time - kill_game_time for kills of the bought team
(and, as control, of the other team). A real-time game feed shows a sharp peak of d at a constant offset per map
(start-to-horn offset plus a short reaction); the same for the market's public repricing (tape moves >= 3c in 10 s
toward a team, block time) gives the market's offset, so the wallet's lead over the market is the difference.
Map markets only (question 'Game N Winner'); map N = the N-th OpenDota match of the series by start time.
Output: results/dota_align.json
"""
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from polyrea.adapters.http import shared_client  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from server_clock import OUT, RES, WALLET  # noqa: E402

SERIES = {  # Polymarket event -> OpenDota match ids (from proMatches, development units only), in map order
    "dota2-ty-gl-2026-10-22": [9056215433, 9056271057],
    "dota2-liquid-1win-2026-10-22": [9056618744, 9056794318],
    "dota2-ty-gl-2026-10-31": [9069952836, 9070062078],
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def main():
    h = shared_client()
    o = pd.read_parquet(OUT / "orders.parquet")
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    # wallet taker orders on Dota map markets: (event, cid, token, sign_s)
    tk = o[(o.role == "taker") & o.event.str.startswith("dota2")][["event", "cid", "token_id", "sign_ms"]].copy()
    dd = d[(d.idx == -1) & (d.maker == WALLET) & d.condition_id.isin(dm[dm.event.str.startswith("dota2")].cid)].drop_duplicates("tx")
    dd = dd.assign(event=dd.condition_id.map(dict(zip(dm.cid, dm.event))), cid=dd.condition_id)[["event", "cid", "token_id", "sign_ms"]]
    tk = pd.concat([tk, dd])
    cids = sorted(tk.cid.unique())
    mk, _ = PolymarketData().markets_by_condition(cids)
    res = {}
    allw, allc, allm, allmc = [], [], [], []
    for ev, mids in SERIES.items():
        maps = []
        for mid in mids:
            g, _ = h.get_json(f"https://api.opendota.com/api/matches/{mid}", {}, adapter="opendota.match", max_age=None)
            rn, dn = norm(g.get("radiant_name") or (g.get("radiant_team") or {}).get("name")), norm(g.get("dire_name") or (g.get("dire_team") or {}).get("name"))
            kills = []
            for p in g.get("players") or []:
                side = "r" if p.get("player_slot", 0) < 128 else "d"
                for k in p.get("kills_log") or []:
                    kills.append((k["time"], side))
            maps.append({"start": g["start_time"], "rn": rn, "dn": dn, "kills": kills, "dur": g.get("duration")})
        for cid in tk[tk.event == ev].cid.unique():
            x = mk.get(cid) or {}
            q = x.get("question", "")
            mm = re.search(r"Game (\d)", q)
            if not mm or int(mm.group(1)) > len(maps):
                continue
            mp = maps[int(mm.group(1)) - 1]
            outs = json.loads(x["outcomes"]) if isinstance(x.get("outcomes"), str) else x.get("outcomes")
            toks = json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds")
            side_of = {}
            for i, nm in enumerate(outs):
                n6 = norm(nm)[:5]
                side_of[str(toks[i])] = "r" if n6 and n6 in mp["rn"] else ("d" if n6 and n6 in mp["dn"] else None)
            kills = np.array([t for t, s in mp["kills"]], float)
            ks = np.array([s for t, s in mp["kills"]])
            for r in tk[tk.cid == cid].itertuples():
                s_team = side_of.get(str(r.token_id))
                if s_team is None:
                    continue
                rel = r.sign_ms / 1000 - mp["start"]
                allw += list(rel - kills[ks == s_team])
                allc += list(rel - kills[ks != s_team])
            # market: tape moves >= 3c within 10 s (block time), excluding the wallet's own transactions
            p = OUT / "tapes" / f"{cid}_tkw.parquet"
            if p.exists():
                tp = pd.read_parquet(p).sort_values("timestamp")
                tp = tp[tp.proxyWallet.str.lower() != WALLET]
                ts = tp.timestamp.to_numpy(float)
                p0 = np.where(tp.outcomeIndex.astype(int) == 0, tp.price.astype(float), 1 - tp.price.astype(float))
                j = np.searchsorted(ts, ts - 10)
                mv = p0 - p0[np.maximum(j, 0)]
                s0 = side_of.get(str(toks[0]))
                for t, v in zip(ts[np.abs(mv) >= 0.03], mv[np.abs(mv) >= 0.03]):
                    team = s0 if v > 0 else ("d" if s0 == "r" else "r")
                    rel = t - mp["start"]
                    allm += list(rel - kills[ks == team])
                    allmc += list(rel - kills[ks != team])
    edges = np.arange(-200, 1202, 4)

    def peak(a, b):
        ha = np.histogram(a, edges)[0].astype(float)
        hb = np.histogram(b, edges)[0].astype(float)
        diff = ha - hb
        i = np.argsort(diff)[::-1][:5]
        return [[int(edges[k]), int(ha[k]), int(hb[k])] for k in sorted(i)], int(len(a))
    res["wallet_vs_kills"] = {"peaks_[offset_s,bought_team_kills,other_team_kills]": peak(allw, allc)[0], "pairs": len(allw)}
    res["market_moves_vs_kills"] = {"peaks": peak(allm, allmc)[0], "pairs": len(allm)}
    res["wallet_orders"] = int(len(tk))
    json.dump(res, open(RES / "dota_align.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
