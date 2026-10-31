"""Iteration 7, X94 (mechanics panel iter6 P3): are the maker leg's UNTRIGGERED re-quotes informed (a dense label of a
private feed), or is the ladder an uninformed state machine of public, own and timer inputs?

BUILD-live (10-31 14:50-18:00 UTC, own recorder tommy_cs2_near, server clock, the 7 token-0 books of the wallet's
dev-unit CS2 markets). Validated own label (label_validate.py, X92): an add is the wallet's if it links to a wallet
order in calldata, or it is a whole-cent add of an in-market wallet size that is in an equal-size multi-level burst
(>= 2 within 5 ms) or has an odd size (!= 100). Own add bursts = validated own adds on one (book, side) within 5 ms.
Own pull bursts = validated multi-level / odd-size cancels (as wave_lock_valid.py).
Triggered if any of these precede the burst: a non-own level event or a trade on the same book in [-300, 0] ms; an own
cancel at the same price and size 1,480-1,540 ms earlier (timer re-post); a wallet taker signing on the same event in
[-2 s, 0] (calldata). Bursts in the 5 s before a wallet take are dropped (no conditioning on its later action).
Markout of the burst's token i: mid(t + h) - mid(t) for h = 2 / 10 / 30 s (token-1 bids = SELL side, sign flipped).
Adds: positive markout = it added bids before its token rose. Pulls: negative = it pulled before a fall.
Null: the same bursts shifted by +-U(60, 600) s within the same book (2,000 draws of the mean, vectorised).
Output: results/untriggered_othersmid.json (iteration 7 v2: markouts on the OTHERS' mid, own validated levels removed, so a pull of its own top cannot move the mid mechanically; plus the cross-market untriggered split)
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
# iteration 7: block parameters for re-use on later development blocks (defaults = BUILD-live 10-31 14:50-18:00);
# TOMMY_BLOCK_START / TOMMY_BLOCK_END (unix s) and TOMMY_BLOCK_SUFFIX (appended to every input / output file name)
SUF = _os.environ.get("TOMMY_BLOCK_SUFFIX", "")
OWN0, END = int(_os.environ.get("TOMMY_BLOCK_START", 1793458232)), int(_os.environ.get("TOMMY_BLOCK_END", 1793469600))
HS = (2000, 10000, 30000)
rng = np.random.default_rng(11)


def mids_from_feed(books, vset=None, own_sz=None):
    """Others' mid per token-0 book: best bid / ask among levels with (size - own) > 0.5, own = validated own adds
    (vset membership) decremented by in-market-size decreases (as live_price_relabel 'valid')."""
    st, M = {}, {a: [] for a in books}
    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                a = r.get("a")
                if a not in books or "s" not in r:
                    continue
                k = r.get("k")
                s_ = float(r["s"])
                if k in ("q", "f"):
                    b = {float(p): float(z) for p, z in (r.get("b") or [])}
                    o = {float(p): float(z) for p, z in (r.get("o") or [])}
                    if a in st:
                        ob, oo = st[a][2], st[a][3]
                        ob = {p: min(v, b.get(p, 0.0)) for p, v in ob.items()}
                        oo = {p: min(v, o.get(p, 0.0)) for p, v in oo.items()}
                    else:
                        ob, oo = {}, {}
                    st[a] = (b, o, ob, oo)
                elif k == "pc" and a in st:
                    b, o, ob, oo = st[a]
                    for sd, p, z in r.get("c") or []:
                        p, z = float(p), float(z)
                        bk, ow = (b, ob) if sd == "BUY" else (o, oo)
                        d = z - bk.get(p, 0.0)
                        whole = abs(p * 100 - round(p * 100)) < 1e-6
                        if d > 0 and vset is not None and (a, sd, round(p, 3), int(s_)) in vset:
                            ow[p] = ow.get(p, 0.0) + d
                        elif d < 0 and whole and own_sz is not None and round(abs(d), 2) in own_sz.get(a, {100.0}):
                            ow[p] = max(0.0, ow.get(p, 0.0) + d)
                        if z == 0:
                            bk.pop(p, None)
                        else:
                            bk[p] = z
                        if p in ow:
                            ow[p] = min(ow[p], bk.get(p, 0.0))
                else:
                    continue
                b, o, ob, oo = st[a]
                bb = [p for p, z in b.items() if z - ob.get(p, 0.0) > 0.5]
                aa = [p for p, z in o.items() if z - oo.get(p, 0.0) > 0.5]
                if bb and aa:
                    M[a].append((int(s_), (max(bb) + min(aa)) / 2))
        except Exception as e:  # noqa: BLE001
            print("feed", type(e).__name__, flush=True)
        h += 3600
    return {a: (np.array([x[0] for x in v], float), np.array([x[1] for x in v], float)) for a, v in M.items() if v}


def mid_at(m, t):
    s, v = m
    j = np.searchsorted(s, t, side="right") - 1
    return v[j] if j >= 0 else np.nan


def main():
    A = pd.read_parquet(OUT / f"linked_adds_dev{SUF}.parquet")
    A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
    books = set(A.a)
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    ev_of = {str(r.tok0): r.event for r in dm.itertuples()}
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    E = pd.read_parquet(OUT / f"level_events_dev{SUF}.parquet")
    E = E[E.a.isin(books)].copy()
    E["size"] = E.d.abs().round(2)
    own_sz = {a: set(g["size"]) for a, g in A[A.vown].groupby("a")}
    # validated own cancels (multi-level equal size within 5 ms, or odd in-market size)
    C = E[E.kind == "cancel"].sort_values(["a", "side", "s"]).reset_index(drop=True)
    C["f"] = [bool(abs(p * 100 - round(p * 100)) < 1e-6) and z in own_sz.get(a, {100.0}) for a, p, z in zip(C.a, C.p, C["size"])]
    multi = np.zeros(len(C), bool)
    for _, g in C[C.f].groupby(["a", "side"]):
        s_, z_, ix = g.s.to_numpy(), g["size"].to_numpy(), g.index.to_numpy()
        for i in range(len(g)):
            if ((np.abs(s_ - s_[i]) <= 5) & (z_ == z_[i])).sum() >= 2:
                multi[ix[i]] = True
    C["vown"] = C.f & (multi | (C["size"] != 100))
    # non-own events per book (any side), for the public trigger
    Ad = A[["a", "s", "vown"]].rename(columns={"vown": "own"})
    Cd = C[["a", "s", "vown"]].rename(columns={"vown": "own"})
    Tr = E[E.kind == "cons"][["a", "s"]].assign(own=False)
    nonown = pd.concat([Ad[~Ad.own], Cd[~Cd.own], Tr])
    no = {a: np.sort(g.s.to_numpy(float)) for a, g in nonown.groupby("a")}
    nonown["ev"] = nonown.a.map(ev_of)
    no_ev = {e: np.sort(g.s.to_numpy(float)) for e, g in nonown.groupby("ev")}
    own_cancel = {k: np.sort(g.s.to_numpy(float)) for k, g in C[C.vown].groupby(["a", "side", "p", "size"])}
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    cd["tok"] = cd.token_id.astype(str)
    tk = cd[(cd.idx == -1) & (cd.maker.str.lower() == WALLET) & cd.tok.isin(t0map)].drop_duplicates("tx")
    tke = {}
    for r in tk.itertuples():
        tke.setdefault(ev_of.get(t0map[r.tok]), []).append(float(r.sign_ms))
    tke = {k: np.sort(np.array(v)) for k, v in tke.items()}

    def bursts(df, kind):
        out = []
        for (a, sd), g in df.sort_values("s").groupby(["a", "side"]):
            s_ = g.s.to_numpy(float)
            p_ = g.p.to_numpy(float)
            z_ = g["size"].to_numpy(float)
            i = 0
            while i < len(g):
                j = i
                while j + 1 < len(g) and s_[j + 1] - s_[i] <= 5:
                    j += 1
                out.append({"a": a, "side": sd, "s": s_[i], "pmax": p_[i:j + 1].max(), "pmin": p_[i:j + 1].min(),
                            "n": j - i + 1, "size": z_[i], "kind": kind})
                i = j + 1
        return pd.DataFrame(out)

    B = pd.concat([bursts(A[A.vown], "add"), bursts(C[C.vown], "pull")], ignore_index=True)
    trig, drop = [], []
    for r in B.itertuples():
        x = no.get(r.a)
        pub = x is not None and np.any((x >= r.s - 300) & (x <= r.s))
        tm = False
        if r.kind == "add":
            for p in (r.pmax, r.pmin):
                oc = own_cancel.get((r.a, r.side, p, r.size))
                if oc is not None and np.any((oc >= r.s - 1540) & (oc <= r.s - 1480)):
                    tm = True
        t = tke.get(ev_of.get(r.a))
        tk_before = t is not None and np.any((t >= r.s - 2000) & (t <= r.s))
        tk_after = t is not None and np.any((t > r.s) & (t <= r.s + 5000))
        xe = no_ev.get(ev_of.get(r.a))
        pub_ev = xe is not None and np.any((xe >= r.s - 300) & (xe <= r.s))
        trig.append(bool(pub or tm or tk_before) + 2 * bool(pub_ev and not (pub or tm or tk_before)))
        drop.append(bool(tk_after))
    B["trig_code"] = trig  # 0 untriggered everywhere, 1 triggered in book / timer / take, 2 only cross-market
    B["triggered"] = B.trig_code > 0
    B = B[~np.array(drop)].copy()
    B.to_parquet(OUT / f"own_bursts_dev{SUF}.parquet", index=False)  # intermediate (development block only)
    if "--bursts-only" in sys.argv:
        return
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in A[A.vown].itertuples()}
    M = mids_from_feed(books, vset, own_sz)
    sgn = np.where(B.side == "BUY", 1.0, -1.0)
    for h in HS:
        B[f"mk{h // 1000}"] = [sg * (mid_at(M[a], s + h) - mid_at(M[a], s)) if a in M else np.nan
                               for a, s, sg in zip(B.a, B.s, sgn)]
    B.to_parquet(OUT / f"own_bursts_markouts_dev{SUF}.parquet", index=False)  # per-burst markouts (development block only)
    res = {"bursts": int(len(B)), "by_kind_trigger": {}}
    B["grp"] = np.where(B.trig_code == 0, "untrig_all", np.where(B.trig_code == 2, "trig_cross_only", "trig"))
    for (kind, tr), g in B.groupby(["kind", "grp"]):
        o = {"n": int(len(g))}
        for h in HS:
            c = f"mk{h // 1000}"
            v = g[c].dropna().to_numpy()
            o[c + "_mean_c"] = round(float(v.mean() * 100), 3) if len(v) else None
            o[c + "_share_pos"] = round(float((v > 0.0049).mean()), 3) if len(v) else None
            o[c + "_share_neg"] = round(float((v < -0.0049).mean()), 3) if len(v) else None
            # null: shift within book
            if len(g) >= 10:
                nul = np.zeros(2000)
                tot = np.zeros(2000)
                for a, gg in g.groupby("a"):
                    if a not in M:
                        continue
                    ms, mv = M[a]
                    s0 = gg.s.to_numpy(float)
                    sg = np.where(gg.side.to_numpy() == "BUY", 1.0, -1.0)
                    for dI in range(2000):
                        sh = rng.uniform(60000, 600000, len(s0)) * rng.choice([-1, 1], len(s0))
                        t = s0 + sh
                        j0 = np.searchsorted(ms, t, side="right") - 1
                        j1 = np.searchsorted(ms, t + h, side="right") - 1
                        ok = (j0 >= 0) & (j1 >= 0) & (t >= ms[0]) & (t + h <= ms[-1])
                        if ok.any():
                            nul[dI] += float(np.sum(sg[ok] * (mv[j1[ok]] - mv[j0[ok]])))
                            tot[dI] += int(ok.sum())
                nul = nul / np.maximum(tot, 1)
                m0 = np.nanmean(v) if len(v) else np.nan
                o[c + "_null_mean_c"] = round(float(np.mean(nul) * 100), 3)
                o[c + "_p_greater"] = round(float((nul >= m0).mean()), 4)
                o[c + "_p_less"] = round(float((nul <= m0).mean()), 4)
        res["by_kind_trigger"][f"{kind}_{tr}"] = o
    res["untriggered_share"] = B.groupby("kind").triggered.apply(lambda x: round(float(1 - x.mean()), 3)).to_dict()
    res["takes_in_window"] = int(sum(len(v) for v in tke.values()))
    (RES / f"untriggered_othersmid{SUF}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
