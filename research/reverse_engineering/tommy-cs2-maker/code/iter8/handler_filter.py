"""Iteration 8, X109 (mechanics panel iter7 P3): handler identity, then the take filter conditional on a receipt.
BUILD-live (10-31 14:50-18:00; the 7 recorded token-0 books; server clock).

(1) Handler identity. Take-time pulls = validated own pull bursts in [sign, sign + 200 ms] after a wallet take on the
same market; untriggered multi-level pulls = validated untriggered-all pull bursts with >= 2 levels. Compared on: levels
per burst, server-ms spread inside the burst (from the level events), the other side of the same book touched by an own
validated pull within +-20 ms, the delay to the next own validated add on the same book side (1.04-s FAK return vs 1.5-s
timer vs other), size.
(2) Take filter. Receipts = wallet takes + untriggered multi-level pulls. Gaining token = the token whose complement bids
were pulled (SELL side of the token-0 book = token-1 bids, so the gaining token is token 0) or the token bought. At
t - 1 ms: best ask of the gaining token, depth within 1c / 2c of it, spread, mid; trades on the book in the previous 30 s;
match vs map. Logit take vs strip-only, in-sample (BUILD-live only; frozen for VALIDATE-live).
Output: results/handler_filter.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SUF = os.environ.get("TOMMY_BLOCK_SUFFIX", "")


def book_at(L, t):
    """L: level events of one book (sorted by s); returns {(side, p): size} at time t (last z before t)."""
    x = L[L.s < t]
    last = x.groupby(["side", "p"]).z.last()
    return {k: v for k, v in last.items() if v > 0}


def main():
    B = pd.read_parquet(OUT / f"own_bursts_markouts_dev{SUF}.parquet")
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    E = pd.read_parquet(OUT / f"level_events_dev{SUF}.parquet", columns=["a", "s", "side", "p", "z", "kind", "d"])
    E = E.sort_values("s")
    tok = {str(r.tok0): (str(r.tok0), 0, r.slug) for r in dm.itertuples()}
    tok.update({str(r.tok1): (str(r.tok0), 1, r.slug) for r in dm.itertuples()})
    slug = {str(r.tok0): r.slug for r in dm.itertuples()}
    cd["tok"] = cd.token_id.astype(str)
    tk = cd[(cd.idx == -1) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(tok)].drop_duplicates("tx").copy()
    tk["a"] = tk.tok.map(lambda t: tok[t][0])
    tk["oi"] = tk.tok.map(lambda t: tok[t][1])
    books = set(B.a)
    tk = tk[tk.a.isin(books)]
    P = B[B.kind == "pull"].copy()
    Ad = B[B.kind == "add"]
    # (1) handler identity
    tkd = {a: np.sort(g.sign_ms.to_numpy(float)) for a, g in tk.groupby("a")}
    tt = []
    for r in P.itertuples():
        x = tkd.get(r.a)
        tt.append(bool(x is not None and np.any((r.s - x >= 0) & (r.s - x <= 200))))
    P["take_time"] = tt
    P["cls"] = np.where(P.take_time, "take_time", np.where((P.trig_code == 0) & (P.n >= 2), "untrig_multi",
                        np.where(P.trig_code == 0, "untrig_single", "other")))
    addk = {k: np.sort(g.s.to_numpy(float)) for k, g in Ad.groupby(["a", "side"])}
    pk = {k: np.sort(g.s.to_numpy(float)) for k, g in P.groupby(["a", "side"])}
    rows = []
    for r in P.itertuples():
        x = addk.get((r.a, r.side))
        nxt = None
        if x is not None:
            j = np.searchsorted(x, r.s + 1)
            nxt = x[j] - r.s if j < len(x) else None
        other = "SELL" if r.side == "BUY" else "BUY"
        y = pk.get((r.a, other))
        both = bool(y is not None and np.any(np.abs(y - r.s) <= 20))
        Lc = E[(E.a == r.a) & (E.side == r.side) & (E.kind == "cancel") & (E.s >= r.s) & (E.s <= r.s + 5)]
        rows.append({"cls": r.cls, "n": r.n, "spread_ms": float(Lc.s.max() - Lc.s.min()) if len(Lc) else 0.0,
                     "both_sides": both, "next_add_ms": nxt, "size": r.size})
    Q = pd.DataFrame(rows)
    hid = {}
    for c, g in Q.groupby("cls"):
        na = g.next_add_ms.dropna()
        hid[c] = {"n": int(len(g)), "levels_mean": round(float(g.n.mean()), 2), "multi_share": round(float((g.n >= 2).mean()), 3),
                  "spread_ms_median": round(float(g.spread_ms.median()), 1), "both_sides_share": round(float(g.both_sides.mean()), 3),
                  "next_add_1000_1150ms": round(float(((na >= 1000) & (na <= 1150)).mean()), 3) if len(na) else None,
                  "next_add_1480_1540ms": round(float(((na >= 1480) & (na <= 1540)).mean()), 3) if len(na) else None,
                  "next_add_lt_1000ms": round(float((na < 1000).mean()), 3) if len(na) else None,
                  "next_add_median_ms": round(float(na.median()), 0) if len(na) else None,
                  "size_100_share": round(float((g["size"] == 100).mean()), 3)}
    res = {"handler_identity": hid}
    # (2) take vs strip-only filter at receipts
    Lb = {a: g for a, g in E.groupby("a")}
    rec = []
    for r in tk.itertuples():
        rec.append({"a": r.a, "t": float(r.sign_ms), "gain": int(r.oi), "y": 1})
    for r in P[P.cls == "untrig_multi"].itertuples():
        rec.append({"a": r.a, "t": float(r.s), "gain": 0 if r.side == "SELL" else 1, "y": 0})
    feats = []
    for r in rec:
        L = Lb[r["a"]]
        bk = book_at(L, r["t"] - 1)
        bids = {p: z for (sd, p), z in bk.items() if sd == "BUY"}
        asks = {p: z for (sd, p), z in bk.items() if sd == "SELL"}
        if not bids or not asks:
            continue
        bb, ba = max(bids), min(asks)
        if r["gain"] == 0:  # token-0 asks
            best = ba
            d1 = sum(z for p, z in asks.items() if p <= ba + 0.01 + 1e-9)
            d2 = sum(z for p, z in asks.items() if p <= ba + 0.02 + 1e-9)
        else:  # token-1 asks = token-0 bids at 1 - p
            best = 1 - bb
            d1 = sum(z for p, z in bids.items() if p >= bb - 0.01 - 1e-9)
            d2 = sum(z for p, z in bids.items() if p >= bb - 0.02 - 1e-9)
        tr = L[(L.kind == "cons") & (L.s < r["t"]) & (L.s >= r["t"] - 30000)]
        feats.append({**r, "best_ask": best, "d1": d1, "d2": d2, "spread": ba - bb, "mid": (ba + bb) / 2,
                      "trades30": int(len(tr)), "match": int(not str(slug.get(r["a"], "")).split("-")[-1].startswith("game"))})
    F = pd.DataFrame(feats)
    res["receipts"] = {"takes": int(F.y.sum()), "strip_only": int((F.y == 0).sum())}
    res["receipt_feature_medians"] = F.groupby("y")[["best_ask", "d1", "d2", "spread", "trades30", "match"]].median().round(3).to_dict("index")
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_predict
        X = np.column_stack([np.log1p(F.d1), np.log1p(F.d2), F.spread, np.abs(F.best_ask - 0.5), np.log1p(F.trades30), F.match])
        lr = LogisticRegression(max_iter=5000)
        pr = cross_val_predict(lr, X, F.y, cv=5, method="predict_proba")[:, 1]
        from scipy.stats import rankdata
        y = F.y.to_numpy().astype(bool)
        rk = rankdata(pr)
        res["take_vs_strip_auc_cv5"] = round(float((rk[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum())), 4)
        lr.fit(X, F.y)
        res["coef"] = dict(zip(["log1p_d1", "log1p_d2", "spread", "|ask-0.5|", "log1p_trades30", "match"], [round(float(c), 3) for c in lr.coef_[0]]))
    except Exception as e:  # noqa: BLE001
        res["logit_error"] = repr(e)[:200]
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(RES / f"handler_filter{SUF}.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
