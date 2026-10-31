"""H-C data: ESPN soccer key events (goals, red cards, with wall-clock) for a deterministic sample
of RN1's in-play soccer events, plus public tapes (taker + maker rows) of RN1's top-3 markets per event.
ESPN soccer was not used by the project (its ESPN adapter covers only US leagues)."""
import json, pickle, random, re, sys, difflib
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import S, W
from polyrea.adapters.http import shared_client
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.profile import resolution_info

LEAGUE = {"lal": "esp.1", "epl": "eng.1", "sea": "ita.1", "bun": "ger.1", "fl1": "fra.1", "ucl": "uefa.champions", "uel": "uefa.europa",
          "ere": "ned.1", "por": "por.1", "mex": "mex.1", "arg": "arg.1", "bra": "bra.1", "tur": "tur.1", "elc": "eng.2", "bl2": "ger.2",
          "es2": "esp.2", "unl": "uefa.nations", "mls": "usa.1"}
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
http = shared_client(); pm = PolymarketData()
t = pd.read_pickle(S / "rn1_trades.pkl")
markets = pickle.load(open(S / "rn1_markets.pkl", "rb"))
t["lg"] = t.event_slug.str.split("-").str[0]
t = t[t.lg.isin(LEAGUE)]
gst = {c: pd.Timestamp(m["gameStartTime"]).timestamp() for c, m in markets.items() if m.get("gameStartTime")}
t = t[t.condition_id.map(lambda c: c in gst)]
t = t[t.ts >= t.condition_id.map(gst)]
ev = t.groupby("event_slug").agg(lg=("lg", "first"), n=("ts", "size"), cid0=("condition_id", "first")).reset_index()
ev = ev[ev.n >= 10]
rng = random.Random(11)
evs = sorted(rng.sample(list(ev.event_slug), min(70, len(ev))))
print("eligible soccer events", len(ev), "sampled", len(evs))


def norm(s):
    s = re.sub(r"[^a-z ]", " ", (s or "").lower())
    return " ".join(w for w in s.split() if w not in ("fc", "cf", "club", "de", "sc", "ac", "afc", "cd", "ud", "sd", "the", "vs"))


def match(e):
    row = ev[ev.event_slug == e].iloc[0]
    m = markets[row.cid0]
    title = ((m.get("events") or [{}])[0].get("title") or "")
    parts = re.split(r"\s+vs\.?\s+", title)
    if len(parts) != 2:
        return None
    kick = gst[row.cid0]
    day = pd.Timestamp(kick, unit="s", tz="UTC").strftime("%Y%m%d")
    try:
        sb, _ = http.get_json(f"{BASE}/{LEAGUE[row.lg]}/scoreboard", {"dates": day}, adapter="espn.soccer.scoreboard", max_age=None)
    except Exception as exc:
        return None
    best, bs = None, 0
    for x in sb.get("events") or []:
        if abs(pd.Timestamp(x["date"]).timestamp() - kick) > 1800:
            continue
        comps = x.get("competitions", [{}])[0].get("competitors", [])
        names = [c.get("team", {}).get("displayName", "") for c in comps]
        if len(names) != 2:
            continue
        sc = max(difflib.SequenceMatcher(None, norm(parts[0]), norm(names[0])).ratio() + difflib.SequenceMatcher(None, norm(parts[1]), norm(names[1])).ratio(),
                 difflib.SequenceMatcher(None, norm(parts[0]), norm(names[1])).ratio() + difflib.SequenceMatcher(None, norm(parts[1]), norm(names[0])).ratio())
        if sc > bs:
            best, bs = x, sc
    if best is None or bs < 0.9:
        return None
    sm, _ = http.get_json(f"{BASE}/{LEAGUE[row.lg]}/summary", {"event": best["id"]}, adapter="espn.soccer.summary", max_age=None)
    kes = []
    for k in sm.get("keyEvents") or []:
        wc = k.get("wallclock")
        if not wc:
            continue
        typ = (k.get("type") or {}).get("type") or ""
        kes.append({"ts": int(pd.Timestamp(wc).timestamp()), "type": typ, "scoring": bool(k.get("scoringPlay")), "text": (k.get("text") or "")[:100]})
    return {"event_slug": e, "lg": row.lg, "espn_id": best["id"], "espn_name": best.get("name"), "title": title, "match_score": bs, "kick": kick, "key_events": kes}


games = [g for g in (match(e) for e in evs) if g]
print("matched", len(games))
json.dump(games, open(S / "soccer_games.json", "w"))

jobs = []
for g in games:
    x = t[t.event_slug == g["event_slug"]].groupby("condition_id").usdc.sum().sort_values(ascending=False).head(3)
    for cid in x.index:
        r = resolution_info(markets[cid]); tokens = json.loads(markets[cid].get("clobTokenIds") or "[]")
        if r["resolved"] and len(tokens) == 2:
            jobs.append((g["event_slug"], cid, tokens, r["payout"].get(str(tokens[0]), 0.0), int(g["kick"])))


def load(j):
    e, cid, tokens, pay0, kick = j
    a, b = kick - 600, kick + 9000
    taker, _, _ = pm.market_trades(cid, start=a, end=b, taker_only=True)
    full, _, _ = pm.market_trades(cid, start=a, end=b, taker_only=False)
    keys = {}; trow = []; mrow = []
    for r in taker:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        keys[k] = keys.get(k, 0) + 1
        if str(r.get("asset")) in tokens:
            trow.append({"event_slug": e, "condition_id": cid, "ts": int(r["timestamp"]), "outcome": tokens.index(str(r["asset"])), "side": r.get("side"), "price": float(r["price"]), "size": float(r["size"]), "wallet": (r.get("proxyWallet") or "").lower(), "tx": r.get("transactionHash")})
    for r in full:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        if keys.get(k, 0) > 0:
            keys[k] -= 1; continue
        if str(r.get("asset")) in tokens:
            mrow.append({"event_slug": e, "condition_id": cid, "ts": int(r["timestamp"]), "outcome": tokens.index(str(r["asset"])), "side": r.get("side"), "price": float(r["price"]), "size": float(r["size"]), "wallet": (r.get("proxyWallet") or "").lower(), "tx": r.get("transactionHash")})
    return pd.DataFrame(trow), pd.DataFrame(mrow)

with ThreadPoolExecutor(6) as ex:
    parts = list(ex.map(load, jobs))
pd.concat([p[0] for p in parts], ignore_index=True).to_pickle(S / "soccer_taker.pkl")
pd.concat([p[1] for p in parts], ignore_index=True).to_pickle(S / "soccer_maker.pkl")
json.dump({"markets": [{"event_slug": j[0], "condition_id": j[1], "pay0": j[3], "kick": j[4], "slug": markets[j[1]].get("slug"),
                        "fee": markets[j[1]].get("feeSchedule")} for j in jobs]}, open(S / "soccer_markets.json", "w"), default=str)
print("markets", len(jobs), "taker rows", sum(len(p[0]) for p in parts), "maker rows", sum(len(p[1]) for p in parts))
