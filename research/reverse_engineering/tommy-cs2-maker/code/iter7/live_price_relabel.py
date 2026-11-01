"""Iteration 7, X92 step 3 (mechanics panel iter6 P1): re-run the frozen live join rule (final_rule._live_price) on
BUILD-live with the own-level label replaced, on the same filled maker orders of the wallet.

Own-level trackers run in parallel on one pass over tommy_cs2_near (server clock, 10-31 14:50-18:00 UTC, the wallet's
dev-unit CS2 token-0 books):
  frozen : whole-cent changes whose size is one of its maker sizes in that market (+100)   [iteration-6 rule]
  valid  : adds only if validated own by features unfilled orders also have (label_validate.py: member of an equal-size
           multi-level burst within 5 ms, or an odd in-market size != 100); decreases as in frozen
  none   : nothing removed (full-book best bid, i.e. own state included)
For each wallet maker order (calldata, one per order) the rule reads the book at sign_ms - 100 ms:
  J = best bid on the order's token among levels with (size - own) > 0.5;  JC = min(J, 0.99 - own top on the other token).
Score: share within one tick (0.01 inside [0.04, 0.96]) and exact, plus the last trade.
Output: results/live_price_relabel.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OWN0, END = 1793458232, 1793469600
VIEW, CAP = 100.0, 0.99


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    tok = {r.cid: (str(r.tok0), str(r.tok1)) for r in dm.itertuples()}
    t0map = {v[0]: v[0] for v in tok.values()}
    t0map.update({v[1]: v[0] for v in tok.values()})
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["tok"] = cd.token_id.astype(str)
    mo = cd[(cd.idx >= 0) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)].drop_duplicates("salt")
    mo = mo[(mo.sign_ms >= OWN0 * 1000) & (mo.sign_ms < END * 1000)]
    sizes = {}
    for r in mo.itertuples():
        sizes.setdefault(t0map[r.tok], set()).add(round(float(r.shares), 2))
    sizes = {a: v | {100.0} for a, v in sizes.items()}
    LA = pd.read_parquet(OUT / "linked_adds_dev.parquet")
    LA["valid"] = LA.F_mkt & (LA.in_burst | (LA["size"] != 100))
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in LA[LA.valid].itertuples()}
    q = {}
    for r in mo.itertuples():
        a = t0map[r.tok]
        q.setdefault(a, []).append((float(r.sign_ms) - VIEW, 0 if r.tok == a else 1, round(float(r.price), 3)))
    for a in q:
        q[a].sort()
    trackers = ("frozen", "valid", "none")
    st = {}
    qi = {a: 0 for a in q}
    last_trade = {}
    rows = []

    def answer(a, upto):
        b, o, own = st[a]
        qa = q[a]
        while qi[a] < len(qa) and qa[qi[a]][0] < upto:
            t, oi, price = qa[qi[a]]
            qi[a] += 1
            rec = {"p": price, "oi": oi}
            lt = last_trade.get(a)
            rec["lt"] = None if lt is None else (lt if oi == 0 else 1 - lt)
            for tr in trackers:
                ob, oo = own[tr]
                if oi == 0:
                    oth = [p for p, z in b.items() if z - ob.get(p, 0.0) > 0.5]
                    J = max(oth) if oth else None
                    oo_l = [p for p, z in oo.items() if z > 0.5]
                    other_top = (1 - min(oo_l)) if oo_l else None
                else:
                    oth = [p for p, z in o.items() if z - oo.get(p, 0.0) > 0.5]
                    J = (1 - min(oth)) if oth else None
                    ob_l = [p for p, z in ob.items() if z > 0.5]
                    other_top = max(ob_l) if ob_l else None
                rec["J_" + tr] = None if J is None else round(J, 3)
                rec["JC_" + tr] = None if J is None else round(min(J, CAP - other_top) if other_top is not None else J, 3)
            rows.append(rec)

    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                a = r.get("a")
                if a not in q or "s" not in r:
                    continue
                s = float(r["s"])
                if a in st:
                    answer(a, s)
                k = r.get("k")
                if k == "x":
                    try:
                        last_trade[a] = float(r.get("p"))
                    except Exception:  # noqa: BLE001
                        pass
                    continue
                own_sz = sizes.get(a, {100.0})
                if k in ("q", "f"):
                    b = {float(p): float(z) for p, z in (r.get("b") or [])}
                    o = {float(p): float(z) for p, z in (r.get("o") or [])}
                    own = {}
                    for tr in trackers:
                        if a in st:
                            pb, po = st[a][2][tr]
                            own[tr] = ({p: min(v, b.get(p, 0.0)) for p, v in pb.items()},
                                       {p: min(v, o.get(p, 0.0)) for p, v in po.items()})
                        else:
                            own[tr] = ({}, {})
                    st[a] = (b, o, own)
                elif k == "pc" and a in st:
                    b, o, own = st[a]
                    for sd, p, z in r.get("c") or []:
                        p, z = float(p), float(z)
                        book = b if sd == "BUY" else o
                        d = z - book.get(p, 0.0)
                        whole = abs(p * 100 - round(p * 100)) < 1e-6
                        fz = whole and round(abs(d), 2) in own_sz
                        for tr in ("frozen", "valid"):
                            ow = own[tr][0] if sd == "BUY" else own[tr][1]
                            if d > 0:
                                ok = fz if tr == "frozen" else ((a, sd, round(p, 3), int(s)) in vset)
                                if ok:
                                    ow[p] = ow.get(p, 0.0) + d
                            elif fz:
                                ow[p] = max(0.0, ow.get(p, 0.0) + d)
                        if z == 0:
                            book.pop(p, None)
                        else:
                            book[p] = z
                        for tr in ("frozen", "valid"):
                            ow = own[tr][0] if sd == "BUY" else own[tr][1]
                            if p in ow:
                                ow[p] = min(ow[p], book.get(p, 0.0))
        except Exception as e:  # noqa: BLE001
            print("feed", type(e).__name__, flush=True)
        h += 3600
    for a in q:
        if a in st:
            answer(a, 1e18)
    R = pd.DataFrame(rows)

    def wt(col):
        ok = R[col].notna()
        x, pp = R.loc[ok, "p"].to_numpy(float), R.loc[ok, col].to_numpy(float)
        tick = np.where((pp >= 0.04) & (pp <= 0.96), 0.01, 0.001)
        return {"n": int(ok.sum()), "within_tick": round(float((np.abs(x - pp) <= tick + 1e-9).mean()), 3),
                "exact": round(float((np.abs(x - pp) <= 1e-4).mean()), 3)}

    res = {"n_orders": int(len(R)), "label_valid_rule": "F_mkt & (in_burst | size != 100)"}
    for c in [c for c in R.columns if c.startswith("J")] + ["lt"]:
        res[c] = wt(c)
    (RES / "live_price_relabel.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
