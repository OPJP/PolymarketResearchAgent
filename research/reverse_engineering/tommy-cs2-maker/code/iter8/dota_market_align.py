"""Iteration 8 (X24 retrospective): the same per-map kill alignment as dota_feed_align.py, with PUBLIC anchors: the
first print of each >= 3c move in 10 s on the map market (block-time stamps; wallet and P4e transactions excluded;
team = the side whose price rose), so the feed's offset D_feed and the market's D_market sit on the same game clock.
D_market - D_feed is then the market's lag behind the feed on in-game kills (prints carry up to ~2-4 s of block delay).
Output: results/dota_market_align.json
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
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    ud = ud[ud.event_slug.isin(SERIES) & (ud.smt == "child_moneyline")]
    mk, _ = pm.markets_by_condition(sorted(ud.cid))
    cols = ["tx", "maker"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    d = pd.concat([pd.read_parquet(p, columns=cols) for p in glob.glob(str(OUT / "dota_pub" / "*.parquet"))])
    bad = set(a.tx) | set(d.loc[d.maker.str.lower() == P4E, "tx"])
    edges = np.arange(-300, 1801, 1)
    rng = np.random.default_rng(3)
    res = {}
    for ev, mids in SERIES.items():
        for r in ud[ud.event_slug == ev].itertuples():
            x = mk.get(r.cid) or {}
            mm = re.search(r"Game (\d)", x.get("question", ""))
            if not mm:
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
            n0 = norm(outs[0])[:5]
            s0 = "r" if n0 and n0 in rn else ("d" if n0 and n0 in dn else None)
            if s0 is None:
                continue
            st = float(g["start_time"])
            tr, _, _ = pm.market_trades(r.cid, start=int(st) - 600, end=int(st + 1200 + 2400), taker_only=True)
            t = pd.DataFrame(tr)
            t = t[~t.transactionHash.isin(bad)].sort_values("timestamp")
            ts = t.timestamp.to_numpy(float)
            p0 = np.where(t.outcomeIndex.astype(int) == 0, t.price.astype(float), 1 - t.price.astype(float))
            j = np.searchsorted(ts, ts - 10)
            mv = p0 - p0[np.maximum(j, 0)]
            an, last = [], -1e9
            for tt, v in zip(ts, mv):
                if abs(v) >= 0.03 and tt - last > 10:
                    an.append((tt - st, s0 if v > 0 else ("d" if s0 == "r" else "r")))
                    last = tt
            if not an:
                continue
            sb, so = scan(an, kt, ks, edges, 10)
            diff = sb - so
            k = int(np.argmax(diff))
            nul = []
            for _ in range(200):
                an2 = [(rel, sd if rng.random() < 0.5 else ("d" if sd == "r" else "r")) for rel, sd in an]
                b2, o2 = scan(an2, kt, ks, edges, 10)
                nul.append(float((b2 - o2).max()))
            res[f"{ev} map {mm.group(1)}"] = {"anchors": len(an), "best_D_s": int(edges[k]), "bought_hits": int(sb[k]), "other_hits": int(so[k]),
                                              "top3_D": [int(edges[i]) for i in np.argsort(diff)[::-1][:3]],
                                              "null_max_p50_p95": [float(np.percentile(nul, 50)), float(np.percentile(nul, 95))],
                                              "p_max": round(float(np.mean(np.array(nul) >= diff[k])), 3)}
    feed = json.load(open(RES / "dota_feed_align.json"))
    for k, v in res.items():
        if k in feed and feed[k].get("anchors"):
            v["D_feed_s"] = feed[k]["best_D_s"]
            v["D_market_minus_D_feed_s"] = v["best_D_s"] - feed[k]["best_D_s"]
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "dota_market_align.json", "w"), indent=1)


if __name__ == "__main__":
    main()
