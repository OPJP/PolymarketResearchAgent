"""X194 step 3 (MLB part): the operator's September MLB takes (0x52661b8e, 'TommyLeePeeecan') against MLB statsapi
plays (official wall clocks, key-free; cached through the shared polyrea client). Development data (all before H).

Events: each play's about.endTime (the official result time), scoring plays (isScoringPlay) signed by the batting
team (+1 = the team it bought would be favoured if it is the scoring team), and pitch endTimes (playEvents). Decisions:
its taker orders (calldata, sign ms) and its maker orders. Units: each game from its first to its last play end, on a
shifted timeline (offset k x 1e6 s). Tests: indicators.event_study at +-10 s (0.25-s bins) and +-60 s (1-s bins) with
the swap null, signed for scoring plays; the lag histogram of sign time minus the latest preceding play end vs a
uniform-time null in the same games; direction: share of takes within 0-30 s after a scoring play that buy the
scoring team. Output: results/mlb_twin.json
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import indicators as ind  # noqa: E402
from polyrea.adapters.http import shared_client  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker/sib5266_sport"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SIB = "0x52661b8e13158f23d94a9e8302ab0295704c22ac"
ONBASE = {"single", "double", "triple", "home_run", "walk", "intent_walk", "hit_by_pitch", "field_error", "catcher_interf"}


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() if s else np.nan


def norm(x):
    return re.sub(r"[^a-z]", "", (x or "").lower())


def main():
    h = shared_client()
    a = pd.read_parquet(OUT / "activity_sep_sport.parquet")
    a = a[a.pre == "mlb"]
    c = pd.concat([pd.read_parquet(p) for p in sorted((OUT / "calldata").glob("*.parquet"))], ignore_index=True)
    c["maker"] = c.maker.str.lower()
    own = c[c.maker == SIB].copy()
    own["role"] = np.where(own.idx >= 0, "maker", "taker")
    own = own.drop_duplicates(["salt", "sign_ms", "role"])
    tok_team = {}
    for r in a.drop_duplicates(["cid", "oi"]).itertuples():
        pass
    # outcome (team) per traded token from activity rows: tx -> outcome name
    tx_out = a.groupby("tx").agg(outcome=("title", "first"), ev=("ev", "first"), cid=("cid", "first"))
    act = pd.read_parquet(OUT / "activity_sep_sport.parquet")
    # need the outcome names: reload from the activity file columns (title has 'A vs. B'; outcome column not stored) -> use calldata token + activity oi
    tok_oi = {}
    games = {}
    rows = []
    for ev, g in a.groupby("ev"):
        m = re.match(r"mlb-([a-z]+)-([a-z]+)-(\d{4}-\d{2}-\d{2})", ev)
        if not m:
            continue
        title = g.title.iloc[0]
        parts = title.split(" vs. ")
        if len(parts) != 2:
            continue
        t_a, t_b = norm(parts[0]), norm(parts[1])
        day = datetime.fromisoformat(m.group(3))
        pk = None
        for dd in (0, -1, 1):
            d, _ = h.get_json("https://statsapi.mlb.com/api/v1/schedule", {"sportId": 1, "date": (day + timedelta(days=dd)).strftime("%Y-%m-%d")},
                              adapter="mlb.schedule", max_age=None)
            for gg in (d.get("dates") or [{}])[0].get("games", []) if d.get("dates") else []:
                na, nh = norm(gg["teams"]["away"]["team"]["name"]), norm(gg["teams"]["home"]["team"]["name"])
                if {na, nh} == {t_a, t_b} or (t_a in (na + nh) and t_b in (na + nh)):
                    pk = (gg["gamePk"], na, nh)
                    break
            if pk:
                break
        if not pk:
            continue
        f, _ = h.get_json(f"https://statsapi.mlb.com/api/v1.1/game/{pk[0]}/feed/live", {}, adapter="mlb.feed", max_age=None)
        plays = f.get("liveData", {}).get("plays", {}).get("allPlays", [])
        if not plays:
            continue
        pe, sc, pitch, ob = [], [], [], []
        for p in plays:
            e = ts(p["about"].get("endTime"))
            if not np.isfinite(e):
                continue
            pe.append(e)
            et = (p.get("result") or {}).get("eventType") or ""
            if et in ONBASE:
                ob.append((e, pk[2] if not p["about"].get("isTopInning") else pk[1]))
            if p["about"].get("isScoringPlay"):
                bat_home = not p["about"].get("isTopInning")
                scorer = pk[2] if bat_home else pk[1]
                sc.append((e, scorer))
            for q in p.get("playEvents", []):
                if q.get("isPitch"):
                    pt = ts(q.get("endTime"))
                    if np.isfinite(pt) and abs(pt - e) < 3600:
                        pitch.append(pt)
        games[ev] = {"pk": pk[0], "away": pk[1], "home": pk[2], "a": t_a, "b": t_b, "plays": np.sort(pe), "scoring": sc, "onbase": ob, "pitch": np.sort(pitch),
                     "cids": set(g.cid)}
    # token -> team name for the sibling's orders: from activity oi + title order (outcome 0 = first team in title)
    tk_team = {}
    for r in a.itertuples():
        tm = norm(r.title.split(" vs. ")[0]) if r.oi == 0 else norm(r.title.split(" vs. ")[1])
        tk_team[r.tx] = tm
    own = own[own.condition_id.isin(set(a.cid))]
    cid_ev = dict(zip(a.cid, a.ev))
    own["ev"] = own.condition_id.map(cid_ev)
    # token's team: use the activity's oi for txs where the sibling traded that token
    tok2oi = {}
    for r in c[(c.maker == SIB)].itertuples():
        pass
    at = a.drop_duplicates("tx").set_index("tx")
    own["team"] = own.tx.map(lambda t: tk_team.get(t))
    units, dec_t, dec_s, ev_t, ev_s, all_play, lags, lags_null, dirn = [], [], [], [], [], [], [], [], []
    ob_t, ob_s = [], []
    rng = np.random.default_rng(0)
    k = 0
    res = {"mlb_events": int(a.ev.nunique()), "games_mapped": len(games)}
    for ev, G in games.items():
        if len(G["plays"]) < 20:
            continue
        o = own[(own.ev == ev) & (own.role == "taker")]
        if len(o) == 0:
            continue
        off = k * 1e6
        k += 1
        a0, a1 = G["plays"][0] - 300, G["plays"][-1] + 300
        units.append((a0 + off, a1 + off))
        st = o.sign_ms.to_numpy() / 1000
        inu = (st >= a0) & (st < a1)
        st = st[inu]
        teams = o.team.to_numpy()[inu]
        dec_t.append(st + off)
        sgn = np.array([1.0 if (t == G["home"] or (t and t in G["home"])) else -1.0 for t in teams])
        dec_s.append(sgn)
        all_play.append(G["plays"] + off)
        for e, bt in G["onbase"]:
            ob_t.append(e + off)
            ob_s.append(1.0 if bt == G["home"] else -1.0)
        for e, scorer in G["scoring"]:
            ev_t.append(e + off)
            ev_s.append(1.0 if scorer == G["home"] else -1.0)
        j = np.searchsorted(G["plays"], st, side="right") - 1
        lags += list(np.where(j >= 0, st - G["plays"][np.maximum(j, 0)], np.nan))
        u = rng.uniform(a0 + 300, a1 - 300, len(st) * 5)
        jn = np.searchsorted(G["plays"], u, side="right") - 1
        lags_null += list(np.where(jn >= 0, u - G["plays"][np.maximum(jn, 0)], np.nan))
        sct = np.array([e for e, _ in G["scoring"]])
        scs = np.array([1.0 if s == G["home"] else -1.0 for _, s in G["scoring"]])
        if len(sct):
            js = np.searchsorted(sct, st, side="right") - 1
            for i_, jj in enumerate(js):
                if jj >= 0 and 0 <= st[i_] - sct[jj] <= 30:
                    dirn.append(float(sgn[i_] == scs[jj]))
    if not units:
        (RES / "mlb_twin.json").write_text(json.dumps(res, indent=1))
        print(res)
        return
    o_ = np.argsort(np.concatenate(dec_t))
    D = np.concatenate(dec_t)[o_]
    DS = np.concatenate(dec_s)[o_]
    P = np.sort(np.concatenate(all_play))
    E = np.array(ev_t)
    oe = np.argsort(E)
    E, ES = E[oe], np.array(ev_s)[oe]
    U = np.array(units)
    lags, lags_null = np.array(lags), np.array(lags_null)
    edges = [0, 1, 2, 3, 5, 10, 20, 30, 60, 120, 1e9]
    res.update({"games_with_takes": int(len(U)), "takes": int(len(D)), "scoring_plays": int(len(E)),
                "lag_since_last_play_end_hist": {f"{edges[i]}-{edges[i+1]}": round(float(np.mean((lags >= edges[i]) & (lags < edges[i + 1]))), 3) for i in range(len(edges) - 1)},
                "lag_null_hist": {f"{edges[i]}-{edges[i+1]}": round(float(np.mean((lags_null >= edges[i]) & (lags_null < edges[i + 1]))), 3) for i in range(len(edges) - 1)},
                "takes_0_30s_after_scoring_play": len(dirn), "buy_scoring_team_share": round(float(np.mean(dirn)), 3) if dirn else None})
    OBT = np.array(ob_t)
    oo = np.argsort(OBT)
    OBT, OBS = OBT[oo], np.array(ob_s)[oo]
    res["onbase_events"] = int(len(OBT))
    for tag, L, bs, ev_ts, ev_sg in (("onbase_pm10s", 10.0, 0.25, OBT, OBS), ("onbase_pm60s", 60.0, 1.0, OBT, OBS), ("plays_pm10s", 10.0, 0.25, P, None), ("plays_pm60s", 60.0, 1.0, P, None),
                                     ("scoring_pm60s", 60.0, 1.0, E, ES), ("scoring_pm600s", 600.0, 5.0, E, ES)):
        try:
            r = ind.event_study(D, ev_ts, U, max_lag_s=L, bin_s=bs, n_null=500, decision_sign=DS if ev_sg is not None else None, event_sign=ev_sg)
            res[tag] = {k2: r.get(k2) for k2 in ("null", "units_in_null", "n_units", "n_events", "peak_lag_s", "peak_lift", "median_lift", "shape_peak_lag_s",
                                                  "shape_width_s", "shape_lift", "p_level", "p_shape", "p_link", "level_peak_in_flank")}
            if ev_sg is not None:
                res[tag]["signed"] = {k2: r["signed"].get(k2) for k2 in ("shape_peak_lag_s", "shape_z", "p_link")}
        except Exception as e:  # noqa: BLE001
            res[tag] = {"error": repr(e)[:200]}
        print(tag, json.dumps(res[tag])[:400], flush=True)
    (RES / "mlb_twin.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k2: v for k2, v in res.items() if not isinstance(v, dict) or k2.startswith("lag")}, indent=1, default=float)[:2500])


if __name__ == "__main__":
    main()
