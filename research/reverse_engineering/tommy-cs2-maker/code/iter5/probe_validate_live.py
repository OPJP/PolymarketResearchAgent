"""Iteration 5, mechanics panel iter4 P2 step 2 (X56): validate the sweep-probe label against the live book.

10-31 14:50-18:00 development block, the wallet's dev-unit CS2 markets. Probes as in sweep_probes.py, from calldata_dev:
fully consumed levels of other takers' multi-level sweeps (in play), y_probe = the wallet filled at that bid-equivalent
level in the tx. Live label: the wallet's own resting level at that price just before the tx's server match time
(recorder trade message by tx hash), from the own-level tracker of band_hazard.py (fingerprint 100 / 68 / 58 / 54 at
whole cents; bids on token 0 = BUY side of the token-0 book, bids on token 1 = SELL side at 1 - p).
Reported: agreement, and the confusion table. v2: own sizes = its actual order sizes in that market; state queried at m - 150 ms. Target (panel): >= 95%.
Output: results/probe_validate_live.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OWN = (100.0, 68.0, 58.0, 54.0)
OWN0, END = 1793458232, 1793469600
QUERY_LEAD_MS = 150.0  # the book update of a match is stamped ~20 ms before its trade message: query before it


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    tok_info = {}
    for r in dm.itertuples():
        tok_info[str(r.tok0)] = (str(r.tok0), 0, float(r.gs))
        tok_info[str(r.tok1)] = (str(r.tok0), 1, float(r.gs))
    mt = {}
    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                if r.get("k") == "x" and str(r.get("a")) in tok_info and r.get("h"):
                    hh = str(r["h"]).lower()
                    mt[hh] = min(mt.get(hh, 1e18), int(r["s"]))
        except Exception as e:  # noqa: BLE001
            print("feed stopped", type(e).__name__, flush=True)
        h += 3600
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["tok"] = cd.token_id.astype(str)
    cd = cd[cd.tok.isin(tok_info)].copy()
    cd["a"] = cd.tok.map(lambda t: tok_info[t][0])
    cd["oi"] = cd.tok.map(lambda t: tok_info[t][1])
    cd["gs"] = cd.tok.map(lambda t: tok_info[t][2])
    probes = []
    for tx, g in cd.groupby("tx"):
        t = g[g.idx == -1]
        if t.empty:
            continue
        t = t.iloc[0]
        m = mt.get(str(tx).lower())
        if m is None or not (OWN0 * 1000 <= m < END * 1000) or str(t.maker).lower() == WALLET or m / 1000 < t.gs + 60:
            continue
        z = int(t.oi) if int(t.side) == 1 else 1 - int(t.oi)
        mk = g[g.idx >= 0]
        beq = np.where((mk.side == 0) & (mk.oi == z), mk.price, np.where((mk.side == 1) & (mk.oi != z), 1 - mk.price, np.nan))
        ok = np.isfinite(beq)
        if ok.sum() < 2:
            continue
        b = np.round(beq[ok], 3)
        lv = np.unique(b)[::-1]
        if len(lv) < 2:
            continue
        wb = set(np.round(beq[ok & (mk.maker.to_numpy() == WALLET)], 3))
        for p in lv[:-1]:
            # token-0 book side and price of a bid on token z at p
            side, bp = ("BUY", round(float(p), 3)) if z == 0 else ("SELL", round(1 - float(p), 3))
            probes.append((t.a, side, bp, float(m), int(p in wb)))
    P = pd.DataFrame(probes, columns=["a", "side", "bp", "m", "y_probe"]).sort_values("m")
    E = pd.read_parquet(OUT / "level_events_dev.parquet").sort_values("s")
    # fingerprint v2: the wallet's own maker order sizes in that market on this block (calldata_dev; the event size
    # schedule makes 100 / 68 / 58 / 54 incomplete), whole cents
    wsz = cd[(cd.maker == WALLET) & (cd.idx >= 0)].groupby("a").shares.apply(lambda x: set(np.round(x.to_numpy(float), 2)))
    E["own"] = [bool(w) and (round(z, 2) in wsz.get(a, set())) for a, z, w in zip(E.a, E["size"], E.whole)]
    live_y = []
    for (a, side), pg in P.groupby(["a", "side"]):
        g = E[(E.a == a) & (E.side == side)]
        s_arr = g.s.to_numpy(float); p_arr = g.p.to_numpy(float); z_arr = g.z.to_numpy(float); d_arr = g.d.to_numpy(float)
        k_arr = g.kind.to_numpy(); o_arr = g.own.to_numpy()
        lvl = {}
        own = defaultdict(float)
        i = 0
        for r in pg.sort_values("m").itertuples():
            while i < len(g) and s_arr[i] < r.m - QUERY_LEAD_MS:
                p, z, d, k, o = p_arr[i], z_arr[i], d_arr[i], k_arr[i], o_arr[i]
                lvl[p] = z
                if z <= 1e-9:
                    lvl.pop(p, None)
                if k == "add" and o:
                    own[p] += abs(d)
                elif k == "cancel" and o:
                    own[p] = max(0.0, own[p] - abs(d))
                if p in own:
                    own[p] = min(own[p], lvl.get(p, 0.0))
                i += 1
            key = min(own.keys(), key=lambda q: abs(q - r.bp)) if own else None
            pres = int(key is not None and abs(key - r.bp) < 0.0005 and own[key] > 0.5)
            live_y.append((r.Index, pres))
    L = dict(live_y)
    P["y_live"] = P.index.map(L)
    P = P[P.y_live.notna()]
    agree = float((P.y_probe == P.y_live).mean()) if len(P) else None
    res = {"probes": int(len(P)), "agreement": round(agree, 4) if agree is not None else None,
           "confusion": {f"probe{a}_live{b}": int(((P.y_probe == a) & (P.y_live == b)).sum()) for a in (0, 1) for b in (0, 1)},
           "base_rate_probe": round(float(P.y_probe.mean()), 3) if len(P) else None}
    (RES / "probe_validate_live.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
