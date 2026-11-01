"""Iteration 8 (X24 / X88 retrospective, with the feed's Dota messages): align the push feed's Dota 2 messages (taker
BUY signing times of P4e and the wallet on the 10-22 PARI Universe map markets, development) to the parsed game
(OpenDota /api/matches/<id> kills_log: game seconds, by side). Per map, wall(tau) = start_time + D + tau; for D in
[-300, 1500] s (1-s steps) score_b(D) = anchors with a kill by the BOUGHT team in [t - 6, t] s, score_o(D) the same for
the other team (control). A real-time feed shows a sharp per-map peak of score_b - score_o at D near the pre-game
duration (+ a reaction of a few seconds); a broadcast-side feed at D + the spectator / stream delay. Pauses break the
mapping, so only the first 20 game minutes are used. Output: results/dota_feed_align.json
"""
from __future__ import annotations

import glob
import json
import os
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
WIN = float(os.environ.get("TOMMY_DOTA_WIN", 6))
SUFW = os.environ.get("TOMMY_DOTA_SUF", "")
SERIES = {"dota2-ty-gl-2026-10-22": [9056215433, 9056271057], "dota2-liquid-1win-2026-10-22": [9056618744, 9056794318],
          "dota2-ty-gl-2026-10-31": [9069952836, 9070062078],  # 10-31 12-18 development unit (iteration 8 addition)
          "dota2-ts8-legion1-2026-10-22": [9056353535, 9056429802]}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def main():
    h = shared_client()
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    ud = ud[ud.event_slug.isin(SERIES) & (ud.smt == "child_moneyline")]
    mk, _ = PolymarketData().markets_by_condition(sorted(ud.cid))
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    d = pd.concat([pd.read_parquet(p, columns=cols) for p in glob.glob(str(OUT / "dota_pub" / "*.parquet")) + glob.glob(str(OUT / "dota_pub_1031" / "*.parquet"))])
    T = pd.concat([a, d]).drop_duplicates(["tx", "idx"])
    T["maker"] = T.maker.str.lower()
    T["token_id"] = T.token_id.astype(str)
    WHO = os.environ.get("TOMMY_DOTA_WHO", "both")  # both | wallet | p4e
    T = T[(T.idx == -1) & (T.side == 0) & T.maker.isin({"both": [W, P4E], "wallet": [W], "p4e": [P4E]}[WHO])]
    edges = np.arange(-300, 1501, 1)
    res = {}
    for ev, mids in SERIES.items():
        for r in ud[ud.event_slug == ev].itertuples():
            x = mk.get(r.cid) or {}
            mm = re.search(r"Game (\d)", x.get("question", ""))
            if not mm or int(mm.group(1)) > len(mids):
                continue
            mid = mids[int(mm.group(1)) - 1]
            g, _ = h.get_json(f"https://api.opendota.com/api/matches/{mid}", {}, adapter="opendota.match", max_age=None)
            rn = norm(g.get("radiant_name") or (g.get("radiant_team") or {}).get("name"))
            dn = norm(g.get("dire_name") or (g.get("dire_team") or {}).get("name"))
            kills = [(k["time"], "r" if p.get("player_slot", 0) < 128 else "d") for p in g.get("players") or [] for k in (p.get("kills_log") or [])]
            kt = np.array([k[0] for k in kills], float)
            ks = np.array([k[1] for k in kills])
            keep = kt <= 1200
            kt, ks = kt[keep], ks[keep]
            outs = json.loads(x["outcomes"]) if isinstance(x.get("outcomes"), str) else x.get("outcomes")
            toks = json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds")
            side_of = {}
            for i, nm in enumerate(outs):
                n5 = norm(nm)[:5]
                side_of[str(toks[i])] = "r" if n5 and n5 in rn else ("d" if n5 and n5 in dn else None)
            an = T[T.token_id.isin(side_of)]
            st = float(g["start_time"])

            def curves(shift_s):
                sb_, so_ = np.zeros(len(edges)), np.zeros(len(edges))
                for q in an.itertuples():
                    sd_ = side_of.get(q.token_id)
                    if sd_ is None:
                        continue
                    rel_ = q.sign_ms / 1000 - st + shift_s
                    for arr, sel in ((sb_, ks == sd_), (so_, ks != sd_)):
                        hit = np.zeros(len(edges), bool)
                        for L in rel_ - kt[sel]:
                            lo, hi = np.searchsorted(edges, L - WIN), np.searchsorted(edges, L, side="right")
                            hit[lo:hi] = True
                        arr += hit
                return sb_, so_
            rng = np.random.default_rng(int(mid) % 1000)
            # null: each anchor's side label randomised (bought vs other team), 200 draws of the max per-map diff
            nulmax = []
            if len(an):
                for _ in range(200):
                    sb_, so_ = np.zeros(len(edges)), np.zeros(len(edges))
                    for q in an.itertuples():
                        sd_ = side_of.get(q.token_id)
                        if sd_ is None:
                            continue
                        if rng.random() < 0.5:
                            sd_ = "d" if sd_ == "r" else "r"
                        rel_ = q.sign_ms / 1000 - st
                        for arr, sel in ((sb_, ks == sd_), (so_, ks != sd_)):
                            hit = np.zeros(len(edges), bool)
                            for L in rel_ - kt[sel]:
                                lo, hi = np.searchsorted(edges, L - WIN), np.searchsorted(edges, L, side="right")
                                hit[lo:hi] = True
                            arr += hit
                    nulmax.append(float((sb_ - so_).max()))
            sb, so = np.zeros(len(edges)), np.zeros(len(edges))
            n_an = 0
            for q in an.itertuples():
                sd = side_of.get(q.token_id)
                if sd is None:
                    continue
                rel = q.sign_ms / 1000 - st
                if rel > 1200 + 1500:
                    continue
                n_an += 1
                for arr, sel in ((sb, ks == sd), (so, ks != sd)):
                    lag = rel - kt[sel]  # = D + (t - wall(tau)) ; take after the kill by 0-6 s -> D in [lag - 6, lag]
                    hit = np.zeros(len(edges), bool)
                    for L in lag:
                        lo, hi = np.searchsorted(edges, L - WIN), np.searchsorted(edges, L, side="right")
                        hit[lo:hi] = True
                    arr += hit
            diff = sb - so
            k = int(np.argmax(diff))
            top = np.argsort(diff)[::-1][:3]
            res[f"{ev} map {mm.group(1)}"] = {"match_id": mid, "anchors": n_an, "pre_game_duration": g.get("pre_game_duration"),
                                              "best_D_s": int(edges[k]), "bought_hits": int(sb[k]), "other_hits": int(so[k]),
                                              "top3_D": [int(edges[i]) for i in top], "top3_diff": [int(diff[i]) for i in top],
                                              "median_diff": float(np.median(diff)),
                                              "null_max_diff_p50_p95": [float(np.percentile(nulmax, 50)), float(np.percentile(nulmax, 95))] if nulmax else None,
                                              "p_max": round(float(np.mean(np.array(nulmax) >= diff[k])), 3) if nulmax else None}
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / f"dota_feed_align{SUFW}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
