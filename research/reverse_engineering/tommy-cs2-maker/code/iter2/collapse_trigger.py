"""Public trigger candidate (A7 strong form): a collapse of the near-touch depth on one side of the book, without
trades, followed within a second by the wallet's (and the pack's) taker BUY of the team whose asks vanished.

Event rule (point-in-time on the public book, token-0 snapshots of clob_wallets, development block 10-31 12-18 UTC):
  D(t) = size within 3c of the best level on a side; ref(t) = max D over snapshots in [t - 1.5 s, t - 0.4 s];
  collapse at t if D(t) <= FRAC * ref(t), ref(t) >= MIN_REF shares, and no public trade on the token in [t - 1.5 s, t];
  ask-side collapse of token 0 -> team 0; bid-side collapse of token 0 (= team-1 asks) -> team 1; one event per
  (market, team) per 3 s.
Scores: recall = share of the wallet's taker orders with an event on the same team in [sign - 2 s, sign];
precision = share of events followed by a wallet taker order on that team within 2 s; the same for the pack and for
other takers; event rate per market-hour. Grid over FRAC (0.3, 0.5) and MIN_REF (200, 500)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from dev_books import BLOCK0, OUT, RES, WALLET  # noqa: E402
from dev_book_trigger import PACK  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import live  # noqa: E402


def near(L, side, w=0.03):
    if not L:
        return 0.0
    if side == "o":
        best = min(p for p, z in L)
        return sum(z for p, z in L if p <= best + w + 1e-9)
    best = max(p for p, z in L)
    return sum(z for p, z in L if p >= best - w - 1e-9)


def load(end):
    a = pd.read_parquet(OUT / "activity_devblocks.parquet")
    cids = sorted(a.conditionId.unique())
    mk, _ = PolymarketData().markets_by_condition(cids)
    tok = {}
    for cid, x in mk.items():
        t = x["clobTokenIds"]
        t = json.loads(t) if isinstance(t, str) else t
        tok[str(t[0])] = (cid, 0, str(t[0]))
        tok[str(t[1])] = (cid, 1, str(t[0]))
    tok0 = {v[2] for v in tok.values()}
    recs, trades = [], []
    h = BLOCK0
    while h < end:
        try:
            for r in live.iter_live("clob_wallets", h, min(h + 3600, end)):
                if r.get("a") in tok0:
                    if r.get("k") in ("q", "f"):
                        recs.append((r["t"], r["a"], near([(float(p), float(z)) for p, z in (r.get("b") or [])], "b"),
                                     near([(float(p), float(z)) for p, z in (r.get("o") or [])], "o")))
                    elif r.get("k") == "x":
                        trades.append((r["t"], r["a"]))
        except Exception as e:  # noqa: BLE001
            print("hour stopped", type(e).__name__)
        h += 3600
    return tok, pd.DataFrame(recs, columns=["t", "a", "Db", "Do"]).sort_values("t"), pd.DataFrame(trades, columns=["t", "a"]).sort_values("t")


def events(bk, tr, frac, min_ref):
    out = []
    for a, b in bk.groupby("a"):
        tt = b.t.to_numpy()
        trt = tr[tr.a == a].t.to_numpy()
        for col, team in (("Do", 0), ("Db", 1)):
            D = b[col].to_numpy()
            last = -1e18
            for i in range(len(tt)):
                lo, hi = np.searchsorted(tt, tt[i] - 1500), np.searchsorted(tt, tt[i] - 400, side="right")
                if hi <= lo:
                    continue
                ref = D[lo:hi].max()
                if ref < min_ref or D[i] > frac * ref:
                    continue
                k = np.searchsorted(trt, tt[i] - 1500)
                if k < len(trt) and trt[k] <= tt[i]:
                    continue
                if tt[i] - last < 3000:
                    continue
                last = tt[i]
                out.append((a, team, tt[i]))
    return pd.DataFrame(out, columns=["a", "team", "t"])


def main():
    end = min(time.time() - 60, BLOCK0 + 6 * 3600)
    tok, bk, tr = load(end)
    d = pd.read_parquet(OUT / "calldata_dev.parquet")
    d = d[(d.idx == -1) & (d.sign_ms > 1.79e12) & (d.sign_ms < 1.8e12) & d.token_id.astype(str).isin(tok)].copy()
    d["a"] = d.token_id.astype(str).map(lambda t: tok[t][2])
    d["team"] = [(tok[str(t)][1] if s == 0 else 1 - tok[str(t)][1]) for t, s in zip(d.token_id, d.side)]
    d["grp"] = np.where(d.maker == WALLET, "W", np.where(d.maker.isin(PACK), "pack", "other"))
    span = bk.groupby("a").t.agg(["min", "max"])
    d = d[d.a.isin(span.index)]
    d = d[(d.sign_ms >= d.a.map(span["min"]) + 2000) & (d.sign_ms <= d.a.map(span["max"]))]
    hours = float(((span["max"] - span["min"]) / 3.6e6).sum())
    res = {"market_hours_with_book": round(hours, 2), "orders": d.grp.value_counts().to_dict()}
    grid = []
    for frac in (0.3, 0.5):
        for min_ref in (200, 500):
            ev = events(bk, tr, frac, min_ref)
            r = {"frac": frac, "min_ref": min_ref, "events": len(ev), "events_per_market_hour": round(len(ev) / max(hours, 1e-9), 1)}
            for g in ("W", "pack", "other"):
                o = d[d.grp == g]
                if len(o) == 0:
                    continue
                hit = []
                for a, team, s in zip(o.a, o.team, o.sign_ms):
                    e = ev[(ev.a == a) & (ev.team == team)].t.to_numpy()
                    hit.append(bool(((e >= s - 2000) & (e <= s)).any()))
                r[f"recall_{g}"] = round(float(np.mean(hit)), 3)
                # precision: events followed by an order of group g on the same team within 2 s
                fol = []
                for a, team, t in zip(ev.a, ev.team, ev.t):
                    s = o[(o.a == a) & (o.team == team)].sign_ms.to_numpy()
                    fol.append(bool(((s >= t) & (s <= t + 2000)).any()))
                r[f"precision_{g}"] = round(float(np.mean(fol)), 3) if fol else None
            # wrong-team check for W: events on the OTHER team before W orders
            o = d[d.grp == "W"]
            wrong = []
            for a, team, s in zip(o.a, o.team, o.sign_ms):
                e = ev[(ev.a == a) & (ev.team != team)].t.to_numpy()
                wrong.append(bool(((e >= s - 2000) & (e <= s)).any()))
            r["W_other_team_event_share"] = round(float(np.mean(wrong)), 3) if wrong else None
            grid.append(r)
    res["grid"] = grid
    json.dump(res, open(RES / "results/collapse_trigger.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
