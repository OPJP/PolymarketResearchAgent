"""Iteration 7, X97 step 3 / X99 step 1 (assumptions panel iter6 P1 step 3, P3 step 1): what the shared feed carries.
Census bursts split by P4e (0x4ebc2722) membership (a P4e BUY signing on the burst token in [t0 - 1 s, t0 + 10 s]):
co-signed (P4e in burst, wallet led / near), P4e-alone (P4e in burst, wallet absent), wallet without P4e, absent without P4e.
Same per-map binomial GLM on bo3.gg team differences (rounds won W, opening kills FK, clutches CL, bomb plants BP).
Output: results/census_p4e_types.json

Original docstring: Iteration 5 (X58 step 3, census event type): the X50 recipe applied to the census bursts (code/iter5/census.py):
wallet-led/near bursts vs wallet-absent bursts (informed BUY bursts with a >= 3c move at +10 s). Original X50 docstring:
Iteration 4, X50 (assumptions iter3 P4, clock-free part): which in-round event type does the taker signal follow?
16-22 Oct (development). Per CS2 map market the wallet traded that bo3.gg parsed (same matching as code/bo3_rounds.py:
team-name prefixes + map number), per team: the number of its take EVENTS buying that team in that map market (orders
signed within 5 ms merged) and the bo3 per-map team totals: rounds won (W), opening kills (FK), clutches won (CL),
bomb plants (BP), kills (K), trade kills (TK).
Map fixed effects: a binomial GLM of the share of the map's take events on team A against the team differences
(dW, dFK, ...), weighted by the map's number of take events (equivalent to a Poisson model with map fixed effects).
The key contrast: does dFK carry weight beyond dW (opening-kill team loses the round in 28% of rounds)?
Also the pack (P4e 0x4ebc2722) the same way. Output: results/event_type_counts.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import HttpClient  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
P4E = "0x4ebc2722"
DAYS = ("2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22")
STATS = {"W": "win", "FK": "first_kills", "CL": "clutches", "BP": "bomb_plants", "K": "kills", "TK": "trade_kills"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def main():
    h = HttpClient()
    bl = []
    for day in DAYS:
        d, _ = h.get_json("https://api.bo3.gg/api/v2/matches/finished", {"date": day, "filter[discipline_id][eq]": 1}, adapter="bo3gg.matches", max_age=None)
        for tier, v in (d or {}).get("data", {}).get("tiers", {}).items():
            for m in v.get("matches", []):
                if m.get("parsed_status") == "done":
                    bl.append(m["slug"])
    mj = json.load(open(OUT / "markets_dev.json"))
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols + ["cid", "oi"])
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted((OUT / "calldata_pub").glob("*.parquet"))])
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi"]).drop_duplicates("token_id")
    tok = {str(k): v for k, v in zip(o.token_id, zip(o.cid, o.oi))}
    b["tok"] = b.token_id.astype(str)
    b = b[b.tok.isin(tok)].copy()
    b["cid"] = b.tok.map(lambda t: tok[t][0])
    b["oi"] = b.tok.map(lambda t: tok[t][1])
    cd = pd.concat([a, b.drop(columns=["tok"])], ignore_index=True)
    B = pd.read_parquet(OUT / "census_bursts.parquet")
    B["sign_ms"] = B.t0 * 1000.0
    cd["maker"] = cd.maker.str.lower()
    p4 = cd[(cd.idx == -1) & (cd.side == 0) & cd.maker.str.startswith("0x4ebc2722")].copy()
    p4["key"] = list(zip(p4.cid, p4.oi))
    p4g = {k: np.sort(g.sign_ms.to_numpy(float)) for k, g in p4.groupby("key")}
    inb = []
    for r in B.itertuples():
        s_ = p4g.get((r.cid, r.oi))
        inb.append(bool(s_ is not None and np.any((s_ >= r.t0 * 1000 - 1000) & (s_ <= r.t0 * 1000 + 10000))))
    B["p4e"] = inb
    pres = B.label.isin(["wallet-led", "wallet-near"])
    absn = B.label == "wallet-absent"
    who = {"cosigned_p4e_and_wallet": B[B.p4e & pres], "p4e_alone_wallet_absent": B[B.p4e & absn],
           "wallet_without_p4e": B[~B.p4e & pres], "absent_without_p4e": B[~B.p4e & absn]}
    print({k: len(v) for k, v in who.items()}, flush=True)
    rows = []
    for cid, x in mj.items():
        if x.get("sportsMarketType") != "child_moneyline":
            continue
        mm = re.search(r"Map (\d)", x.get("question", ""))
        if not mm:
            continue
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        an, bn = norm(outs[0])[:6], norm(outs[1])[:6]
        cand = [s for s in bl if an in norm(s) and bn in norm(s)]
        if not cand:
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [y for y in (g or {}).get("games") or [] if y.get("number") == int(mm.group(1))]
        if not gm:
            continue
        r, _ = h.get_json(f"https://api.bo3.gg/api/v1/games/{gm[0]['id']}/rounds", {}, adapter="bo3gg.rounds", max_age=None)
        rounds = (r or {}).get("game_rounds") if isinstance(r, dict) else None
        if not rounds:
            continue
        tot = {0: {k: 0.0 for k in STATS}, 1: {k: 0.0 for k in STATS}}
        ok = True
        for z in rounds:
            for t in z.get("game_round_team_clans") or []:
                cn = norm(t.get("clan_name"))[:6]
                side = 0 if cn == an else (1 if cn == bn else None)
                if side is None:
                    ok = False
                    continue
                for k, f in STATS.items():
                    tot[side][k] += float(t.get(f) or 0)
        if not ok or tot[0]["W"] + tot[1]["W"] == 0:
            continue
        rec = {"cid": cid, "rounds": len(rounds), **{f"d{k}": tot[0][k] - tot[1][k] for k in STATS}}
        for lab, T in who.items():
            g2 = T[T.cid == cid].sort_values("sign_ms")
            rec[f"{lab}_n0"] = int((g2.oi == 0).sum())
            rec[f"{lab}_n1"] = int((g2.oi == 1).sum())
        rows.append(rec)
    X = pd.DataFrame(rows)
    res = {"maps": int(len(X))}
    for lab in who:
        y = X[(X[f"{lab}_n0"] + X[f"{lab}_n1"]) > 0].copy()
        n = y[f"{lab}_n0"] + y[f"{lab}_n1"]
        frac = y[f"{lab}_n0"] / n
        out = {"maps": int(len(y)), "events": int(n.sum()),
               "corr_share_vs": {k: round(float(np.corrcoef(frac, y[f"d{k}"] / y.rounds)[0, 1]), 3) for k in STATS}}
        for name, cols_ in (("W", ["dW"]), ("FK", ["dFK"]), ("W+FK", ["dW", "dFK"]), ("W+FK+CL+BP", ["dW", "dFK", "dCL", "dBP"]), ("W+K", ["dW", "dK"])):
            Z = sm.add_constant(y[cols_].astype(float) / 10.0)
            try:
                m = sm.GLM(frac, Z, family=sm.families.Binomial(), freq_weights=n).fit()
                out[name] = {"coef": {c: round(float(v), 3) for c, v in m.params.items()}, "p": {c: float(f"{v:.3g}") for c, v in m.pvalues.items()},
                             "aic": round(float(m.aic), 1)}
            except Exception as e:  # noqa: BLE001
                out[name] = {"error": repr(e)[:120]}
        res[lab] = out
    json.dump(res, open(RES / "census_p4e_types.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
