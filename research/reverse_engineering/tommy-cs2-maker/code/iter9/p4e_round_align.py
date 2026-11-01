"""Iteration 9, X125 step 1 (mechanics panel iter8 P3): does P4e's take-cluster team sequence follow bo3's round-winner
sequence (a public CS2 round clock from on-chain P4e takes)? Per map (16-22 Oct, bo3 parsed maps matched to the
wallet's map markets): Needleman-Wunsch identity of the P4e-cluster team sequence vs the round-winner sequence, against
(a) 200 permutations of the winner sequence and (b) 200 random team sequences of the same length with the map's base
rate. Also the per-map Spearman of P4e's team share vs the team's round-win share. Output: results/p4e_round_align.json"""
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code")); sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter2"))
from polyrea.adapters.http import shared_client
from pack_vs_rounds import nw, norm, bo3_maps
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
h = shared_client(); slugs = bo3_maps(h)
mk = json.load(open(OUT / "markets_dev.json"))
c = pd.read_parquet(OUT / "pack_clusters.parquet")
po = pd.read_parquet(OUT / "pack_orders.parquet", columns=["cluster", "who", "map_no", "team"])
rng = np.random.default_rng(11)
rows = []
for cid, x in mk.items():
    if x.get("sportsMarketType") != "child_moneyline" or not x.get("question", "").startswith("Counter-Strike"):
        continue
    mm = re.search(r"Map (\d)", x["question"])
    if not mm:
        continue
    mapno = int(mm.group(1)); outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
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
    win = [0 if norm(z["winner_clan_name"])[:6] == a else 1 for z in rounds]
    cl_ids = po[(po.map_no == mapno)].cluster.unique()
    cc = c[(c.event == ev) & c.cluster.isin(cl_ids) & c.has_P4e].sort_values("t0")
    if len(cc) < 5:
        continue
    team = list(cc.team.astype(int))
    mt, al = nw(team, win)
    ident = mt / max(al, 1)
    perm = [(lambda q: q[0] / max(q[1], 1))(nw(team, list(rng.permutation(win)))) for _ in range(200)]
    p1 = np.mean(team)
    rnd = [(lambda q: q[0] / max(q[1], 1))(nw(list((rng.random(len(team)) < p1).astype(int)), win)) for _ in range(200)]
    rows.append({"cid": cid, "rounds": len(win), "p4e_clusters": len(team), "ident": ident, "perm_mean": float(np.mean(perm)),
                 "perm_p": float(np.mean(np.array(perm) >= ident)), "rand_mean": float(np.mean(rnd)), "rand_p": float(np.mean(np.array(rnd) >= ident)),
                 "p4e_share_team0": 1 - p1, "roundwin_share_team0": 1 - float(np.mean(win))})
X = pd.DataFrame(rows)
# combine per-map p-values (Fisher) and count maps at p < 0.05
fisher = lambda p: float(stats.chi2.sf(-2 * np.sum(np.log(np.clip(p, 1 / 201, 1))), 2 * len(p)))
res = {"maps": int(len(X)), "ident_mean": round(float(X.ident.mean()), 4), "perm_mean": round(float(X.perm_mean.mean()), 4),
       "rand_mean": round(float(X.rand_mean.mean()), 4), "maps_perm_p_lt_0.05": int((X.perm_p < 0.05).sum()),
       "maps_rand_p_lt_0.05": int((X.rand_p < 0.05).sum()), "fisher_perm": fisher(X.perm_p.to_numpy()), "fisher_rand": fisher(X.rand_p.to_numpy()),
       "share_spearman": [round(float(v), 4) for v in stats.spearmanr(X.p4e_share_team0, X.roundwin_share_team0)],
       "p4e_clusters_per_round_median": round(float((X.p4e_clusters / X.rounds).median()), 3)}
print(json.dumps(res, indent=1))
json.dump(res, open(RES / "p4e_round_align.json", "w"), indent=1)
