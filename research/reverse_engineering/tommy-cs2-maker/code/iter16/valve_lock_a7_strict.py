"""X227 exploratory, strict game match (gate failed: not a verdict). dota2-synaps-hn-2026-11-01 (Team Synapse vs
HellNight): Valve snapshots of the two games whose live-list names match the outcomes (match ids 9071281369 and
9071365885; radiant HellNight, dire Team Synapse). Kill events: a team's kill count rising between consecutive snapshots
(receive time), signed +1 when Synapse (token 0) gains. Decisions: 0x7d67f01d's maker bursts on the event's tokens whose top
moves >= 1c, signed in Synapse space. Lag histogram decision - event in [-60, +60] s against 1,000 circular shifts inside
the games' span; direction agreement of decisions 0-10 s after an event (and 0-10 s before) with the event's sign.
Output: results/valve_lock_a7_strict.json"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
OUT = ROOT / ".cache/re/tommy-cs2-maker"
A7 = "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"
EV = "dota2-synaps-hn-2026-11-01"
GAMES = {"9071281369", "9071365885"}
u = pd.read_parquet(OUT / "universe_t0.parquet")
u = u[u.event_slug == EV]
tok0 = set()
alltok = set()
for r in u.itertuples():
    t = json.loads(r.tokens) if isinstance(r.tokens, str) else list(r.tokens)
    outs = json.loads(r.outcomes) if isinstance(r.outcomes, str) else list(r.outcomes)
    k = 0 if "synap" in str(outs[0]).lower() else 1
    tok0.add(str(t[k]))
    alltok |= {str(x) for x in t}
snaps = []
for r in live.iter_live("tommy_dota_rt", 1793512800, 1793534400):
    if r.get("k") == "S" and str(r.get("m")) in GAMES:
        k = {int(x[0]): int(x[1]) for x in (r.get("tm") or []) if len(x) >= 2}
        snaps.append((r["t"] / 1000.0, str(r.get("m")), k.get(2, np.nan), k.get(3, np.nan)))
S = pd.DataFrame(snaps, columns=["t", "m", "k2", "k3"]).sort_values("t")
ev_t, ev_s = [], []
for m, g in S.groupby("m"):
    g = g.drop_duplicates(["k2", "k3"])
    d2, d3 = g.k2.diff().fillna(0).to_numpy(), g.k3.diff().fillna(0).to_numpy()
    for t, a, b in zip(g.t.to_numpy(), d2, d3):
        if a > 0 or b > 0:
            ev_t.append(t)
            ev_s.append(float(np.sign(b - a)))  # dire = Synapse gains -> +1
ev_t, ev_s = np.array(ev_t), np.array(ev_s)
cd = pd.read_parquet(OUT / "iter16/sfg_calldata.parquet")
c = cd[(cd.maker.str.lower() == A7) & (cd.idx >= 0) & cd.token_id.astype(str).isin(alltok) & (cd.sign_ms > 1.7e12)].drop_duplicates(["salt", "sign_ms"])
dec_t, dec_s = [], []
for tok, g in c.sort_values("sign_ms").groupby("token_id"):
    s_, p = g.sign_ms.to_numpy(float), g.price.to_numpy(float)
    i, last = 0, None
    while i < len(s_):
        j = i
        while j + 1 < len(s_) and s_[j + 1] - s_[i] <= 50:
            j += 1
        top = p[i:j + 1].max()
        if last is not None and abs(top - last) >= 0.01 - 1e-9:
            sg = np.sign(top - last) * (1 if str(tok) in tok0 else -1)
            dec_t.append(s_[i] / 1000.0)
            dec_s.append(sg)
        last = top
        i = j + 1
dec_t, dec_s = np.array(dec_t), np.array(dec_s)
lo, hi = S.t.min(), S.t.max()
k = (dec_t >= lo) & (dec_t <= hi)
dec_t, dec_s = dec_t[k], dec_s[k]
bins = np.arange(-60, 61, 2.0)


def hist(dd):
    lg = (dd[:, None] - ev_t[None, :]).ravel()
    return np.histogram(lg[(lg >= -60) & (lg < 60)], bins=bins)[0]


obs = hist(dec_t)
rng = np.random.default_rng(2271)
span = hi - lo
null = np.array([hist(lo + ((dec_t - lo + rng.uniform(60, span - 60)) % span)) for _ in range(1000)])
win = {}
for a, b in ((-10, 0), (0, 10), (-30, -10), (10, 30)):
    m = (bins[:-1] >= a) & (bins[:-1] < b)
    o_, n_ = obs[m].sum(), null[:, m].sum(1)
    win[f"{a}..{b}s"] = {"obs": int(o_), "null_mean": round(float(n_.mean()), 1), "ratio": round(float(o_ / max(n_.mean(), 1e-9)), 2), "p": round(float((n_ >= o_).mean()), 4)}
agree = {}
for nm, (a, b) in (("after_0_10s", (0, 10)), ("before_0_10s", (-10, 0))):
    vals = []
    for t, sgn in zip(dec_t, dec_s):
        d = t - ev_t
        mm = (d >= a) & (d < b) if a >= 0 else (d >= a) & (d < b)
        if mm.any():
            e = ev_s[mm][np.argmin(np.abs(d[mm]))]
            if e != 0:
                vals.append(float(sgn == e))
    agree[nm] = {"n": len(vals), "agreement": round(float(np.mean(vals)), 3) if vals else None}
out = {"games": sorted(GAMES), "snapshots": int(len(S)), "kill_events": int(len(ev_t)), "decisions": int(len(dec_t)), "windows": win,
       "direction_agreement": agree, "note": "exploratory: the same-feed gate failed (same_feed_gate.json)"}
(RES / "valve_lock_a7_strict.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
