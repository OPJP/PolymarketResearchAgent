"""X226 extension (iteration 16, after the main run): clutch rounds as an in-round swing measure. X226 (mechanics panel iter-15 P4): clock-free R vs K from per-map counts of the wallet's value changes.
Pre-registered in NOTES iteration 16. Maps: CS2 map books of 16-22 Oct (before H) with >= 30 wallet maker orders and bo3
rounds (cached responses, no new request needed). Per map: V-change decisions (dark_split rows: burst tops, 16-22 Oct)
on the map book inside [bo3 begin_at - 60 s, begin_at + duration + 120 s]; classes large (|dV| >= 4c), small (1-3c),
co-repriced (another book of the event re-priced by the wallet within 5 ms). Negative binomial of each count on kills
per round and plants per round with log(rounds) as offset; variants with log(own filled maker orders) and log(1 + public
prints) as controls, and with log(rounds) free. Output: results/map_counts.json"""
from __future__ import annotations

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
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(CODE / "iter12"))
import round_markov_fit as R  # noqa: E402
from polyrea.adapters.http import shared_client  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")


def main():
    h = shared_client()
    slugs = R.bo3_maps(h)
    mk = json.load(open(OUT / "markets_dev.json"))
    d = pd.read_parquet(SP)
    d = d[d.dtop.notna() & (d.dtop.abs() >= 0.01 - 1e-9)].copy()
    d["ts"] = d.t / 1000.0
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "cid", "role"])
    o = o[o.role == "maker"]
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    bad = set(cd.loc[cd.maker == R.WALLET, "tx"])
    ev_t = {ev: np.sort(g.ts.to_numpy(float)) for ev, g in d.groupby("event")}
    rows = []
    for cid, x in mk.items():
        if x.get("sportsMarketType") != "child_moneyline" or not x.get("question", "").startswith("Counter-Strike"):
            continue
        mm = re.search(r"Map (\d)", x["question"])
        if not mm:
            continue
        mapno = int(mm.group(1))
        if (o.cid == cid).sum() < 30:
            continue
        outs = json.loads(x["outcomes"]) if isinstance(x["outcomes"], str) else x["outcomes"]
        a, b = R.norm(outs[0])[:6], R.norm(outs[1])[:6]
        cand = [s for s in slugs if a in R.norm(s) and b in R.norm(s)]
        if not cand:
            continue
        g, _ = h.get_json(f"https://api.bo3.gg/api/v1/matches/{cand[0]}", {"with": "games"}, adapter="bo3gg.match", max_age=None)
        gm = [yy for yy in (g.get("games") or []) if yy.get("number") == mapno]
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
        if hi >= R.H:
            continue
        kills = plants = clutch = 0
        for z in rounds:
            for q in z.get("game_round_team_clans") or []:
                kills += int(q.get("kills") or 0)
                plants += int(q.get("bomb_plants") or 0)
                clutch += int(q.get("clutches") or 0)
        dm = d[(d.cid == cid) & (d.ts >= lo) & (d.ts <= hi)]
        tt = dm.ts.to_numpy(float)
        other = np.setdiff1d(ev_t.get(dm.event.iloc[0], np.array([])) if len(dm) else np.array([]), tt)
        co = np.array([bool(len(other)) and np.min(np.abs(other - t0)) <= 0.005 for t0 in tt]) if len(tt) else np.zeros(0, bool)
        big = (dm.dtop.abs() >= 0.04 - 1e-9).to_numpy()
        own = int(((o.cid == cid) & (o.sign_ms / 1000 >= lo) & (o.sign_ms / 1000 <= hi)).sum())
        tp = R.TAPES / f"{cid}_tkw.parquet"
        npub = 0
        if tp.exists():
            tpd = pd.read_parquet(tp, columns=["timestamp", "transactionHash"])
            npub = int(((tpd.timestamp >= lo) & (tpd.timestamp <= hi) & ~tpd.transactionHash.isin(bad)).sum())
        rows.append({"cid": cid, "map": mapno, "build": bool(pd.Timestamp(x.get("gameStartTime")).timestamp() < R.SPLIT),
                     "rounds": len(rounds), "kills": kills, "plants": plants, "clutch": clutch, "dur": dur,
                     "n_all": int(len(dm)), "n_large": int(big.sum()), "n_small": int((~big).sum()),
                     "n_co_large": int((big & co).sum()), "n_co_small": int((~big & co).sum()),
                     "own_orders": own, "pub_prints": npub})
    D = pd.DataFrame(rows)
    D = D[D.own_orders > 0].copy()
    D["kpr"] = D.kills / D.rounds
    D["ppr"] = D.plants / D.rounds
    D["kpr_c"] = D.kpr - D.kpr.mean()
    D["ppr_c"] = D.ppr - D.ppr.mean()
    D["cpr_c"] = D.clutch / D.rounds - (D.clutch / D.rounds).mean()
    D["l_own"] = np.log(D.own_orders)
    D["l_pub"] = np.log1p(D.pub_prints)
    D["l_rounds"] = np.log(D.rounds)
    out = {"maps": int(len(D)), "corr_kills_rounds": round(float(np.corrcoef(D.kills, D.rounds)[0, 1]), 3),
           "kpr_sd": round(float(D.kpr.std()), 3), "ppr_sd": round(float(D.ppr.std()), 3),
           "means": {c: round(float(D[c].mean()), 2) for c in ["rounds", "kills", "plants", "n_all", "n_large", "n_small", "n_co_large", "n_co_small", "own_orders", "pub_prints"]}}
    specs = {"offset_only": ["kpr_c", "ppr_c", "cpr_c"], "with_controls": ["kpr_c", "ppr_c", "cpr_c", "l_own", "l_pub"]}
    out["clutch_per_round_mean_sd"] = [round(float((D.clutch / D.rounds).mean()), 3), round(float((D.clutch / D.rounds).std()), 3)]
    for ycol in ["n_all", "n_large", "n_small"]:
        for nm, xs in specs.items():
            X = sm.add_constant(D[xs].astype(float))
            off = None if nm == "rounds_free" else np.log(D.rounds.astype(float))
            try:
                m = sm.NegativeBinomial(D[ycol].astype(float), X, offset=off).fit(disp=0, maxiter=200)
                kind = "negbin"
            except Exception:  # noqa: BLE001
                m = sm.GLM(D[ycol].astype(float), X, family=sm.families.Poisson(), offset=off).fit(cov_type="HC1")
                kind = "poisson_hc1"
            out[f"{ycol}|{nm}"] = {"model": kind, **{k: {"coef": round(float(m.params[k]), 3), "se": round(float(m.bse[k]), 3), "p": round(float(m.pvalues[k]), 4)} for k in xs}}
    D.to_parquet(OUT / "iter16" / "map_counts_clutch_rows.parquet", index=False)
    (RES / "map_counts_clutch.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
