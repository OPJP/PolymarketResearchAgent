"""X225 step 4c: the print-clock tracker of decided_early.py with the taker regime's own sign moments as anchors
(direction = the team the moment's first order backs, which must equal the round's winner), against the reversed winner
sequence with the same freedom (G in {0, 10, 20, 30} s, window [-15, +30] s around the predicted end). Written after
step 4b (cumulative-duration fit: no clock) and before this run. Clock iff snaps >= 1.5x reversed.
Output: results/taker_moment_tracker.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
D = pd.read_parquet(OUT / "iter16/taker_map_rows.parquet")
WLO, WHI = 15.0, 30.0


def track(ct, cs, ws, dur, G, t0):
    e = np.full(len(ws), np.nan)
    sn = np.zeros(len(ws), bool)
    c0 = np.where((cs == ws[0]) & (ct >= t0 - 300) & (ct <= t0 + 2400))[0]
    if not len(c0):
        return sn
    e[0], sn[0] = ct[c0[0]], True
    for r in range(1, len(ws)):
        pred = e[r - 1] + dur[r] + G
        cand = np.where((cs == ws[r]) & (ct >= pred - WLO) & (ct <= pred + WHI) & (ct > e[r - 1] + 20))[0]
        if len(cand):
            e[r], sn[r] = ct[cand[0]], True
        else:
            e[r] = pred
    return sn


tot = rev = rounds = 0
both = 0
for r in D.itertuples():
    ct = np.array(json.loads(r.mom_ts), float)
    cs = np.array(json.loads(r.mom_dir), float)
    ws = np.array(json.loads(r.a_won), float)
    dur = np.array(json.loads(r.round_dur), float)
    if len(ct) < 5 or len(ws) < 13 or (ws == 0).any():
        continue
    o = np.argsort(ct)
    ct, cs = ct[o], cs[o]
    best = max((track(ct, cs, ws, dur, G, r.begin) for G in (0.0, 10.0, 20.0, 30.0)), key=lambda x: x.sum())
    bestr = max((track(ct, cs, ws[::-1].copy(), dur, G, r.begin) for G in (0.0, 10.0, 20.0, 30.0)), key=lambda x: x.sum())
    tot += int(best.sum())
    rev += int(bestr.sum())
    rounds += len(ws)
    both += int((best[1:] & best[:-1]).sum())
out = {"rounds": rounds, "snaps": tot, "snaps_reversed": rev, "ratio": round(tot / max(rev, 1), 3), "clock": bool(tot >= 1.5 * rev),
       "rounds_with_both_ends": both, "print_clock_reference": "maker regime print clock 1.30x (block) / 1.33x (match)"}
(RES / "taker_moment_tracker.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
