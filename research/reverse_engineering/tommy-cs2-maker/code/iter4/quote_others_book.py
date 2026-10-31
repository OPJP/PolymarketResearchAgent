"""Iteration 4, X43 (mechanics iter3 P1): the maker quote decoded on OTHERS' book (own levels subtracted), live BUILD
data (own recorder tommy_cs2_near, server clock, 10-31 14:50-18:00 UTC, the wallet's dev-unit CS2 markets).

Own-level tracker on the token-0 book (approximate, size fingerprint): +z on an increase of z in OWN_SIZES at a whole
cent; -z on a cancel of an own size at that level; a level that shrinks below the tracked own size caps it (own volume
consumed or cancelled). Others' size at a level = book size - own size.
At every filled wallet maker order (calldata_dev, BUY token X at price q, signed at t) the book 5 ms before t gives
others' best bid on X (obb_X) and on the complement (obb_Y), plus the full-book best bid on X (bb_X, own included).
Candidate rules for q (all point-in-time on the live book; scored within one in-play tick 0.01 and exactly):
  A  q = bb_X (full book, own levels included: the old self-referenced anchor)
  B  q = obb_X (join others' best bid)
  C_K q = min(obb_X, K - obb_Y)            (pair-sum cap, shade only the side that would break the cap)
  D_K q = obb_X - max(0, obb_X + obb_Y - K) (full shade on X)
  E  q = last trade price of X (any token, mirrored) before t
with K in 0.96 / 0.97 / 0.98. Also: the share of its orders ABOVE obb_X, and its level within the burst.
Output: results/quote_others_book.json
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pull_attrib import read_feed, OUT, RES, WALLET, OWN0, END  # noqa: E402

OWN_SIZES = (100.0, 68.0, 58.0, 54.0)


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    is_t1 = {str(r.tok1) for r in dm.itertuples()}
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    mo = cd[(cd.idx >= 0) & (cd.maker == WALLET) & (cd.side == 0)].copy()
    mo["tok"] = mo.token_id.astype(str)
    mo = mo[mo.tok.isin(t0map) & (mo.sign_ms >= OWN0 * 1000 + 60000) & (mo.sign_ms < END * 1000)]
    mo = mo.drop_duplicates(["tok", "sign_ms", "price"])
    mo["a"] = mo.tok.map(t0map)
    queries = defaultdict(list)
    for r in mo.itertuples():
        queries[r.a].append((int(r.sign_ms) - 5, r.tok in is_t1, float(r.price), float(r.shares)))
    for a in queries:
        queries[a].sort()
    recs = read_feed("tommy_cs2_near", OWN0, END, set(t0map))
    recs.sort(key=lambda r: r.get("s", 0))
    lastx = {}
    out = []
    state = {}
    qi = defaultdict(int)

    def answer(a, s):
        bd, od, ob, oo = state[a]
        lq = queries[a]
        while qi[a] < len(lq) and lq[qi[a]][0] <= s:
            t, x1, q, z = lq[qi[a]]
            qi[a] += 1
            ob_lv = [p for p, v in bd.items() if v - ob.get(p, 0.0) > 1e-6]
            oa_lv = [p for p, v in od.items() if v - oo.get(p, 0.0) > 1e-6]
            obb0 = max(ob_lv) if ob_lv else np.nan          # others' best bid on token 0
            obb1 = 1 - min(oa_lv) if oa_lv else np.nan      # others' best bid on token 1 (mirrored asks)
            bb0 = max(bd) if bd else np.nan
            bb1 = 1 - min(od) if od else np.nan
            lx = lastx.get(a)
            ltp = (lx if not x1 else 1 - lx) if lx is not None else np.nan
            if x1:
                out.append({"q": q, "obb": obb1, "obb_o": obb0, "bb": bb1, "ltp": ltp, "z": z})
            else:
                out.append({"q": q, "obb": obb0, "obb_o": obb1, "bb": bb0, "ltp": ltp, "z": z})

    for r in recs:
        a = str(r.get("a"))
        if a not in t0map:
            continue
        k = r.get("k")
        if k == "x":
            p = float(r["p"])
            lastx[t0map[a]] = p if a not in is_t1 else 1 - p
            continue
        if a != t0map[a]:
            continue
        s = int(r.get("s", 0))
        if a in state:
            answer(a, s)
        if k == "f":
            bd = {float(p): float(z) for p, z in r.get("b") or []}
            od = {float(p): float(z) for p, z in r.get("o") or []}
            ob, oo = (state[a][2], state[a][3]) if a in state else ({}, {})
            for d, o in ((bd, ob), (od, oo)):
                for p in list(o):
                    o[p] = min(o[p], d.get(p, 0.0))
                    if o[p] <= 1e-9:
                        o.pop(p)
            state[a] = (bd, od, ob, oo)
        elif k == "pc" and a in state:
            bd, od, ob, oo = state[a]
            for side, p, z in r["c"]:
                p, z = float(p), float(z)
                bk, own = (bd, ob) if side == "BUY" else (od, oo)
                old = bk.get(p, 0.0)
                dz = z - old
                whole = abs(p * 100 - round(p * 100)) < 1e-6
                if dz > 1e-9 and whole and any(abs(dz - w) < 1e-6 for w in OWN_SIZES):
                    own[p] = own.get(p, 0.0) + dz
                elif dz < -1e-9 and p in own and any(abs(-dz - w) < 1e-6 for w in OWN_SIZES):
                    own[p] = max(0.0, own[p] + dz)
                if z == 0:
                    bk.pop(p, None)
                else:
                    bk[p] = z
                if p in own:
                    own[p] = min(own[p], z)
                    if own[p] <= 1e-9:
                        own.pop(p)
    X = pd.DataFrame(out).dropna(subset=["obb", "obb_o"])
    res = {"orders_scored": int(len(X)), "orders_total": int(len(mo))}

    def score(pred):
        d = np.round((X.q - pred) * 100, 6)
        ok = np.isfinite(d)
        return {"within_tick": round(float((np.abs(d[ok]) <= 1 + 1e-6).mean()), 3), "exact": round(float((np.abs(d[ok]) <= 0.1).mean()), 3), "n": int(ok.sum())}
    res["A_full_book_bid"] = score(X.bb)
    res["B_join_others_bid"] = score(X.obb)
    res["E_last_trade"] = score(X.ltp)
    for K in (0.96, 0.97, 0.98):
        res[f"C_cap_{K}"] = score(np.minimum(X.obb, K - X.obb_o))
        res[f"D_fullshade_{K}"] = score(X.obb - np.maximum(0, X.obb + X.obb_o - K))
    d = np.round((X.q - X.obb) * 100)
    res["q_minus_others_bid_cents"] = {str(int(k)): round(float(v), 3) for k, v in d.value_counts(normalize=True).sort_index().items() if abs(k) <= 6}
    res["others_bid_sum_cents"] = {str(int(k)): round(float(v), 3) for k, v in np.round((X.obb + X.obb_o) * 100).value_counts(normalize=True).sort_index().items() if 90 <= k <= 101}
    res["share_above_others_bid"] = round(float((d > 0).mean()), 3)
    json.dump(res, open(RES / "quote_others_book.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
