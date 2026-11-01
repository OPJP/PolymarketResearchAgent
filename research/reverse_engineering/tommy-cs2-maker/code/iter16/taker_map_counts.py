"""X225, clock-free form (mechanics panel iter-15 P3 step 4): in the taker regime (10-01..10-14, development), do the
wallet's sign moments (its FAK orders signed within 50 ms of each other) per map scale with the map's rounds, kills or
plants? Same model as X226 (map_counts.py): negative binomial of sign moments on the map book inside [bo3 begin_at - 60 s,
begin_at + duration + 120 s] on kills per round and plants per round with log(rounds) as offset (and log(rounds) free).
bo3 finished-match lists for 10-01..10-15 (cached adapter, new requests only where the shared cache lacks them).
Output: results/taker_map_counts.json"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[5]
CODE = ROOT / "research/reverse_engineering/tommy-cs2-maker/code"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE / "iter2"))
from pack_vs_rounds import norm  # noqa: E402
from polyrea.adapters.http import shared_client  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    h = shared_client()
    slugs = []
    for day in [f"2026-10-{d:02d}" for d in range(1, 16)]:
        try:
            d, _ = h.get_json("https://api.bo3.gg/api/v2/matches/finished", {"date": day, "filter[discipline_id][eq]": 1}, adapter="bo3gg.matches", max_age=None)
        except Exception:  # noqa: BLE001
            continue
        for tier, v in (d.get("data") or {}).get("tiers", {}).items():
            for m in v.get("matches", []):
                if m.get("parsed_status") == "done":
                    slugs.append(m["slug"])
    mk = json.load(open(OUT / "markets_taker.json"))
    fs = sorted(glob.glob(str(OUT / "calldata_taker/*.parquet")))
    o = pd.concat([pd.read_parquet(f, columns=["maker", "token_id", "sign_ms", "side"]) for f in fs])
    o = o[(o.maker.str.lower() == W) & (o.sign_ms > 1.7e12)].drop_duplicates(["token_id", "sign_ms"])
    tok2cid = {}
    for cid, x in mk.items():
        for t in (json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else (x.get("clobTokenIds") or [])):
            tok2cid[str(t)] = cid
    o["cid"] = o.token_id.astype(str).map(tok2cid)
    o = o[o.cid.notna()].sort_values("sign_ms")
    rows = []
    for cid, x in mk.items():
        if x.get("sportsMarketType") != "child_moneyline" or not str(x.get("question", "")).startswith("Counter-Strike"):
            continue
        if not str(x.get("gameStartTime") or "").startswith("2026-10"):
            continue
        mm = re.search(r"Map (\d)", x["question"])
        if not mm:
            continue
        oo = o[o.cid == cid]
        if len(oo) < 5:
            continue
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        a, b = norm(outs[0])[:6], norm(outs[1])[:6]
        cand = [s for s in slugs if a in norm(s) and b in norm(s)]
        if not cand:
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [yy for yy in (g.get("games") or []) if yy.get("number") == int(mm.group(1))]
        if not gm or not gm[0].get("begin_at"):
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = r.get("game_rounds") if isinstance(r, dict) else None
        if not rounds or len(rounds) < 13:
            continue
        begin = pd.Timestamp(gm[0]["begin_at"]).timestamp()
        dur = float(r.get("duration") or 0) / 1e9
        if not (600 < dur < 7200):
            dur = sum(float(z.get("round_duration") or 0) for z in rounds) / 1e9 + 30 * len(rounds)
        lo, hi = begin - 60, begin + dur + 120
        if hi >= 1792108800:  # keep the taker regime only (before 10-16)
            continue
        kills = plants = 0
        for z in rounds:
            for q in z.get("game_round_team_clans") or []:
                kills += int(q.get("kills") or 0)
                plants += int(q.get("bomb_plants") or 0)
        s = oo.sign_ms.to_numpy(float)
        s = s[(s / 1000 >= lo) & (s / 1000 <= hi)]
        n_mom = int((np.diff(s, prepend=-1e18) > 50).sum()) if len(s) else 0
        mom = s[np.diff(s, prepend=-1e18) > 50] / 1000.0 if len(s) else np.array([])
        toks = (json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else (x.get("clobTokenIds") or []))
        oo2 = oo[(oo.sign_ms / 1000 >= lo) & (oo.sign_ms / 1000 <= hi)].sort_values("sign_ms")
        first = oo2[np.diff(oo2.sign_ms.to_numpy(float), prepend=-1e18) > 50]
        is_a = first.token_id.astype(str).to_numpy() == (str(toks[0]) if toks else "")
        buy = first.side.to_numpy() == 0
        mom_dir = np.where(is_a == buy, 1, -1)  # +1: the moment backs team A (BUY A or SELL B)
        rr = sorted(rounds, key=lambda z: z["round_number"])
        fa = norm(outs[0])
        wn = [norm(z.get("winner_clan_name")) for z in rr]
        a_won = [1 if ((w[:6] == a) or (len(w) >= 3 and (w in fa or fa in w))) else (-1 if ((w[:6] == b) or (len(w) >= 3 and (w in norm(outs[1]) or norm(outs[1]) in w))) else 0) for w in wn]
        rd = [float(z.get("round_duration") or 0) / 1e9 for z in sorted(rounds, key=lambda z: z["round_number"])]
        rows.append({"cid": cid, "rounds": len(rounds), "kills": kills, "plants": plants, "orders": int(len(s)), "moments": n_mom,
                     "begin": begin, "dur": dur, "mom_ts": json.dumps([round(float(x), 3) for x in mom]), "round_dur": json.dumps(rd),
                     "mom_dir": json.dumps([int(v) for v in mom_dir]), "a_won": json.dumps(a_won)})
    D = pd.DataFrame(rows)
    out = {"bo3_slugs": len(slugs), "maps": int(len(D))}
    D = D[D.orders > 0].copy()
    out["maps_with_orders"] = int(len(D))
    if len(D) >= 15:
        D["kpr_c"] = D.kills / D.rounds - (D.kills / D.rounds).mean()
        D["ppr_c"] = D.plants / D.rounds - (D.plants / D.rounds).mean()
        D["l_rounds"] = np.log(D.rounds)
        out["means"] = {c: round(float(D[c].mean()), 2) for c in ["rounds", "kills", "plants", "orders", "moments"]}
        for nm, xs, off in (("offset_only", ["kpr_c", "ppr_c"], np.log(D.rounds.astype(float))), ("rounds_free", ["l_rounds", "kpr_c", "ppr_c"], None)):
            X = sm.add_constant(D[xs].astype(float))
            try:
                m = sm.NegativeBinomial(D.moments.astype(float), X, offset=off).fit(disp=0, maxiter=200)
            except Exception:  # noqa: BLE001
                m = sm.GLM(D.moments.astype(float), X, family=sm.families.Poisson(), offset=off).fit(cov_type="HC1")
            out[nm] = {k: {"coef": round(float(m.params[k]), 3), "se": round(float(m.bse[k]), 3), "p": round(float(m.pvalues[k]), 4)} for k in xs}
    pd.DataFrame(rows).to_parquet(OUT / "iter16" / "taker_map_rows.parquet", index=False)
    (RES / "taker_map_counts.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
