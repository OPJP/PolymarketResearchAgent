"""Iteration 9, X123: training data for a public Dota 2 win-probability model V (no wallet data). OpenDota /proMatches
pages, matches started in [2026-10-08, 2026-10-21) (development dates before VALIDATE; the five VALIDATE test maps and
the 10-31 maps are excluded), parsed /matches/<id>: per game minute radiant_gold_adv, radiant_xp_adv, kills by side up
to that minute, radiant_win. Output: .cache/re/tommy-cs2-maker/dota_train_minutes.parquet"""
import sys, time, json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import shared_client
LO, HI = 1791417600, 1792540800  # 10-08 .. 10-21
TEST = {9056215433, 9056271057, 9056618744, 9056794318, 9056353535, 9056429802, 9069952836, 9070062078}
h = shared_client()
ids, last = [], None
for page in range(40):
    p = {} if last is None else {"less_than_match_id": last}
    d, _ = h.get_json("https://api.opendota.com/api/proMatches", p, adapter="opendota.pro", max_age=None if last else 86400)
    if not d:
        break
    for m in d:
        if LO <= m.get("start_time", 0) < HI and m["match_id"] not in TEST and (m.get("duration") or 0) > 900:
            ids.append(m["match_id"])
    last = d[-1]["match_id"]
    if d[-1].get("start_time", 0) < LO:
        break
print("candidates", len(ids), flush=True)
rng = np.random.default_rng(3)
ids = list(rng.permutation(ids))[:int(sys.argv[1]) if len(sys.argv) > 1 else 160]
rows = []
for i, mid in enumerate(ids):
    try:
        g, _ = h.get_json(f"https://api.opendota.com/api/matches/{int(mid)}", {}, adapter="opendota.match", max_age=None)
    except Exception as e:
        print("err", mid, repr(e)[:80], flush=True); continue
    ga, xa = g.get("radiant_gold_adv"), g.get("radiant_xp_adv")
    if not ga or not xa or g.get("radiant_win") is None:
        continue
    kt = [(k["time"], 1 if p.get("player_slot", 0) < 128 else -1) for p in g.get("players") or [] for k in (p.get("kills_log") or [])]
    kt = np.array(kt, float) if kt else np.zeros((0, 2))
    for mi in range(1, min(len(ga), len(xa))):
        kd = float(kt[kt[:, 0] <= mi * 60, 1].sum()) if len(kt) else 0.0
        rows.append({"match_id": int(mid), "minute": mi, "gold_adv": float(ga[mi]), "xp_adv": float(xa[mi]), "kill_diff": kd,
                     "dur_min": g.get("duration", 0) / 60, "radiant_win": int(bool(g["radiant_win"]))})
    if i % 20 == 0:
        print(i, len(rows), flush=True)
pd.DataFrame(rows).to_parquet(ROOT / ".cache/re/tommy-cs2-maker/dota_train_minutes.parquet", index=False)
print("done", len(rows), len(set(r["match_id"] for r in rows)))
