"""R1 (round-end) vs R2 (in-round) discriminator: pack clusters per map vs bo3.gg rounds, and the order of teams bought
vs the order of round winners (Needleman-Wunsch identity vs shuffled controls). Also a time-aware alignment: clusters
are mapped to rounds by cumulative bo3 durations anchored at each cluster (local, +-3 rounds), score = clusters whose
predicted round end matches within tol. Development data 16-22 Oct only."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from polyrea.adapters.http import shared_client  # noqa: E402
from common import OUT, RES, SPLIT  # noqa: E402

def norm(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())

def nw(a, b, match=1, mis=-1, gap=-1):
    n, m = len(a), len(b); S = np.zeros((n + 1, m + 1)); S[:, 0] = np.arange(n + 1) * gap; S[0, :] = np.arange(m + 1) * gap
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            S[i, j] = max(S[i - 1, j - 1] + (match if a[i - 1] == b[j - 1] else mis), S[i - 1, j] + gap, S[i, j - 1] + gap)
    # traceback count matches / aligned pairs
    i, j, mt, al = n, m, 0, 0
    while i > 0 and j > 0:
        if S[i, j] == S[i - 1, j - 1] + (match if a[i - 1] == b[j - 1] else mis):
            al += 1; mt += int(a[i - 1] == b[j - 1]); i -= 1; j -= 1
        elif S[i, j] == S[i - 1, j] + gap: i -= 1
        else: j -= 1
    return mt, al

def bo3_maps(h):
    days = [f"2026-10-{d}" for d in range(16, 23)]; slugs = []
    for day in days:
        d, _ = h.get_json("https://api.bo3.gg/api/v2/matches/finished", {"date": day, "filter[discipline_id][eq]": 1}, adapter="bo3gg.matches", max_age=None)
        for tier, v in d["data"]["tiers"].items():
            for m in v.get("matches", []):
                if m.get("parsed_status") == "done": slugs.append(m["slug"])
    return slugs

def main():
    h = shared_client(); slugs = bo3_maps(h)
    mk = json.load(open(OUT / "markets_dev.json"))
    c = pd.read_parquet(OUT / "pack_clusters.parquet")
    po = pd.read_parquet(OUT / "pack_orders.parquet", columns=["cluster", "who", "map_no", "team", "sign_ms", "usd"])
    rng = np.random.default_rng(3); rows = []; seqs = []
    for cid, x in mk.items():
        if x.get("sportsMarketType") != "child_moneyline" or not x.get("question", "").startswith("Counter-Strike"): continue
        mm = re.search(r"Map (\d)", x["question"]);
        if not mm: continue
        mapno = int(mm.group(1)); outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        ev = (x.get("events") or [{}])[0].get("slug")
        a, b = norm(outs[0])[:6], norm(outs[1])[:6]
        cand = [s for s in slugs if a in norm(s) and b in norm(s)]
        if not cand: continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [y for y in (g.get("games") or []) if y.get("number") == mapno]
        if not gm: continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = r.get("game_rounds") if isinstance(r, dict) else None
        if not rounds: continue
        rounds = sorted(rounds, key=lambda z: z["round_number"])
        win = np.array([0 if norm(z["winner_clan_name"])[:6] == a else 1 for z in rounds])
        dur = np.array([z["round_duration"] / 1e9 for z in rounds])
        # clusters on this map market (W or pack) in-play
        cl_ids = po[(po.map_no == mapno)].cluster.unique()
        cc = c[(c.event == ev) & c.cluster.isin(cl_ids)].sort_values("t0")
        if len(cc) < 5: continue
        team = cc.team.to_numpy(); t = cc.t0.to_numpy() / 1000
        p4 = cc[cc.has_P4e]
        mt, al = nw(list(team), list(win))
        ctrl = [nw(list(team), list(rng.permutation(win)))[0] / max(1, nw(list(team), list(rng.permutation(win)))[1]) for _ in range(5)]
        mt4, al4 = nw(list(p4.team), list(win)) if len(p4) >= 5 else (np.nan, np.nan)
        # time-aware local alignment: anchor cluster i at round end k; predicted ends of k-3..k+3 via durations + c
        best = (0, None)
        for cpar in (10, 15, 20, 25, 30):
            hits = 0
            for i in range(len(t)):
                bestk = 0
                for k in range(len(dur)):
                    if win[k] != team[i]: continue
                    E = {k: t[i]}
                    for j in range(k + 1, min(len(dur), k + 4)): E[j] = E[j - 1] + dur[j] + cpar
                    for j in range(k - 1, max(-1, k - 4), -1): E[j] = E[j + 1] - dur[j + 1] - cpar
                    sc = sum(1 for j, e in E.items() if j != k and np.any((np.abs(t - e) <= 4) & (team == win[j])))
                    bestk = max(bestk, sc)
                hits += bestk
            if hits > best[0]: best = (hits, cpar)
        rows.append({"cid": cid, "event": ev, "map": mapno, "gs": x.get("gameStartTime"), "rounds": len(win), "clusters": len(cc),
                     "clusters_P4e": len(p4), "clusters_W": int(cc.has_W.sum()), "nw_ident": mt / max(al, 1), "nw_aligned": al,
                     "nw_ctrl": float(np.mean(ctrl)), "nw4_ident": mt4 / al4 if al4 and al4 == al4 else np.nan,
                     "local_hits_per_cluster": best[0] / len(t), "c_best": best[1]})
    x = pd.DataFrame(rows)
    x.to_parquet(OUT / "pack_vs_rounds.parquet", index=False)
    res = {"maps": len(x), "rounds_total": int(x.rounds.sum()), "clusters_total": int(x.clusters.sum()),
           "clusters_per_round_median": round(float((x.clusters / x.rounds).median()), 2),
           "P4e_clusters_per_round_median": round(float((x.clusters_P4e / x.rounds).median()), 2),
           "W_clusters_per_round_median": round(float((x.clusters_W / x.rounds).median()), 2),
           "nw_identity_mean": round(float(x.nw_ident.mean()), 3), "nw_ctrl_mean": round(float(x.nw_ctrl.mean()), 3),
           "nw4_identity_mean": round(float(x.nw4_ident.mean()), 3),
           "local_hits_per_cluster_median": round(float(x.local_hits_per_cluster.median()), 2), "c_best_mode": x.c_best.mode().tolist()}
    json.dump(res, open(RES / "results/pack_vs_rounds.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
