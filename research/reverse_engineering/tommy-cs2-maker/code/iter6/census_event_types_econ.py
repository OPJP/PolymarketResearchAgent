"""Iteration 6 (Y1-economy vs plant event type): the X50 / census GLM with two new per-team round counts from bo3.gg:
  U  = upset wins: rounds won while the team's equipment_value was below 0.8 x the opponent's (eco / force wins);
  BR = breaks: rounds won right after the opponent won the previous round (a reversal of the round sequence).
Burst classes from census_bursts.parquet (wallet-led / near, wallet-absent). Binomial GLM with map weights of the share of
the class's bursts on team A against dW and the new differences per 10 rounds. Development data (16-22 Oct) only.
Output: results/census_event_types_econ.json
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
EXTRA = ("U", "BR")


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
    who = {"wallet_led_or_near": B[B.label.isin(["wallet-led", "wallet-near"])], "wallet_absent": B[B.label == "wallet-absent"],
           }
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
        tot = {0: {k: 0.0 for k in list(STATS) + list(EXTRA)}, 1: {k: 0.0 for k in list(STATS) + list(EXTRA)}}
        ok = True
        prev_w = None
        for z in sorted(rounds, key=lambda q: q.get("round_number") or 0):
            tc = z.get("game_round_team_clans") or []
            per = {}
            for t in tc:
                cn = norm(t.get("clan_name"))[:6]
                side = 0 if cn == an else (1 if cn == bn else None)
                if side is None:
                    ok = False
                    continue
                per[side] = t
                for k, f in STATS.items():
                    tot[side][k] += float(t.get(f) or 0)
            if len(per) == 2:
                wn = [sd for sd in (0, 1) if float(per[sd].get("win") or 0) > 0]
                if len(wn) == 1:
                    w = wn[0]
                    ev_w = float(per[w].get("equipment_value") or 0); ev_l = float(per[1 - w].get("equipment_value") or 0)
                    if ev_l > 0 and ev_w < 0.8 * ev_l:
                        tot[w]["U"] += 1
                    if prev_w is not None and prev_w != w:
                        tot[w]["BR"] += 1
                    prev_w = w
        if not ok or tot[0]["W"] + tot[1]["W"] == 0:
            continue
        rec = {"cid": cid, "rounds": len(rounds), **{f"d{k}": tot[0][k] - tot[1][k] for k in list(STATS) + list(EXTRA)}}
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
               "corr_share_vs": {k: round(float(np.corrcoef(frac, y[f"d{k}"] / y.rounds)[0, 1]), 3) for k in list(STATS) + list(EXTRA)}}
        for name, cols_ in (("W", ["dW"]), ("W+U", ["dW", "dU"]), ("W+BR", ["dW", "dBR"]), ("W+U+BR+BP", ["dW", "dU", "dBR", "dBP"])):
            Z = sm.add_constant(y[cols_].astype(float) / 10.0)
            try:
                m = sm.GLM(frac, Z, family=sm.families.Binomial(), freq_weights=n).fit()
                out[name] = {"coef": {c: round(float(v), 3) for c, v in m.params.items()}, "p": {c: float(f"{v:.3g}") for c, v in m.pvalues.items()},
                             "aic": round(float(m.aic), 1)}
            except Exception as e:  # noqa: BLE001
                out[name] = {"error": repr(e)[:120]}
        res[lab] = out
    json.dump(res, open(RES / "census_event_types_econ.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
