"""X175 (information panel iter-12 P4), BUILD-live: what public change precedes each event-wide withdrawal start, and
does it differ from what precedes its other triggered pulls? For the 64 withdrawal episodes (iter12/withdrawal_episodes)
and for every triggered own pull burst NOT within 100 ms of an episode start: the latest non-own level event (own
levels within 3 ms of an own burst removed) on ANY book of the event within 40 ms before; its kind (cancel / add /
cons = trade), its size class (5, 10, 20, 30-49, 50-100 whole, other), same token or not. Also the number of distinct
non-own changes on the event's books in the 40 ms before (cluster size), against the same at shifted times.
Output: results/withdrawal_triggers.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def sclass(x):
    if not np.isfinite(x):
        return "na"
    if abs(x - 5) < 0.5:
        return "5"
    if abs(x - 10) < 0.5:
        return "10"
    if abs(x - 20) < 0.5:
        return "20"
    if 30 <= x < 50:
        return "30-49"
    if 50 <= x <= 100 and abs(x - round(x)) < 1e-6:
        return "50-100w"
    return "other"


def main():
    ep = pd.read_parquet(OUT / "iter12/withdrawal_episodes.parquet")
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    ev_tok = {}
    for r in dm.itertuples():
        ev_tok.setdefault(r.event, set()).update({str(r.tok0), str(r.tok1)})
    tok_ev = {t: e for e, ts in ev_tok.items() for t in ts}
    ob = pd.read_parquet(OUT / "own_bursts_dev.parquet")
    ob["a"] = ob.a.astype(str)
    ob["event"] = ob.a.map(tok_ev)
    le = pd.read_parquet(OUT / "level_events_dev.parquet", columns=["a", "s", "kind", "size", "side"])
    le["a"] = le.a.astype(str)
    le["event"] = le.a.map(tok_ev)
    own_t = np.sort(ob.s.to_numpy(float))
    s = le.s.to_numpy(float)
    j = np.searchsorted(own_t, s)
    d = np.minimum(np.abs(s - own_t[np.clip(j - 1, 0, len(own_t) - 1)]), np.abs(s - own_t[np.clip(j, 0, len(own_t) - 1)]))
    oth = le[d > 3]
    byev = {e: g.sort_values("s") for e, g in oth.groupby("event")}

    def attrib(ev, t, own_tok=None):
        g = byev.get(ev)
        if g is None:
            return None
        ss = g.s.to_numpy(float)
        i1 = np.searchsorted(ss, t, side="left")
        i0 = np.searchsorted(ss, t - 40, side="left")
        if i1 <= i0:
            return {"has": False, "n40": 0}
        last = g.iloc[i1 - 1]
        return {"has": True, "n40": int(i1 - i0), "kind": last.kind, "size": sclass(float(last["size"])),
                "same_token": bool(own_tok is not None and last.a == own_tok), "lag": float(t - last.s)}
    starts = []
    for r in ep.itertuples():
        x = attrib(r.event, r.start)
        if x is not None:
            starts.append(x)
    ep_starts = np.sort(ep.start.to_numpy(float))
    tp = ob[(ob.kind == "pull") & ob.triggered.astype(bool)]
    k = np.searchsorted(ep_starts, tp.s.to_numpy(float))
    dd = np.minimum(np.abs(tp.s.to_numpy(float) - ep_starts[np.clip(k - 1, 0, len(ep_starts) - 1)]),
                    np.abs(tp.s.to_numpy(float) - ep_starts[np.clip(k, 0, len(ep_starts) - 1)]))
    tp = tp[dd > 100]
    pulls = [x for x in (attrib(r.event, r.s, r.a) for r in tp.itertuples()) if x is not None]
    rng = np.random.default_rng(5)
    shifted = []
    for r in ep.itertuples():
        for _ in range(10):
            x = attrib(r.event, r.start + rng.choice([-1, 1]) * rng.uniform(3000, 30000))
            if x is not None:
                shifted.append(x)

    def summ(L):
        D = pd.DataFrame(L)
        if not len(D):
            return {}
        H = D[D.has]
        return {"n": int(len(D)), "share_with_change_40ms": round(float(D.has.mean()), 3), "mean_changes_40ms": round(float(D.n40.mean()), 2),
                "kind": {k2: round(float(v), 3) for k2, v in H.kind.value_counts(normalize=True).items()} if len(H) else {},
                "size_class": {k2: round(float(v), 3) for k2, v in H["size"].value_counts(normalize=True).items()} if len(H) else {},
                "lag_ms_median": round(float(H.lag.median()), 1) if len(H) else None}
    out = {"withdrawal_starts": summ(starts), "other_triggered_pulls": summ(pulls), "shifted_starts": summ(shifted)}
    (RES / "withdrawal_triggers.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
