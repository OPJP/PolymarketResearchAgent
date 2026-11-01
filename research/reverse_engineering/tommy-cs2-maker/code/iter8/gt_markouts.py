"""Iteration 8, X107 step 3 (mechanics panel iter7 P1): markouts of GROUND-TRUTH wallet cancels (remainder cancels of
partially filled wallet orders, cancel_truth.py) by trigger class, on the OTHERS' mid (own validated levels removed),
with the iteration-7 trigger definition, except that GT wallet cancels are not counted as non-own events. Also saves
the others'-mid series of the BUILD-live books (others_mid_dev.parquet) for re-use. Null: 2,000 within-book shifts of
+-U(60, 600) s. Output: results/gt_markouts.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter7"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import untriggered_v2 as U  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = U.WALLET
SUF = os.environ.get("TOMMY_BLOCK_SUFFIX", "")
rng = np.random.default_rng(5)


def main():
    A = pd.read_parquet(OUT / f"linked_adds_dev{SUF}.parquet")
    A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
    books = set(A.a)
    own_sz = {a: set(g["size"]) for a, g in A[A.vown].groupby("a")}
    mp = OUT / f"others_mid_dev{SUF}.parquet"
    if mp.exists():
        m = pd.read_parquet(mp)
        M = {a: (g.s.to_numpy(float), g.mid.to_numpy(float)) for a, g in m.groupby("a")}
    else:
        vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in A[A.vown].itertuples()}
        M = U.mids_from_feed(books, vset, own_sz)
        pd.concat([pd.DataFrame({"a": a, "s": v[0], "mid": v[1]}) for a, v in M.items()]).to_parquet(mp, index=False)
    G = pd.read_parquet(OUT / f"gt_cancels_dev{SUF}.parquet")
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    ev_of = {str(r.tok0): r.event for r in dm.itertuples()}
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    E = pd.read_parquet(OUT / f"level_events_dev{SUF}.parquet")
    E = E[E.a.isin(books)].copy()
    E["size"] = E.d.abs().round(2)
    gw = G[G.owner == "wallet"]
    gwk = set(zip(gw.a, gw.side, gw.p.round(3), gw.s.astype(np.int64)))
    C = E[E.kind == "cancel"].copy()
    C["f"] = [bool(abs(p * 100 - round(p * 100)) < 1e-6) and z in own_sz.get(a, {100.0}) for a, p, z in zip(C.a, C.p, C["size"])]
    C["gtw"] = [(a, sd, round(float(p), 3), int(s)) in gwk for a, sd, p, s in zip(C.a, C.side, C.p, C.s)]
    # non-own events: adds not validated own, cancels that are neither own-size whole-cent nor GT wallet, trades
    nonown = pd.concat([A.loc[~A.vown, ["a", "s"]], C.loc[~C.f & ~C.gtw, ["a", "s"]], E.loc[E.kind == "cons", ["a", "s"]]])
    no = {a: np.sort(g.s.to_numpy(float)) for a, g in nonown.groupby("a")}
    nonown["ev"] = nonown.a.map(ev_of)
    no_ev = {e: np.sort(g.s.to_numpy(float)) for e, g in nonown.groupby("ev")}
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    cd["tok"] = cd.token_id.astype(str)
    tk = cd[(cd.idx == -1) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)].drop_duplicates("tx")
    tke = {}
    for r in tk.itertuples():
        tke.setdefault(ev_of.get(t0map[r.tok]), []).append(float(r.sign_ms))
    tke = {k: np.sort(np.array(v)) for k, v in tke.items()}
    rows = []
    for r in G.itertuples():
        x = no.get(r.a)
        pub = x is not None and np.any((x >= r.s - 300) & (x < r.s))
        t = tke.get(ev_of.get(r.a))
        tkb = t is not None and np.any((t >= r.s - 2000) & (t <= r.s))
        tka = t is not None and np.any((t > r.s) & (t <= r.s + 5000))
        xe = no_ev.get(ev_of.get(r.a))
        pev = xe is not None and np.any((xe >= r.s - 300) & (xe < r.s))
        code = 1 if (pub or tkb) else (2 if pev else 0)
        sg = 1.0 if r.side == "BUY" else -1.0
        mk = {h: (sg * (U.mid_at(M[r.a], r.s + h) - U.mid_at(M[r.a], r.s)) if r.a in M else np.nan) for h in (2000, 10000, 30000)}
        rows.append({"owner": r.owner, "a": r.a, "side": r.side, "s": r.s, "code": code, "drop": tka,
                     "mk2": mk[2000], "mk10": mk[10000], "mk30": mk[30000]})
    R = pd.DataFrame(rows)
    res = {}
    for (own, code), g in R[~R["drop"]].groupby([R.owner == "wallet", "code"]):
        key = f"{'wallet' if own else 'other'}_code{code}"
        v = g.mk10.dropna().to_numpy()
        o = {"n": int(len(g)), "mk2_c": round(float(g.mk2.mean() * 100), 3), "mk10_c": round(float(v.mean() * 100), 3) if len(v) else None,
             "mk30_c": round(float(g.mk30.mean() * 100), 3), "share_mk10_le_-1c": round(float((v <= -0.0099).mean()), 3) if len(v) else None,
             "share_mk10_ge_+1c": round(float((v >= 0.0099).mean()), 3) if len(v) else None}
        if len(v) >= 5:
            nul = []
            for _ in range(2000):
                sh = []
                for r in g.itertuples():
                    if r.a not in M:
                        continue
                    t = r.s + rng.choice([-1, 1]) * rng.uniform(60000, 600000)
                    sg = 1.0 if r.side == "BUY" else -1.0
                    sh.append(sg * (U.mid_at(M[r.a], t + 10000) - U.mid_at(M[r.a], t)))
                sh = np.array(sh, float)
                nul.append(np.nanmean(sh))
            nul = np.array(nul)
            o["null_mk10_mean_c"] = round(float(np.nanmean(nul) * 100), 3)
            o["p_lower"] = round(float((nul <= np.nanmean(v)).mean()), 4)
        res[key] = o
    res["note"] = ("code 0 = untriggered on every book of the event, 1 = triggered on the book / by a wallet take, 2 = "
                   "cross-market trigger only; GT wallet cancels are not counted as non-own events; drop = a wallet take "
                   "within 5 s after")
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / f"gt_markouts{SUF}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
