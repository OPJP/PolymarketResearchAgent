"""Iteration 9, X119 timing part (information panel iter8 P2 step 2, historical censored version): share of the wallet's
Dota maker signing bursts (orders within 200 ms) on the 10-22 maps that fall 0-6 s after a kill (own team of the
order's token / other team / any), at the P4e-only per-map D, against 400 shifted clocks (D + U(+-20..300) s).
Signature (panel): >= 50% of re-pricing bursts within 6 s of a spectator-clock event. Output: results/dota_burst_events.json"""
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import shared_client
from polyrea.adapters.polymarket import PolymarketData
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SERIES = {"dota2-ty-gl-2026-10-22": [9056215433, 9056271057], "dota2-liquid-1win-2026-10-22": [9056618744, 9056794318],
          "dota2-ts8-legion1-2026-10-22": [9056353535, 9056429802]}
D_P4E = {9056215433: 1043, 9056271057: 1050, 9056618744: 1033, 9056794318: 1033, 9056353535: 840, 9056429802: 840}
def norm(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())
h = shared_client()
ud = pd.read_parquet(OUT / "universe_dota.parquet"); ud = ud[ud.event_slug.isin(SERIES) & (ud.smt == "child_moneyline")]
mk, _ = PolymarketData().markets_by_condition(sorted(ud.cid))
cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["idx", "maker", "token_id", "sign_ms", "salt"])
cd["maker"] = cd.maker.str.lower(); cd["token_id"] = cd.token_id.astype(str)
wo = cd[(cd.maker == W) & (cd.idx != -1)].drop_duplicates(["salt", "sign_ms"])
rng = np.random.default_rng(4)
tot = {"own": [0, np.zeros(400)], "other": [0, np.zeros(400)], "any": [0, np.zeros(400)]}
nb = 0
for ev, mids in SERIES.items():
    for r in ud[ud.event_slug == ev].itertuples():
        x = mk.get(r.cid) or {}
        mm = re.search(r"Game (\d)", x.get("question", ""))
        if not mm or int(mm.group(1)) > len(mids): continue
        mid = mids[int(mm.group(1)) - 1]
        g, _ = h.get_json(f"https://api.opendota.com/api/matches/{mid}", {}, adapter="opendota.match", max_age=None)
        rn = norm(g.get("radiant_name") or (g.get("radiant_team") or {}).get("name")); dn = norm(g.get("dire_name") or (g.get("dire_team") or {}).get("name"))
        K = np.array([(k["time"], 0 if p.get("player_slot", 0) < 128 else 1) for p in g.get("players") or [] for k in (p.get("kills_log") or [])], float)
        K = K[K[:, 0] <= 1200]
        outs = json.loads(x["outcomes"]) if isinstance(x.get("outcomes"), str) else x.get("outcomes")
        toks = [str(t) for t in (json.loads(x["clobTokenIds"]) if isinstance(x.get("clobTokenIds"), str) else x.get("clobTokenIds"))]
        side = {}
        for i, nm in enumerate(outs):
            n5 = norm(nm)[:5]; side[toks[i]] = 0 if n5 and n5 in rn else (1 if n5 and n5 in dn else None)
        o = wo[wo.token_id.isin(toks)].sort_values("sign_ms")
        o = o[(o.sign_ms.diff().fillna(1e9) > 200)]  # burst starts
        st = float(g["start_time"]); D0 = D_P4E[mid]
        rel = o.sign_ms.to_numpy(float) / 1000 - st
        sd = np.array([side.get(t) for t in o.token_id])
        ok = np.array([s is not None for s in sd]); rel, sd = rel[ok], sd[ok].astype(int)
        keep = (rel - D0 > 0) & (rel - D0 < 1200); rel, sd = rel[keep], sd[keep]
        nb += len(rel)
        shifts = rng.choice([-1, 1], 400) * rng.uniform(20, 300, 400)
        for name, f in (("own", lambda s_: K[:, 1] == s_), ("other", lambda s_: K[:, 1] != s_), ("any", lambda s_: np.ones(len(K), bool))):
            def cnt(D):
                c = 0
                for t_, s_ in zip(rel, sd):
                    lag = t_ - D - K[f(s_), 0]
                    c += int(((lag >= 0) & (lag <= 6)).any())
                return c
            tot[name][0] += cnt(D0)
            tot[name][1] += np.array([cnt(D0 + s) for s in shifts])
res = {"bursts": int(nb)}
for k, (obs, nul) in tot.items():
    res[k] = {"share_true": round(obs / max(nb, 1), 4), "share_null_mean": round(float(nul.mean() / max(nb, 1)), 4),
              "null_p95": round(float(np.percentile(nul, 95) / max(nb, 1)), 4), "p": round(float((nul >= obs).mean()), 4), "n_true": int(obs)}
print(json.dumps(res, indent=1)); json.dump(res, open(RES / "dota_burst_events.json", "w"), indent=1)
