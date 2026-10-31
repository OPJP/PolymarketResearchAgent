"""Timing-only alignment of pack/wallet taker clusters to bo3.gg round ends (no team information used).

DP per map: rounds k matched to clusters m monotonically; a link (k-1 -> k) is "tight" when the cluster gap equals
d_k + c within +-TOL s (c = freeze + restart delay, grid per map). Score = number of tight links. Control: the same DP
with the bo3 durations permuted within the map (3 draws). Then, on maps where the alignment beats the control, each
cluster is placed between consecutive aligned round ends, and its team is compared with the winner of the round just
ended / the round in progress. Development data 16-22 Oct only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from polyrea.adapters.http import shared_client  # noqa: E402
from common import OUT, RES, SPLIT  # noqa: E402
from pack_vs_rounds import bo3_maps, norm  # noqa: E402

TOL = 3.0


def dp(t, dur, c):
    R, M = len(dur), len(t)
    V = np.zeros((R, M))
    P = np.full((R, M, 2), -1, dtype=np.int64)
    for k in range(R):
        for m in range(M):
            best, arg = 0.0, (-1, -1)
            for kp in range(max(0, k - 3), k):
                need = dur[kp + 1:k + 1].sum() + c * (k - kp)
                for mp in range(m):
                    gap = t[m] - t[mp]
                    if gap < need - TOL:
                        continue
                    val = V[kp, mp] + (1.0 if (kp == k - 1 and abs(gap - need) <= TOL) else 0.0)
                    if val > best:
                        best, arg = val, (kp, mp)
            V[k, m] = best
            P[k, m] = arg
    k, m = np.unravel_index(np.argmax(V), V.shape)
    score = V[k, m]
    pairs = []
    while k >= 0 and m >= 0:
        pairs.append((int(k), int(m)))
        k, m = P[k, m]
    return score, pairs[::-1]


def tight_of(pairs, t, dur, c):
    out = set()
    for (k, m), (k2, m2) in zip(pairs[:-1], pairs[1:]):
        if k2 == k + 1 and abs((t[m2] - t[m]) - (dur[k2] + c)) <= TOL:
            out.add((k, m))
            out.add((k2, m2))
    return out


def main():
    h = shared_client()
    slugs = bo3_maps(h)
    mk = json.load(open(OUT / "markets_dev.json"))
    c = pd.read_parquet(OUT / "pack_clusters.parquet")
    po = pd.read_parquet(OUT / "pack_orders.parquet", columns=["cluster", "who", "map_no", "team", "sign_ms"])
    rng = np.random.default_rng(5)
    summ, place = [], []
    for cid, x in mk.items():
        if x.get("sportsMarketType") != "child_moneyline" or not x.get("question", "").startswith("Counter-Strike"):
            continue
        mm = re.search(r"Map (\d)", x["question"])
        if not mm:
            continue
        mapno = int(mm.group(1))
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        ev = (x.get("events") or [{}])[0].get("slug")
        a, b = norm(outs[0])[:6], norm(outs[1])[:6]
        cand = [s for s in slugs if a in norm(s) and b in norm(s)]
        if not cand:
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [y for y in (g.get("games") or []) if y.get("number") == mapno]
        if not gm:
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = r.get("game_rounds") if isinstance(r, dict) else None
        if not rounds:
            continue
        rounds = sorted(rounds, key=lambda z: z["round_number"])
        win = np.array([0 if norm(z["winner_clan_name"])[:6] == a else 1 for z in rounds])
        dur = np.array([z["round_duration"] / 1e9 for z in rounds])
        cl_ids = po[po.map_no == mapno].cluster.unique()
        cc = c[(c.event == ev) & c.cluster.isin(cl_ids)].sort_values("t0").reset_index(drop=True)
        if len(cc) < 8:
            continue
        t = cc.t0.to_numpy() / 1000.0
        best = (-1, None, None)
        for cpar in range(0, 41, 4):
            s, pr = dp(t, dur, cpar)
            if s > best[0]:
                best = (s, cpar, pr)
        s, cpar, pairs = best
        ctrl = []
        for _ in range(3):
            dperm = rng.permutation(dur)
            ctrl.append(max(dp(t, dperm, cc_)[0] for cc_ in range(0, 41, 8)))
        tight = tight_of(pairs, t, dur, cpar)
        summ.append({"cid": cid, "event": ev, "map": mapno, "gs": x.get("gameStartTime"), "rounds": len(dur), "clusters": len(t),
                     "score": s, "ctrl_mean": float(np.mean(ctrl)), "ctrl_max": float(np.max(ctrl)), "c": cpar,
                     "tight_team_eq_winner": float(np.mean([cc.team[m] == win[k] for k, m in tight])) if tight else np.nan,
                     "n_tight": len(tight)})
        E = np.full(len(dur), np.nan)
        for k, m in tight:
            E[k] = t[m]
        anchors = {int(cc.cluster[m]) for k, m in tight}
        ok = ~np.isnan(E)
        if ok.sum() < 3:
            continue
        ke = np.where(ok)[0]
        ends = E[ok]
        for i in range(len(t)):
            j = np.searchsorted(ends, t[i] + 1e-9) - 1
            if j < 0 or j + 1 >= len(ends):
                continue
            kprev, knext = ke[j], ke[j + 1]
            if knext != kprev + 1:
                continue
            place.append({"cid": cid, "gs": x.get("gameStartTime"), "cluster": int(cc.cluster[i]), "has_W": bool(cc.has_W[i]),
                          "has_P4e": bool(cc.has_P4e[i]), "since_end": t[i] - ends[j], "to_next_end": ends[j + 1] - t[i],
                          "round_len": dur[knext], "team": int(cc.team[i]), "won_prev": int(cc.team[i] == win[kprev]),
                          "won_next": int(cc.team[i] == win[knext]), "anchor": int(cc.cluster[i]) in anchors})
    s = pd.DataFrame(summ)
    p = pd.DataFrame(place)
    s.to_parquet(OUT / "round_align_maps.parquet", index=False)
    p.to_parquet(OUT / "round_align_place.parquet", index=False)
    good = s[s.score >= s.ctrl_max + 3]
    res = {"maps": len(s), "score_median": float(s.score.median()), "ctrl_mean_median": float(s.ctrl_mean.median()),
           "score_minus_ctrlmean_median": float((s.score - s.ctrl_mean).median()),
           "maps_score_ge_ctrlmax_plus3": len(good), "rounds_in_good": int(good.rounds.sum()), "tight_in_good": int(good.n_tight.sum()),
           "tight_team_eq_winner_good": round(float((good.tight_team_eq_winner * good.n_tight).sum() / max(1, good.n_tight.sum())), 3),
           "tight_team_eq_winner_all": round(float((s.tight_team_eq_winner.fillna(0) * s.n_tight).sum() / max(1, s.n_tight.sum())), 3),
           "c_mode_good": good.c.mode().tolist()}
    if len(p):
        pg = p[p.cid.isin(good.cid) & ~p.anchor]
        res["placed_nonanchor_clusters_good"] = len(pg)
        for lab, q in (("W", pg[pg.has_W]), ("P4e_noW", pg[pg.has_P4e & ~pg.has_W]), ("other", pg[~pg.has_W & ~pg.has_P4e])):
            if len(q) == 0:
                continue
            res[f"place_{lab}"] = {"n": len(q), "since_end_q": q.since_end.quantile([.1, .25, .5, .75, .9]).round(1).tolist(),
                                   "frac_within_10s_after_end": round(float((q.since_end <= 10).mean()), 3),
                                   "won_prev": round(float(q.won_prev.mean()), 3), "won_next": round(float(q.won_next.mean()), 3)}
        pa = p[p.cid.isin(good.cid) & p.anchor]
        res["anchor_W_share"] = round(float(pa.has_W.mean()), 3) if len(pa) else None
    json.dump(res, open(RES / "results/round_align.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
