"""Iteration 9, X129 (assumptions panel iter8 P3, step 1): machine reader or human scouts? Spread of the feed's lag behind
in-game events on the 10-22 Dota maps (anchors = taker BUYs of P4e and the wallet; kills = OpenDota kills_log, integer
game seconds, first 20 game minutes). Per map, scan D in 0.1-s steps; for window widths w in {0.8, 1.2, 1.6, 2, 3, 4} s
count anchors with a bought-team kill in [rel - D - w, rel - D] minus the same for the other team (control); take the
max over D per map and pool. A constant-lag machine saturates by w ~ 1.2 s (integer kill seconds give a 1-s uniform
spread); a scout with SD >= 0.4 s keeps adding hits to 3 s. At the pooled best D per map (w = 3 s), the lag of each hit
behind its most recent bought-team kill, split into isolated kills and teamfight kills (>= 3 kills of any side within
10 s), and for teamfights whether the anchor follows the first or a later kill of the fight.
Output: results/lag_spread.json
"""
from __future__ import annotations

import glob
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
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
SERIES = {"dota2-ty-gl-2026-10-22": [9056215433, 9056271057], "dota2-liquid-1win-2026-10-22": [9056618744, 9056794318],
          "dota2-ts8-legion1-2026-10-22": [9056353535, 9056429802]}
WS = [0.8, 1.2, 1.6, 2.0, 3.0, 4.0]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def main():
    h = shared_client()
    prior = json.load(open(RES / "dota_feed_align.json"))
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    ud = ud[ud.event_slug.isin(SERIES) & (ud.smt == "child_moneyline")]
    mk, _ = PolymarketData().markets_by_condition(sorted(ud.cid))
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    T = pd.concat([pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)] +
                  [pd.read_parquet(p, columns=cols) for p in glob.glob(str(OUT / "dota_pub" / "*.parquet"))]).drop_duplicates(["tx", "idx"])
    T["maker"] = T.maker.str.lower()
    T["token_id"] = T.token_id.astype(str)
    T = T[(T.idx == -1) & (T.side == 0) & T.maker.isin([W, P4E])]
    # cluster anchors: one anchor per 500-ms cluster per token (P4e and the wallet on one message count once)
    pooled = {w: [0, 0] for w in WS}
    hits = []
    per_map = {}
    for ev, mids in SERIES.items():
        for r in ud[ud.event_slug == ev].itertuples():
            x = mk.get(r.cid) or {}
            mm = re.search(r"Game (\d)", x.get("question", ""))
            if not mm or int(mm.group(1)) > len(mids):
                continue
            key = f"{ev} map {mm.group(1)}"
            if key not in prior or prior[key]["anchors"] < 8:
                continue
            mid = mids[int(mm.group(1)) - 1]
            g, _ = h.get_json(f"https://api.opendota.com/api/matches/{mid}", {}, adapter="opendota.match", max_age=None)
            rn = norm(g.get("radiant_name") or (g.get("radiant_team") or {}).get("name"))
            dn = norm(g.get("dire_name") or (g.get("dire_team") or {}).get("name"))
            K = np.array([(k["time"], 0 if p.get("player_slot", 0) < 128 else 1) for p in g.get("players") or [] for k in (p.get("kills_log") or [])], float)
            K = K[(K[:, 0] <= 1200)]
            K = K[np.argsort(K[:, 0])]
            kt, ks = K[:, 0], K[:, 1].astype(int)
            fight = np.array([((np.abs(kt - t0) <= 10).sum() >= 3) for t0 in kt])
            first_in_fight = np.array([fight[i] and not ((kt < kt[i]) & (kt >= kt[i] - 10)).any() for i in range(len(kt))])
            outs = json.loads(x["outcomes"]) if isinstance(x.get("outcomes"), str) else x.get("outcomes")
            toks = json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds")
            side_of = {}
            for i, nm in enumerate(outs):
                n5 = norm(nm)[:5]
                side_of[str(toks[i])] = 0 if n5 and n5 in rn else (1 if n5 and n5 in dn else None)
            an = T[T.token_id.isin(side_of)].sort_values("sign_ms")
            an = an[(an.sign_ms.diff().fillna(1e9) > 500) | (an.token_id != an.token_id.shift())]
            st = float(g["start_time"])
            rel = an.sign_ms.to_numpy(float) / 1000 - st
            sd = np.array([side_of[t] for t in an.token_id])
            ok = np.array([s is not None for s in sd])
            rel, sd = rel[ok], sd[ok].astype(int)
            Ds = np.arange(prior[key]["best_D_s"] - 15, prior[key]["best_D_s"] + 15.01, 0.1)
            res_m = {"anchors": int(len(rel))}
            bestD3 = None
            for w in WS:
                best, bb, bo, bD = -1e9, 0, 0, None
                for D in Ds:
                    lag = rel[:, None] - D - kt[None, :]
                    inwin = (lag >= 0) & (lag <= w)
                    b_ = int((inwin & (ks[None, :] == sd[:, None])).any(axis=1).sum())
                    o_ = int((inwin & (ks[None, :] != sd[:, None])).any(axis=1).sum())
                    if b_ - o_ > best:
                        best, bb, bo, bD = b_ - o_, b_, o_, D
                res_m[f"w{w}"] = {"bought": bb, "other": bo, "D": round(float(bD), 1)}
                pooled[w][0] += bb
                pooled[w][1] += bo
                if w == 3.0:
                    bestD3 = bD
            # lags at the w = 3 best D
            for i in range(len(rel)):
                lag = rel[i] - bestD3 - kt
                sel = (lag >= 0) & (lag <= 3) & (ks == sd[i])
                if sel.any():
                    j = np.flatnonzero(sel)[-1]  # most recent bought-team kill
                    hits.append({"map": key, "lag": float(lag[j]), "fight": bool(fight[j]), "first_in_fight": bool(first_in_fight[j])})
            per_map[key] = res_m
    Hh = pd.DataFrame(hits)
    out = {"per_map": per_map, "pooled": {str(w): {"bought": v[0], "other": v[1], "net": v[0] - v[1]} for w, v in pooled.items()}}
    n3 = pooled[3.0][0] - pooled[3.0][1]
    out["saturation_net_w_over_w3"] = {str(w): round((v[0] - v[1]) / max(n3, 1), 3) for w, v in pooled.items()}
    if len(Hh):
        # centre each map's lags on its median (D is fitted per map, so only the spread is identified)
        Hh["lag_c"] = Hh.lag - Hh.groupby("map").lag.transform("median")
        out["hits"] = int(len(Hh))
        out["lag_centered_sd"] = round(float(Hh.lag_c.std()), 3)
        out["lag_centered_iqr"] = round(float(Hh.lag_c.quantile(0.75) - Hh.lag_c.quantile(0.25)), 3)
        out["lag_skew"] = round(float(Hh.lag_c.skew()), 3)
        out["uniform_1s_reference_sd_iqr"] = [round(1 / np.sqrt(12), 3), 0.5]
        for nm, sel in (("isolated", ~Hh.fight), ("teamfight", Hh.fight), ("teamfight_first_kill", Hh.fight & Hh.first_in_fight),
                        ("teamfight_later_kill", Hh.fight & ~Hh.first_in_fight)):
            y = Hh[sel]
            out[nm] = {"n": int(len(y)), "median_lag_c": round(float(y.lag_c.median()), 3) if len(y) else None,
                       "sd": round(float(y.lag_c.std()), 3) if len(y) > 2 else None}
    print(json.dumps(out, indent=1))
    json.dump(out, open(RES / "lag_spread.json", "w"), indent=1)


if __name__ == "__main__":
    main()
