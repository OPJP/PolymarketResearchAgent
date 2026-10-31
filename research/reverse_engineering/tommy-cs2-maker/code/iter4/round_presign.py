"""Iteration 4, X47 (assumptions iter3 P1b): does any ROUND-market book of the same event move before the wallet's
taker signing? Server clock (record field s) only.

Data: own recorder feed tommy_cs2_rounds (round handicap / round totals / map handicap / total maps books of non-GRID
dev-unit events, from 17:36 UTC 10-31), the wallet's taker orders from calldata_dev (idx -1, BUY, signing ms), the
match / map books of tommy_cs2_near for the same takes (comparison), dev-unit markets only (dev_markets.parquet).
For each take: near-touch book change records (pc) in the event's round markets in [s - W, s) for W = 100, 200, 500,
1000 ms, and level DECREASES (cancels or consumption) among them; the same in the match / map books; control = random
times inside the same event's recorded span (2,000 draws, same windows). Output: results/round_presign.json
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
KEY = "tommy-cs2-maker"
R0 = 1793468189  # round recorder start
WS = (100, 200, 500, 1000)


def read_feed(feed, start, end):
    out = []
    h = int(start // 3600 * 3600)
    while h < end:
        try:
            for r in live.iter_live(feed, max(h, start), min(h + 3600, end)):
                out.append(r)
        except Exception as e:  # noqa: BLE001
            print(feed, "stopped", type(e).__name__, flush=True)
        h += 3600
    return out


def ev_of(slug):
    s = str(slug)
    for cut in ("-game", "-map-handicap", "-total-games"):
        if cut in s:
            s = s.split(cut)[0]
    return s


def main():
    end = min(time.time(), sealed.block_bounds(R0)[1])
    rr = read_feed("tommy_cs2_rounds", R0, end)
    subs = [r for r in rr if r.get("k") == "sub"]
    tok_ev = {}
    for s in subs:
        for cid, v in s["m"].items():
            if not sealed.is_sealed(int(v[2]), KEY):
                tok_ev[str(v[0])] = ev_of(v[3])
    rch = defaultdict(list)  # event -> list of (s, is_decrease)
    last = {}
    for r in rr:
        if r.get("k") == "f":
            a = r["a"]
            last[a] = ({float(p): float(z) for p, z in r.get("b") or []}, {float(p): float(z) for p, z in r.get("o") or []})
        elif r.get("k") == "pc" and r.get("a") in tok_ev:
            a = r["a"]
            bd, od = last.setdefault(a, ({}, {}))
            for side, p, z in r["c"]:
                book = bd if side == "BUY" else od
                dec = float(z) < book.get(float(p), 0.0) - 1e-9
                if float(z) == 0:
                    book.pop(float(p), None)
                else:
                    book[float(p)] = float(z)
                rch[tok_ev[a]].append((int(r["s"]), dec))
    for k in rch:
        rch[k].sort()
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    tok_mev = {}
    for r in dm.itertuples():
        tok_mev[str(r.tok0)] = ev_of(r.slug)
        tok_mev[str(r.tok1)] = ev_of(r.slug)
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    tk = cd[(cd.idx == -1) & (cd.maker == WALLET) & (cd.side == 0)].drop_duplicates("tx").copy()
    tk["ev"] = tk.token_id.astype(str).map(tok_mev)
    tk = tk[tk.ev.notna() & (tk.sign_ms >= R0 * 1000) & (tk.sign_ms < end * 1000)]
    # match / map books for the same takes
    nr = read_feed("tommy_cs2_near", R0, end)
    mch = defaultdict(list)
    lastm = {}
    for r in nr:
        a = str(r.get("a"))
        if a not in tok_mev:
            continue
        if r.get("k") == "f":
            lastm[a] = ({float(p): float(z) for p, z in r.get("b") or []}, {float(p): float(z) for p, z in r.get("o") or []})
        elif r.get("k") == "pc":
            bd, od = lastm.setdefault(a, ({}, {}))
            for side, p, z in r["c"]:
                book = bd if side == "BUY" else od
                dec = float(z) < book.get(float(p), 0.0) - 1e-9
                if float(z) == 0:
                    book.pop(float(p), None)
                else:
                    book[float(p)] = float(z)
                mch[tok_mev[a]].append((int(r["s"]), dec))
    for k in mch:
        mch[k].sort()
    rng = np.random.default_rng(3)

    def rates(ch, ev, times):
        arr = ch.get(ev) or []
        if not arr:
            return None
        s = np.array([x[0] for x in arr], float)
        d = np.array([x[1] for x in arr], bool)
        sd = s[d]
        o = {}
        for w in WS:
            a1 = np.searchsorted(s, times - w, side="left")
            b1 = np.searchsorted(s, times, side="left")
            a2 = np.searchsorted(sd, times - w, side="left")
            b2 = np.searchsorted(sd, times, side="left")
            o[w] = ((b1 > a1).astype(float), (b2 > a2).astype(float))
        return o, (s.min(), s.max())

    res = {"window_utc": [time.strftime("%H:%M:%S", time.gmtime(R0)), time.strftime("%H:%M:%S", time.gmtime(end))],
           "round_markets_subscribed": len(tok_ev), "round_events": sorted(set(tok_ev.values())),
           "wallet_takes_in_window": int(len(tk)), "takes_by_event": tk.ev.value_counts().to_dict(), "by_source": {}}
    for lab, ch in (("round_markets", rch), ("match_map_markets", mch)):
        agg = defaultdict(lambda: {"take_any": [], "take_dec": [], "rnd_any": [], "rnd_dec": []})
        n_cov = 0
        for ev, g in tk.groupby("ev"):
            rt = rates(ch, ev, g.sign_ms.to_numpy(float))
            if rt is None:
                continue
            o, (lo, hi) = rt
            n_cov += len(g)
            ctrl = rng.uniform(max(lo, g.sign_ms.min() - 600000), min(hi, g.sign_ms.max() + 600000), 2000)
            oc, _ = rates(ch, ev, ctrl)
            for w in WS:
                agg[w]["take_any"] += list(o[w][0]); agg[w]["take_dec"] += list(o[w][1])
                agg[w]["rnd_any"] += list(oc[w][0]); agg[w]["rnd_dec"] += list(oc[w][1])
        res["by_source"][lab] = {"takes_covered": n_cov, **{f"last_{w}ms": {k: round(float(np.mean(v)), 3) if v else None for k, v in agg[w].items()} for w in WS}}
    json.dump(res, open(RES / "round_presign.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
