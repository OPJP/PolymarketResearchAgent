"""X170 (assumptions panel iter-11 P4): is the take a threshold on the wallet's own revealed value against the stale ask?

BUILD-live (10-31 14:50-18:00, raw tommy_cs2_near book with snapshots, calldata-validated own label; book machinery of
code/iter12/slot_vrel_panel.py). Markers: (a) its own FAK BUY takes (calldata_dev, sign + 24 ms on the server clock);
(b) its untriggered own re-price bursts (own_bursts_dev trig_code 0: no public trigger on any book of the event).
Token X of a marker: the bought token for takes; for untriggered bursts the token whose value rose (an add above its
old top on the token0 bid or a pull on the token1 bid -> token0; the mirror -> token1).
State read 30 ms before the marker (others' best ask on X with own levels removed, its size, own tops) and 1.5 s after
it (own top on X: its re-posted level; for takes after the FAK returns). gap = own top on X after - others' best ask on X
before (cents). Fit take ~ gap (+ |dV|, ask depth) by logistic regression with leave-one-event-out scoring, AUC against
a shuffled-marker control and the previous-burst-team proxy. Output: results/take_gap.json
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
import os as _os
SUF = _os.environ.get("TOMMY_BLOCK_SUFFIX", "")
OWN0, END = int(_os.environ.get("TOMMY_BLOCK_START", 1793458232)), int(_os.environ.get("TOMMY_BLOCK_END", 1793469600))
POST_MS = 1500.0


def main():
    if "--from-rows" in sys.argv:
        R = pd.read_parquet(OUT / f"iter12/take_gap_rows{SUF}.parquet")
        if "take" in R.columns:
            R = R.rename(columns={"take": "is_take"})
        return analyse(R)
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {}
    slug_of = {}
    for r in dm.itertuples():
        t0map[str(r.tok0)] = (str(r.tok0), 0); t0map[str(r.tok1)] = (str(r.tok0), 1); slug_of[str(r.tok0)] = r.event
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    cd["tok"] = cd.token_id.astype(str)
    mo = cd[(cd.idx >= 0) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)].drop_duplicates("salt")
    sizes = {}
    for r in mo.itertuples():
        sizes.setdefault(t0map[r.tok][0], set()).add(round(float(r.shares), 2))
    sizes = {a: v | {100.0} for a, v in sizes.items()}
    tk = cd[(cd.idx == -1) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map) & (cd.side == 0)]
    tk = tk[(tk.sign_ms >= OWN0 * 1000) & (tk.sign_ms < END * 1000)]
    LA = pd.read_parquet(OUT / f"linked_adds_dev{SUF}.parquet")
    LA["valid"] = LA.F_mkt & (LA.in_burst | (LA["size"] != 100))
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in LA[LA.valid].itertuples()}
    OB = pd.read_parquet(OUT / f"own_bursts_dev{SUF}.parquet")
    U = OB[(OB.trig_code == 0) & OB.a.isin(set(slug_of))].copy()
    markers = []
    for r in tk.itertuples():
        a, oi = t0map[r.tok]
        markers.append({"a": a, "t": float(r.sign_ms) + 24.0, "is_take": 1, "X": oi, "limit": float(r.price), "kind": "take"})
    for r in U.itertuples():
        # BUY side = token0 bids; SELL side = token0 asks = token1 bids at 1 - p
        if r.side == "BUY":
            X = 0 if r.kind == "add" else 1
        else:
            X = 1 if r.kind == "add" else 0
        markers.append({"a": r.a, "t": float(r.s), "is_take": 0, "X": X, "limit": np.nan, "kind": f"untrig_{r.kind}"})
    M = pd.DataFrame(markers).sort_values("t").reset_index(drop=True)
    q = {}
    for i, r in M.iterrows():
        q.setdefault(r.a, []).append((r.t - 30.0, i, "pre"))
        q[r.a].append((r.t + POST_MS, i, "post"))
    for a in q:
        q[a].sort()
    st, qi = {}, {a: 0 for a in q}
    pre, post = {}, {}

    def snap(a):
        b, o, ob, oo = st[a][:4]
        oth_b = {p: z - ob.get(p, 0.0) for p, z in b.items() if z - ob.get(p, 0.0) > 0.5}
        oth_a = {p: z - oo.get(p, 0.0) for p, z in o.items() if z - oo.get(p, 0.0) > 0.5}
        own_b = [p for p, z in ob.items() if z > 0.5]
        own_a = [p for p, z in oo.items() if z > 0.5]
        ask0 = min(oth_a) if oth_a else np.nan
        bid0 = max(oth_b) if oth_b else np.nan
        return {"ask0": ask0, "ask0_sz": oth_a.get(ask0, np.nan) if np.isfinite(ask0) else np.nan,
                "bid0": bid0, "bid0_sz": oth_b.get(bid0, np.nan) if np.isfinite(bid0) else np.nan,
                "own0": max(own_b) if own_b else np.nan, "own1": (1 - min(own_a)) if own_a else np.nan}

    def answer(a, upto):
        qa = q[a]
        while qi[a] < len(qa) and qa[qi[a]][0] < upto:
            t, i, ph = qa[qi[a]]
            qi[a] += 1
            (pre if ph == "pre" else post)[i] = snap(a)

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
                    continue
                own_sz = sizes.get(a, {100.0})
                if k in ("q", "f"):
                    b = {float(p): float(z) for p, z in (r.get("b") or [])}
                    o = {float(p): float(z) for p, z in (r.get("o") or [])}
                    if a in st:
                        ob0, oo0 = st[a][2], st[a][3]
                        ob = {p: min(v, b.get(p, 0.0)) for p, v in ob0.items()}
                        oo = {p: min(v, o.get(p, 0.0)) for p, v in oo0.items()}
                    else:
                        ob, oo = {}, {}
                    st[a] = (b, o, ob, oo)
                elif k == "pc" and a in st:
                    b, o, ob, oo = st[a]
                    for sd, p, z in r.get("c") or []:
                        p, z = float(p), float(z)
                        book = b if sd == "BUY" else o
                        ow = ob if sd == "BUY" else oo
                        d = z - book.get(p, 0.0)
                        whole = abs(p * 100 - round(p * 100)) < 1e-6
                        fz = whole and round(abs(d), 2) in own_sz
                        if d > 0 and (a, sd, round(p, 3), int(s)) in vset:
                            ow[p] = ow.get(p, 0.0) + d
                        elif d < 0 and fz and ow.get(p, 0.0) > 0.5:
                            ow[p] = max(0.0, ow.get(p, 0.0) + d)
                        if z == 0:
                            book.pop(p, None)
                        else:
                            book[p] = z
                        if p in ow:
                            ow[p] = min(ow[p], book.get(p, 0.0))
        except Exception as e:  # noqa: BLE001
            print("feed", type(e).__name__, e, flush=True)
        h += 3600
    for a in q:
        if a in st:
            answer(a, 1e18)
    rows = []
    for i, r in M.iterrows():
        if i not in pre or i not in post:
            continue
        P0, P1 = pre[i], post[i]
        if r.X == 0:
            ask = P0["ask0"]; ask_sz = P0["ask0_sz"]; v_b = P0["own0"]; v_a = P1["own0"]; vc_b = P0["own1"]; vc_a = P1["own1"]
        else:
            ask = (1 - P0["bid0"]) if np.isfinite(P0["bid0"]) else np.nan; ask_sz = P0["bid0_sz"]
            v_b = P0["own1"]; v_a = P1["own1"]; vc_b = P0["own0"]; vc_a = P1["own0"]
        rows.append({**r.to_dict(), "event": slug_of.get(r.a), "ask": ask, "ask_sz": ask_sz, "own_X_before": v_b, "own_X_after": v_a,
                     "own_C_before": vc_b, "own_C_after": vc_a,
                     "gap": (v_a - ask) * 100 if np.isfinite(v_a) and np.isfinite(ask) else np.nan,
                     "gap_comp": ((0.99 - vc_a) - ask) * 100 if np.isfinite(vc_a) and np.isfinite(ask) else np.nan,
                     "dV": (v_a - v_b) * 100 if np.isfinite(v_a) and np.isfinite(v_b) else np.nan,
                     "premium": (r.limit - ask) * 100 if np.isfinite(r.limit) and np.isfinite(ask) else np.nan})
    R = pd.DataFrame(rows)
    R.to_parquet(OUT / f"iter12/take_gap_rows{SUF}.parquet", index=False)
    return analyse(R)


def analyse(R):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    out = {"markers": int(len(R)), "takes": int(R["is_take"].sum()), "untriggered": int((R["is_take"] == 0).sum())}
    for col in ("gap", "gap_comp"):
        S = R[np.isfinite(R[col])]
        if S["is_take"].nunique() < 2:
            continue
        auc = roc_auc_score(S["is_take"], S[col])
        rng = np.random.default_rng(3)
        null = [roc_auc_score(rng.permutation(S["is_take"].to_numpy()), S[col]) for _ in range(2000)]
        q_ = S.groupby("is_take")[col].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])
        out[col] = {"n": int(len(S)), "takes": int(S["is_take"].sum()), "auc_raw": round(float(auc), 3),
                    "perm_p": round(float((np.array(null) >= auc).mean()), 4),
                    "by_class": {str(k): {kk: round(float(vv), 2) for kk, vv in v.items()} for k, v in q_.iterrows()}}
    # leave-one-event-out logistic on gap + |dV| + log ask size
    S = R[np.isfinite(R.gap) & np.isfinite(R.ask_sz)].copy()
    if S["is_take"].nunique() == 2:
        S["absdV"] = np.abs(S.dV.fillna(0)); S["lsz"] = np.log1p(S.ask_sz)
        X = S[["gap", "absdV", "lsz"]].to_numpy(); y = S["is_take"].to_numpy(); pred = np.full(len(S), np.nan)
        for ev in S.event.unique():
            te = (S.event == ev).to_numpy()
            if y[~te].sum() < 3 or (1 - y[~te]).sum() < 3:
                continue
            m = LogisticRegression(max_iter=500).fit(X[~te], y[~te]); pred[te] = m.predict_proba(X[te])[:, 1]
        ok = np.isfinite(pred)
        if ok.sum() and len(np.unique(y[ok])) == 2:
            out["logit_loeo"] = {"n": int(ok.sum()), "auc": round(float(roc_auc_score(y[ok], pred[ok])), 3)}
    T = R[(R["is_take"] == 1) & np.isfinite(R.premium) & np.isfinite(R.gap)]
    if len(T) >= 5:
        out["premium_vs_gap_spearman"] = round(float(T[["premium", "gap"]].corr(method="spearman").iloc[0, 1]), 3)
        out["premium_median_c"] = round(float(T.premium.median()), 2)
    (RES / f"take_gap{SUF}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
