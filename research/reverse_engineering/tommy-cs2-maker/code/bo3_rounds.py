"""Ground-truth round timeline (bo3.gg) for the wallet's traded maps, aligned to the public price jumps, to place
its taker orders inside rounds and score them against the actual round winner (independent of prices).

Per map: rounds k with duration d_k (ns) and winner; predicted round ends E_k = B + offset + sum_{j<=k}(d_j + gap),
B = game begin_at. (offset, gap) by grid search maximizing the number of rounds whose end has a >= 4c public jump in
the map market starting in [E_k - 8, E_k + 12] in the direction of the bo3 winner. Maps with < 50% of rounds aligned
are dropped. For each wallet taker order in an aligned map: round in progress (first E_k > t), seconds into that round,
and whether the bought team won it. Control: random times. Development data (16-22 Oct)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from polyrea.adapters.http import shared_client  # noqa: E402
from common import H, OUT, RES, SPLIT, TAPES, WALLET  # noqa: E402


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def main(days=("2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22")):
    h = shared_client()
    bl = []
    for day in days:
        d, _ = h.get_json("https://api.bo3.gg/api/v2/matches/finished", {"date": day, "filter[discipline_id][eq]": 1}, adapter="bo3gg.matches", max_age=None)
        for tier, v in d["data"]["tiers"].items():
            for m in v.get("matches", []):
                if m.get("parsed_status") == "done":
                    bl.append(m["slug"])
    m = json.load(open(OUT / "markets_dev.json"))
    o = pd.read_parquet(OUT / "orders.parquet")
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd.maker == WALLET, "tx"])
    maps = {}  # (event, map_no) -> cid
    for cid, x in m.items():
        if x.get("sportsMarketType") != "child_moneyline":
            continue
        mm = re.search(r"Map (\d)", x.get("question", ""))
        if not mm:
            continue
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        maps[cid] = (int(mm.group(1)), outs)
    rng = np.random.default_rng(9)
    rows, aligned_maps, tried = [], 0, 0
    for cid, (mapno, outs) in maps.items():
        a, c = norm(outs[0])[:6], norm(outs[1])[:6]
        cand = [s for s in bl if a in norm(s) and c in norm(s)]
        if not cand:
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [x for x in (g.get("games") or []) if x.get("number") == mapno]
        if not gm:
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = r.get("game_rounds") if isinstance(r, dict) else None
        if not rounds or not r.get("begin_at"):
            continue
        tried += 1
        rounds = sorted(rounds, key=lambda z: z["round_number"])
        dur = np.array([z["round_duration"] / 1e9 for z in rounds])
        win0 = np.array([norm(z["winner_clan_name"])[:6] == a for z in rounds])
        B = pd.Timestamp(r["begin_at"]).timestamp()
        p = TAPES / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p); d = d[(d.timestamp < H) & ~d.transactionHash.isin(bad)].sort_values("timestamp")
        ts = d.timestamp.to_numpy(np.int64); p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        if len(ts) < 20:
            continue
        j = np.searchsorted(ts, ts - 15, side="left"); prev = np.where(j > 0, p0[np.maximum(j - 1, 0)], np.nan)
        mv = p0 - prev; k = np.where(np.abs(mv) >= 0.04)[0]
        jt, jd = ts[k] - 15.0, np.sign(mv[k])  # approximate start of each jump window
        best = (-1, 0, 0)
        for gap in range(0, 41, 2):
            ends0 = np.cumsum(dur + gap)
            for off in range(-600, 601, 3):
                E = B + off + ends0
                lo = np.searchsorted(jt, E - 8); hi = np.searchsorted(jt, E + 12)
                sc = 0
                for kk in range(len(E)):
                    if hi[kk] > lo[kk]:
                        dd = jd[lo[kk]:hi[kk]]
                        sc += int(np.any(dd == (1 if win0[kk] else -1)))
                if sc > best[0]:
                    best = (sc, off, gap)
        sc, off, gap = best
        if sc < 0.5 * len(dur):
            continue
        aligned_maps += 1
        E = B + off + np.cumsum(dur + gap)
        S = E - dur  # approximate round start (live play start) = end - duration
        tk = o[(o.cid == cid) & (o.role == "taker")]
        for t, oi, ctrl in [(t, oi, False) for t, oi in zip(tk.sign_ts, tk.oi)] + [(t + rng.uniform(-600, 600), oi, True) for t, oi in zip(tk.sign_ts, tk.oi)]:
            kk = np.searchsorted(E, t, side="right")
            if kk >= len(E):
                continue
            won = bool(win0[kk]) if oi == 0 else not bool(win0[kk])
            rows.append({"cid": cid, "ctrl": ctrl, "round": int(kk + 1), "into_round": float(t - S[kk]), "to_end": float(E[kk] - t),
                         "won_round": won, "gs": int(o.loc[o.cid == cid, "gs_ts"].iloc[0]), "align_score": sc / len(dur)})
    x = pd.DataFrame(rows)
    res = {"maps_tried": tried, "maps_aligned": aligned_maps, "orders": int((~x.ctrl).sum()) if len(x) else 0}
    if len(x):
        for (ctrl, sp), s in x.groupby(["ctrl", x.gs >= SPLIT]):
            k = f"{'ctrl' if ctrl else 'real'}_{'VALIDATE' if sp else 'BUILD'}"
            res[k] = {"n": len(s), "won_round_in_progress": round(float(s.won_round.mean()), 3),
                      "into_round_q": s.into_round.quantile([.1, .25, .5, .75, .9]).round(1).to_dict(),
                      "to_end_q": s.to_end.quantile([.1, .25, .5, .75, .9]).round(1).to_dict()}
        real = x[~x.ctrl]
        res["real_won_by_phase"] = real.assign(ph=pd.cut(real.into_round, [-60, 0, 20, 40, 60, 90, 300])).groupby("ph", observed=True).won_round.agg(["size", "mean"]).round(3).astype(str).to_dict("index")
        res["real_won_by_phase"] = {str(k): v for k, v in res["real_won_by_phase"].items()}
    x.to_parquet(OUT / "bo3_taker_rounds.parquet", index=False)
    json.dump(res, open(RES / "results/bo3_rounds.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
