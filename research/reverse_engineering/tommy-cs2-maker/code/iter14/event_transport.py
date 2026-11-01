"""X198 (mechanics panel iter-13 P5): the examinable historical price rule built from own state, with one event value
transported across the complement and the map / match books, and the slot-shifted prediction.

Orders: the wallet's filled maker orders (orders.parquet, B1 calldata; CS2 and Dota). For each target order signed at
t, the information set is the wallet's OWN earlier filled orders in the same event whose first fill's block time is
< t (public on chain by then; own state). Bursts: own orders on one token chained within 50 ms; burst top = max price.

Rules (team-A space for transport; K and BETA fitted on BUILD only):
  P_tok   price of the latest own order on the same token (per-token persistence, iteration 10's 0.50);
  T_tok   latest own burst top on the same token, minus SHIFT (0 or 1c);
  T_book  freshest own burst top on either token of the same book, the complement mapped by K - top, minus SHIFT;
  T_event T_book, but if the freshest own burst in the event is on the other book (map <-> match) and is newer than
          the same book's, add BETA x (its change since the same book's latest top) (map -> match) or 1 / BETA x
          (match -> map) to the same book's value.
K = BUILD median of (own top on token 0 + own top on token 1) over pairs of bursts on the two tokens of one book within
2 s; BETA = BUILD no-intercept slope of the match-book top change on the map-book top change over consecutive own
bursts (same event, both books re-priced within 5 s).
Score: within one tick (|pred - price| <= 1c) on VALIDATE (sign time 10-21..10-23) and BUILD, overall, for the first
order of a burst (a V change) and for later orders, and by title. Output: results/event_transport.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SPLIT = 1792540800
TICK = 0.0101
import os
MODE = os.environ.get("TRANSPORT_AVAIL", "block")  # block: own fills public at block time; sign: own knowledge at signing


def main():
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "price", "cid", "oi", "event", "smt", "role", "first_fill_ts", "token_id"])
    o = o[(o.role == "maker") & o.event.notna()].sort_values(["event", "sign_ms"]).reset_index(drop=True)
    o["book"] = np.where(o.smt == "moneyline", "match", "map")
    o["title"] = np.where(o.event.str.startswith("dota2"), "dota2", "cs2")
    # bursts per token
    o = o.sort_values(["token_id", "sign_ms"]).reset_index(drop=True)
    o["burst"] = (o.groupby("token_id").sign_ms.diff().fillna(1e12) > 50).cumsum()
    bt = o.groupby("burst").agg(top=("price", "max"), t0=("sign_ms", "min"), avail=("first_fill_ts", "max"))
    o["btop"] = o.burst.map(bt.top)
    o["bt0"] = o.burst.map(bt.t0)
    o["first_in_burst"] = o.sign_ms == o.bt0
    o = o.sort_values(["event", "sign_ms"]).reset_index(drop=True)
    o["A"] = np.where(o.oi == 0, o.btop, np.nan)  # filled later with K
    # --- fit K and BETA on BUILD
    b = o[o.sign_ms / 1000 < SPLIT]
    ks = []
    for cid, g in b.groupby("cid"):
        g0 = g[g.oi == 0].drop_duplicates("burst")
        g1 = g[g.oi == 1].drop_duplicates("burst")
        if len(g0) == 0 or len(g1) == 0:
            continue
        t1 = g1.bt0.to_numpy()
        for t, top in zip(g0.bt0, g0.btop):
            j = np.searchsorted(t1, t)
            for jj in (j - 1, j):
                if 0 <= jj < len(t1) and abs(t1[jj] - t) <= 2000:
                    ks.append(top + g1.btop.iloc[jj])
                    break
    K = float(np.median(ks)) if ks else 0.98
    o["A"] = np.where(o.oi == 0, o.btop, K - o.btop)  # own burst top in team-A space (token-0 top scale)
    # BETA: consecutive own bursts on map then match (or match then map) within 5 s, top changes in A space
    pairs = []
    for ev, g in b.groupby("event"):
        g = g.drop_duplicates("burst").sort_values("bt0")
        last = {}
        for r in g.itertuples():
            key = (r.book, r.cid)
            prev = last.get(key)
            last[key] = (r.bt0, r.A)
        # simpler: per pair of books, match change vs map change between successive co-repricings
    # co-repricing pairs: for each match burst, the nearest map burst within 5 s (any map book of the event); changes
    # between successive such pairs
    for ev, g in b.groupby("event"):
        g = g.drop_duplicates("burst").sort_values("bt0")
        mt = g[g.book == "match"]
        mp = g[g.book == "map"]
        if len(mt) < 3 or len(mp) < 3:
            continue
        tm = mp.bt0.to_numpy()
        prev = None
        for r in mt.itertuples():
            j = np.searchsorted(tm, r.bt0)
            best = None
            for jj in (j - 1, j):
                if 0 <= jj < len(tm) and abs(tm[jj] - r.bt0) <= 5000:
                    best = jj if best is None or abs(tm[jj] - r.bt0) < abs(tm[best] - r.bt0) else best
            if best is None:
                continue
            cur = (r.A, mp.A.iloc[best], mp.cid.iloc[best])
            if prev is not None and prev[2] == cur[2] and abs(cur[1] - prev[1]) >= 0.005:
                pairs.append((cur[0] - prev[0], cur[1] - prev[1]))
            prev = cur
    pr = np.array(pairs) if pairs else np.zeros((0, 2))
    pr = pr[np.isfinite(pr).all(axis=1)] if len(pr) else pr
    BETA = float((pr[:, 0] * pr[:, 1]).sum() / (pr[:, 1] ** 2).sum()) if len(pr) else 0.5
    # --- predictions
    preds = {k: np.full(len(o), np.nan) for k in ("P_tok", "T_tok0", "T_tok1", "T_book0", "T_book1", "T_event1", "T_event0")}
    for ev, g in o.groupby("event"):
        idx = g.index.to_numpy()
        t = g.sign_ms.to_numpy() / 1000
        av = g.first_fill_ts.to_numpy() if MODE == "block" else g.sign_ms.to_numpy() / 1000 + 0.001
        toks = g.token_id.to_numpy()
        cids = g.cid.to_numpy()
        books = g.book.to_numpy()
        A = g.A.to_numpy()
        pz = g.price.to_numpy()
        btop = g.btop.to_numpy()
        oi = g.oi.to_numpy()
        bt0 = g.bt0.to_numpy() / 1000
        order_av = np.argsort(av, kind="mergesort")
        for i in range(len(g)):
            # own orders whose fill was public before t_i, and signed before t_i
            m = (av < t[i]) & (np.arange(len(g)) != i) & (bt0 < t[i])
            if not m.any():
                continue
            js = np.where(m)[0]
            same_tok = js[toks[js] == toks[i]]
            if len(same_tok):
                j = same_tok[np.argmax(bt0[same_tok] * 1e3 + np.arange(len(same_tok)) * 1e-6)]
                preds["P_tok"][idx[i]] = pz[same_tok[np.argmax(t[same_tok])]]
                preds["T_tok0"][idx[i]] = btop[j]
                preds["T_tok1"][idx[i]] = btop[j] - 0.01
            same_book = js[cids[js] == cids[i]]
            vb = None
            if len(same_book):
                j = same_book[np.argmax(bt0[same_book])]
                vA = A[j]
                vb = (bt0[j], vA)
                v = vA if oi[i] == 0 else K - vA
                preds["T_book0"][idx[i]] = v
                preds["T_book1"][idx[i]] = v - 0.01
            other = js[(books[js] != books[i])]
            if vb is not None and len(other):
                j = other[np.argmax(bt0[other])]
                if bt0[j] > vb[0]:
                    # change of the other book's A value since the same book's latest top
                    prior = other[bt0[other] <= vb[0]]
                    prior = prior[cids[prior] == cids[j]]
                    if len(prior):
                        k0 = prior[np.argmax(bt0[prior])]
                        d = A[j] - A[k0]
                        f = BETA if books[i] == "match" else (1 / BETA if BETA > 0.05 else 0)
                        vA = vb[1] + f * d
                        v = vA if oi[i] == 0 else K - vA
                        preds["T_event0"][idx[i]] = round(v, 2)
                        preds["T_event1"][idx[i]] = round(v, 2) - 0.01
                        continue
            if vb is not None:
                preds["T_event0"][idx[i]] = preds["T_book0"][idx[i]]
                preds["T_event1"][idx[i]] = preds["T_book1"][idx[i]]
    for k, v in preds.items():
        o[k] = np.round(v, 2)
    out = {"K_build": round(K, 4), "K_pairs": len(ks), "BETA_build": round(BETA, 3), "BETA_pairs": int(len(pr))}
    o["period"] = np.where(o.sign_ms / 1000 < SPLIT, "BUILD", "VALIDATE")
    for per in ("BUILD", "VALIDATE"):
        d = o[o.period == per]
        res = {"orders": int(len(d))}
        for k in preds:
            ok = np.isfinite(d[k])
            hit = (np.abs(d[k] - d.price) <= TICK) & ok
            res[k] = {"coverage": round(float(ok.mean()), 3), "within_tick_all": round(float(hit.mean()), 3),
                      "within_tick_covered": round(float(hit[ok].mean()), 3) if ok.any() else None,
                      "first_in_burst": round(float(hit[d.first_in_burst].mean()), 3),
                      "later_in_burst": round(float(hit[~d.first_in_burst].mean()), 3),
                      "cs2": round(float(hit[d.title == "cs2"].mean()), 3), "dota2": round(float(hit[d.title == "dota2"].mean()), 3) if (d.title == "dota2").any() else None,
                      "match_book": round(float(hit[d.book == "match"].mean()), 3), "map_book": round(float(hit[d.book == "map"].mean()), 3)}
        res["share_first_in_burst"] = round(float(d.first_in_burst.mean()), 3)
        out[per] = res
    # event bootstrap of T_event1 - P_tok on VALIDATE
    v = o[o.period == "VALIDATE"].copy()
    v["h_e"] = (np.abs(v.T_event1 - v.price) <= TICK) & np.isfinite(v.T_event1)
    v["h_p"] = (np.abs(v.P_tok - v.price) <= TICK) & np.isfinite(v.P_tok)
    v["h_b"] = (np.abs(v.T_book1 - v.price) <= TICK) & np.isfinite(v.T_book1)
    ge = v.groupby("event").agg(e=("h_e", "sum"), p=("h_p", "sum"), b=("h_b", "sum"), n=("h_e", "size"))
    rng = np.random.default_rng(0)
    g1, g2 = [], []
    for _ in range(2000):
        w = rng.dirichlet(np.ones(len(ge)))
        n = (w * ge.n).sum()
        g1.append(((w * ge.e).sum() - (w * ge.p).sum()) / n)
        g2.append(((w * ge.b).sum() - (w * ge.p).sum()) / n)
    out["VALIDATE_gain_T_event1_over_P_tok"] = [round(float(np.quantile(g1, q)), 4) for q in (0.025, 0.5, 0.975)]
    out["VALIDATE_gain_T_book1_over_P_tok"] = [round(float(np.quantile(g2, q)), 4) for q in (0.025, 0.5, 0.975)]
    out["avail_mode"] = MODE
    (RES / f"event_transport_{MODE}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
