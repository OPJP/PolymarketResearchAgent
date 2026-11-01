"""X150 (mechanics panel iter-10 P2): the per-order price ceiling with the wallet's own value known (BUILD-live).

Book machinery of fresh_touch_v2.py (tommy_cs2_near raw feed, snapshots + price changes, server clock, validated own
label; 10-31 14:50-18:00 UTC, development block 12-18). For every validated own add (uncensored decisions) and every
filled maker order of the wallet (calldata_dev), the state just BEFORE the decision (add: s - 30 ms; order: sign - 100 ms)
and just AFTER its burst (add: s + 15 ms; order: sign + 60 ms, after its ~24-ms post latency) is read.
V oracles (own state, never point-in-time for an examiner on h1 / h2):
  V_after  = its own top on the token after the burst (panel definition; includes the add itself);
  V_before = its own top before the decision (persistence of its top).
Target: slot = round(100 * (price - V)) clipped to [-8, 3]. Rules scored within one tick (|slot error| <= 1):
  constant mode slot; LightGBM multiclass on own-ladder and others'-book state before the decision (held own slots
  relative to its top, number of own levels, age of its top level, others' best J and its size, the gap J - own top,
  spread, time since the last non-own change at J, the token side), leave-one-event-out.
This is an oracle CEILING of any rule that knows V, not a rule. Output: results/slot_ceiling.json
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


def main():
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    tok = {r.cid: (str(r.tok0), str(r.tok1)) for r in dm.itertuples()}
    t0map = {v[0]: v[0] for v in tok.values()}
    t0map.update({v[1]: v[0] for v in tok.values()})
    slug_of = {str(r.tok0): r.slug for r in dm.itertuples()}
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    cd["tok"] = cd.token_id.astype(str)
    mo = cd[(cd.idx >= 0) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)].drop_duplicates("salt")
    mo = mo[(mo.sign_ms >= OWN0 * 1000) & (mo.sign_ms < END * 1000)]
    sizes = {}
    for r in mo.itertuples():
        sizes.setdefault(t0map[r.tok], set()).add(round(float(r.shares), 2))
    sizes = {a: v | {100.0} for a, v in sizes.items()}
    LA = pd.read_parquet(OUT / f"linked_adds_dev{SUF}.parquet")
    LA["valid"] = LA.F_mkt & (LA.in_burst | (LA["size"] != 100))
    V = LA[LA.valid]
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in V.itertuples()}
    q = {}
    qid = 0
    for r in mo.itertuples():
        a = t0map[r.tok]
        oi = 0 if r.tok == a else 1
        q.setdefault(a, []).append((float(r.sign_ms) - 100.0, qid, "pre", "fill", oi, round(float(r.price), 3)))
        q[a].append((float(r.sign_ms) + 60.0, qid, "post", "fill", oi, round(float(r.price), 3)))
        qid += 1
    for r in V.itertuples():
        oi = 0 if r.side == "BUY" else 1
        pr = float(r.p) if oi == 0 else 1 - float(r.p)
        q.setdefault(r.a, []).append((float(r.s) - 30.0, qid, "pre", "add", oi, round(pr, 3)))
        q[r.a].append((float(r.s) + 15.0, qid, "post", "add", oi, round(pr, 3)))
        qid += 1
    for a in q:
        q[a].sort()
    st = {}
    qi = {a: 0 for a in q}
    pre, post = {}, {}

    def answer(a, upto):
        b, o, ob, oo, lb, lo_, oage = st[a]
        qa = q[a]
        while qi[a] < len(qa) and qa[qi[a]][0] < upto:
            t, i, ph, kind, oi, price = qa[qi[a]]
            qi[a] += 1
            if oi == 0:
                oth = {p: z - ob.get(p, 0.0) for p, z in b.items() if z - ob.get(p, 0.0) > 0.5}
                own = sorted([p for p, z in ob.items() if z > 0.5], reverse=True)
                asks = [p for p, z in o.items() if z - oo.get(p, 0.0) > 0.5]
                best_ask = min(asks) if asks else np.nan
                last = lb
                ages = {p: oage.get(("b", p), np.nan) for p in own}
            else:
                oth = {1 - p: z - oo.get(p, 0.0) for p, z in o.items() if z - oo.get(p, 0.0) > 0.5}
                own = sorted([1 - p for p, z in oo.items() if z > 0.5], reverse=True)
                bids = [p for p, z in b.items() if z - ob.get(p, 0.0) > 0.5]
                best_ask = (1 - max(bids)) if bids else np.nan
                last = {1 - p: v for p, v in lo_.items()}
                ages = {p: oage.get(("o", round(1 - p, 3)), np.nan) for p in own}
            J = max(oth) if oth else np.nan
            ot = own[0] if own else np.nan
            if ph == "post":
                post[i] = ot
                continue
            rec = {"a": a, "slug": slug_of.get(a), "t": t, "kind": kind, "oi": oi, "p": price, "J": J, "own_top": ot,
                   "n_own": len(own), "J_size": oth.get(J, np.nan) if np.isfinite(J) else np.nan,
                   "gap_J_own": (J - ot) * 100 if np.isfinite(J) and np.isfinite(ot) else np.nan,
                   "spread": (best_ask - J) * 100 if np.isfinite(J) and np.isfinite(best_ask) else np.nan,
                   "J_fresh_ms": (t - last.get(J, -1e18)) if np.isfinite(J) else np.nan,
                   "top_age_ms": (t - ages.get(ot, np.nan)) if np.isfinite(ot) else np.nan}
            for k in range(1, 6):
                rec[f"held_m{k}"] = int(any(abs(x - (ot - k / 100)) < 1e-6 for x in own)) if np.isfinite(ot) else 0
            rec["own_levels"] = tuple(round(x, 3) for x in own)
            pre[i] = rec

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
                        b0, o0, ob0, oo0, lb, lo_, oage = st[a]
                        ob = {p: min(v, b.get(p, 0.0)) for p, v in ob0.items()}
                        oo = {p: min(v, o.get(p, 0.0)) for p, v in oo0.items()}
                        for p, z in b.items():
                            if abs(z - b0.get(p, 0.0)) > 0.5:
                                lb[p] = s
                        for p, z in o.items():
                            if abs(z - o0.get(p, 0.0)) > 0.5:
                                lo_[p] = s
                    else:
                        ob, oo, lb, lo_, oage = {}, {}, {}, {}, {}
                    st[a] = (b, o, ob, oo, lb, lo_, oage)
                elif k == "pc" and a in st:
                    b, o, ob, oo, lb, lo_, oage = st[a]
                    for sd, p, z in r.get("c") or []:
                        p, z = float(p), float(z)
                        book = b if sd == "BUY" else o
                        ow = ob if sd == "BUY" else oo
                        last = lb if sd == "BUY" else lo_
                        d = z - book.get(p, 0.0)
                        whole = abs(p * 100 - round(p * 100)) < 1e-6
                        fz = whole and round(abs(d), 2) in own_sz
                        own_change = False
                        if d > 0 and (a, sd, round(p, 3), int(s)) in vset:
                            ow[p] = ow.get(p, 0.0) + d
                            oage[("b" if sd == "BUY" else "o", round(p, 3))] = s
                            own_change = True
                        elif d < 0 and fz and ow.get(p, 0.0) > 0.5:
                            ow[p] = max(0.0, ow.get(p, 0.0) + d)
                            own_change = True
                        if not own_change and abs(d) > 1e-9:
                            last[p] = s
                        if z == 0:
                            book.pop(p, None)
                        else:
                            book[p] = z
                        if p in ow:
                            ow[p] = min(ow[p], book.get(p, 0.0))
        except Exception as e:  # noqa: BLE001
            print("feed", type(e).__name__, flush=True)
        h += 3600
    for a in q:
        if a in st:
            answer(a, 1e18)
    R = pd.DataFrame([dict(v, qid=i, V_after=post.get(i, np.nan)) for i, v in pre.items()])
    R = R[R.p.between(0.04, 0.96)].copy()
    # V-relative own-ladder state (the iteration-11 classifier saw holes only relative to its OLD top)
    R["dV"] = np.where(np.isfinite(R.own_top), np.round((R.V_after - R.own_top) * 100), 99)
    for k in range(0, 7):
        R[f"hv{k}"] = [int(any(abs(x - (v - k / 100)) < 1e-6 for x in L)) if np.isfinite(v) else 0
                       for v, L in zip(R.V_after, R.own_levels)]
    # deterministic target-ladder rule: the highest V-relative slot in 0..-4 not held before the add
    def tl(row):
        if not np.isfinite(row.V_after):
            return np.nan
        for k in range(0, 5):
            if row[f"hv{k}"] == 0:
                return -k
        return -5
    R["tl_slot"] = R.apply(tl, axis=1)
    R["own_levels"] = [",".join(str(x) for x in L) for L in R.own_levels]
    R.to_parquet(OUT / f"iter12/slot_vrel_rows{SUF}.parquet")
    out = {}
    import lightgbm as lgb
    feats = ["oi", "J", "own_top", "n_own", "J_size", "gap_J_own", "spread", "J_fresh_ms", "top_age_ms",
             "held_m1", "held_m2", "held_m3", "held_m4", "held_m5", "dV"] + [f"hv{k}" for k in range(7)]
    for kind in ("add", "fill"):
        S = R[R.kind == kind].copy()
        o = {"n": int(len(S))}
        T0 = S[np.isfinite(S.V_after)].copy()
        sl = np.clip(np.round((T0.p - T0.V_after) * 100), -8, 3)
        o["target_ladder_rule_within_tick"] = round(float((np.abs(sl - T0.tl_slot) <= 1).mean()), 3)
        o["target_ladder_rule_exact"] = round(float((sl == T0.tl_slot).mean()), 3)
        for vn in ("V_after",):
            T = S[np.isfinite(S[vn])].copy()
            T["slot"] = np.clip(np.round((T.p - T[vn]) * 100), -8, 3).astype(int)
            dist = T.slot.value_counts(normalize=True).sort_index()
            mode = int(dist.idxmax())
            const_hit = float((np.abs(T.slot - mode) <= 1).mean())
            r = {"n": int(len(T)), "slot_dist": {int(k): round(float(v), 3) for k, v in dist.items()}, "mode": mode,
                 "within_tick_constant_mode": round(const_hit, 3),
                 "within_tick_V_itself": round(float((np.abs(T.slot) <= 1).mean()), 3)}
            # leave-one-event-out LightGBM multiclass
            classes = sorted(T.slot.unique())
            cmap = {c: i for i, c in enumerate(classes)}
            y = T.slot.map(cmap).to_numpy()
            X = T[feats].astype(float).to_numpy()
            pred = np.full(len(T), mode)
            for ev in T.slug.fillna("?").unique():
                te = (T.slug.fillna("?") == ev).to_numpy()
                if te.sum() == 0 or (~te).sum() < 50:
                    continue
                m = lgb.LGBMClassifier(n_estimators=150, learning_rate=0.05, num_leaves=15, max_bin=63, min_child_samples=10,
                                       verbose=-1, objective="multiclass")
                m.fit(X[~te], y[~te])
                pr = m.predict_proba(X[te])
                # choose the class that maximizes the probability of being within one slot
                cl = np.array(m.classes_)
                vals = np.array([classes[c] for c in cl])
                score = np.stack([pr[:, (np.abs(vals - v) <= 1)].sum(1) for v in vals], 1)
                pred[te] = vals[np.argmax(score, 1)]
            r["within_tick_lgbm_loeo"] = round(float((np.abs(pred - T.slot.to_numpy()) <= 1).mean()), 3)
            o[vn] = r
        o["touch_within_tick"] = round(float((np.abs(S.p - S.J) <= 0.01 + 1e-9).mean()), 3)
        out[kind] = o
    (RES / f"slot_ceiling_vrel{SUF}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
