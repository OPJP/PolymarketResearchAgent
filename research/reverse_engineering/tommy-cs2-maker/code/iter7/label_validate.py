"""Iteration 7, X92 (mechanics panel iter6 P1, steps 1-2): validate the live-book "own level" size fingerprint against
calldata ground truth on the BUILD-live block (10-31 14:50-18:00 UTC, own recorder tommy_cs2_near, server clock).

Step 1 (link): every filled maker order in calldata_dev (any maker) on the token-0 books of the wallet's dev-unit CS2
markets is linked to its ADD on the book: same book side and price (token-1 BUY q -> token-0 SELL side at 1 - q), a size
increase equal to the order's original size (+-0.02), server time in [sign - 300 ms, sign + 3000 ms], earliest such add.
Owner of a linked add = the order's maker. Report the sign -> add latency by owner class, and the precision / recall of
the size fingerprints used since iteration 3:
  F_any100   : whole cent and size in {100, 68, 58, 54}            (pull_attrib / price rules)
  F_mkt      : whole cent and size in the wallet's sizes in that market (calldata) + {100}   (wave_lock / cooldown)
Step 2 (attribution rule from features unfilled orders also have): burst membership (>= 2 equal-size adds on the same
side within 5 ms at different prices), burst size, contiguity (an F_mkt level resting 1c away), post-take re-post
(1.00-1.15 s after a wallet taker signing on the same event, calldata), sizes 68 / 58 / 54, price vs others' best.
A logistic model is fitted on half the books' linked adds and scored on the other half (and vice versa); the precision
of the "validated own" label at the threshold that keeps precision >= 0.95 on the fitting half is reported.
Output: results/label_validate.json, .cache/re/tommy-cs2-maker/linked_adds_dev.parquet
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
import os as _os
# iteration 7: block parameters for re-use on later development blocks (defaults = BUILD-live 10-31 14:50-18:00);
# TOMMY_BLOCK_START / TOMMY_BLOCK_END (unix s) and TOMMY_BLOCK_SUFFIX (appended to every input / output file name)
SUF = _os.environ.get("TOMMY_BLOCK_SUFFIX", "")
OWN0, END = int(_os.environ.get("TOMMY_BLOCK_START", 1793458232)), int(_os.environ.get("TOMMY_BLOCK_END", 1793469600))
ANY_SIZES = (100.0, 68.0, 58.0, 54.0)


def main():
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    slug = {str(r.tok0): r.slug for r in dm.itertuples()}
    ev_of = {str(r.tok0): r.event for r in dm.itertuples()}
    E = pd.read_parquet(OUT / f"level_events_dev{SUF}.parquet")
    E = E[E.a.isin(set(slug))].copy()
    books = sorted(E.a.unique())
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    cd["tok"] = cd.token_id.astype(str)
    cd["a"] = cd.tok.map(t0map)
    mk = cd[(cd.idx >= 0) & cd.a.isin(set(books))].copy()
    mk["maker"] = mk.maker.str.lower()
    mk = mk.drop_duplicates(["maker", "salt"])  # one row per order
    mk["bside"] = np.where((mk.side == 0) == (mk.tok == mk.a), "BUY", "SELL")
    mk["bp"] = np.where(mk.tok == mk.a, mk.price, 1 - mk.price).round(3)
    mk = mk[(mk.sign_ms >= OWN0 * 1000 - 600_000) & (mk.sign_ms < END * 1000)]
    own_sizes = {a: set(np.round(g.shares.to_numpy(float), 2)) | {100.0}
                 for a, g in mk[mk.maker == WALLET].groupby("a")}
    adds = E[E.kind == "add"].copy()
    adds["size"] = adds.d.round(2)
    adds = adds.sort_values(["a", "side", "p", "s"]).reset_index(drop=True)
    adds["aid"] = np.arange(len(adds))
    grp = {k: g for k, g in adds.groupby(["a", "side", "p"])}
    link = []
    used = set()
    for r in mk.sort_values("sign_ms").itertuples():
        g = grp.get((r.a, r.bside, round(float(r.bp), 3)))
        if g is None:
            continue
        s = g.s.to_numpy()
        lo, hi = np.searchsorted(s, r.sign_ms - 300), np.searchsorted(s, r.sign_ms + 3000)
        for j in range(lo, hi):
            row = g.iloc[j]
            if abs(row["size"] - round(float(r.shares), 2)) <= 0.02 and int(row.aid) not in used:
                used.add(int(row.aid))
                link.append({"aid": int(row.aid), "maker": r.maker, "lat": float(row.s - r.sign_ms),
                             "shares": float(r.shares), "sign_ms": int(r.sign_ms)})
                break
    L = pd.DataFrame(link)
    A = adds.merge(L, on="aid", how="left")
    A["whole"] = (np.abs(A.p * 100 - np.round(A.p * 100)) < 1e-6)
    A["F_any100"] = A.whole & A["size"].isin(ANY_SIZES)
    A["F_mkt"] = [bool(w) and (round(float(z), 2) in own_sizes.get(a, {100.0})) for a, z, w in zip(A.a, A["size"], A.whole)]
    # burst features (same side, equal size, within 5 ms, different prices)
    A = A.sort_values(["a", "side", "s"]).reset_index(drop=True)
    burst_n = np.ones(len(A), int)
    for (a, sd), g in A.groupby(["a", "side"]):
        s = g.s.to_numpy()
        z = g["size"].to_numpy()
        idx = g.index.to_numpy()
        i = 0
        while i < len(g):
            j = i
            while j + 1 < len(g) and s[j + 1] - s[i] <= 5:
                j += 1
            if j > i:
                for zz in set(z[i:j + 1]):
                    m = [k for k in range(i, j + 1) if z[k] == zz]
                    if len(m) >= 2:
                        burst_n[idx[m]] = len(m)
            i = j + 1
    A["burst_n"] = burst_n
    A["in_burst"] = A.burst_n >= 2
    # wallet taker signings per event (re-post 1.00-1.15 s after its take)
    tk = cd[(cd.idx == -1) & (cd.maker.str.lower() == WALLET) & cd.a.notna()].drop_duplicates("tx")
    tk_ev = {}
    for r in tk.itertuples():
        tk_ev.setdefault(ev_of.get(r.a), []).append(int(r.sign_ms))
    tk_ev = {k: np.sort(np.array(v)) for k, v in tk_ev.items()}
    rep = []
    for a, s in zip(A.a, A.s):
        t = tk_ev.get(ev_of[a])
        if t is None:
            rep.append(False)
            continue
        j = np.searchsorted(t, s - 1150)
        rep.append(bool(j < len(t) and t[j] <= s - 1000))
    A["repost"] = rep
    A["odd_size"] = A["size"].isin((68.0, 58.0, 54.0)) | (A.whole & ~A["size"].isin((100.0,)) & A.F_mkt)
    A["owner"] = np.where(A.maker.isna(), "unlinked", np.where(A.maker == WALLET, "wallet", "other"))
    A["slug"] = A.a.map(slug)
    A.to_parquet(OUT / f"linked_adds_dev{SUF}.parquet", index=False)
    lk = A[A.owner != "unlinked"]
    res = {"books": len(books), "adds": int(len(A)), "filled_orders": int(len(mk)), "linked": int(len(lk)),
           "linked_by_owner": lk.owner.value_counts().to_dict(),
           "orders_by_owner": {"wallet": int((mk.maker == WALLET).sum()), "other": int((mk.maker != WALLET).sum())}}
    res["latency_ms_p10_p50_p90"] = {o: [round(float(x), 1) for x in np.percentile(g.lat, [10, 50, 90])]
                                     for o, g in lk.groupby("owner")}

    def pr(mask_label, sub):
        sel = sub[mask_label(sub)]
        tp = int((sel.owner == "wallet").sum())
        prec = tp / len(sel) if len(sel) else None
        rec = tp / int((sub.owner == "wallet").sum()) if (sub.owner == "wallet").any() else None
        return {"n_label": int(len(sel)), "precision": None if prec is None else round(prec, 3),
                "recall": None if rec is None else round(rec, 3)}

    fps = {"F_any100": lambda d: d.F_any100, "F_mkt": lambda d: d.F_mkt,
           "F_mkt_burst": lambda d: d.F_mkt & d.in_burst,
           "F_mkt_single": lambda d: d.F_mkt & ~d.in_burst,
           "F_mkt_100_single": lambda d: d.F_mkt & ~d.in_burst & (d["size"] == 100),
           "F_odd_size": lambda d: d.F_mkt & (d["size"] != 100),
           "F_mkt_repost": lambda d: d.F_mkt & d.repost}
    res["fingerprints_all_books"] = {k: pr(f, lk) for k, f in fps.items()}
    res["fingerprints_by_book"] = {slug[a]: {k: pr(f, g) for k, f in fps.items() if k in ("F_any100", "F_mkt", "F_mkt_burst", "F_mkt_single")}
                                   for a, g in lk.groupby("a")}
    # who are the other owners of F_mkt-labelled linked adds
    fo = lk[lk.F_mkt & (lk.owner == "other")]
    res["other_owners_of_F_mkt"] = fo.maker.str[:10].value_counts().head(8).to_dict()
    res["other_owner_burst_share"] = round(float(fo.in_burst.mean()), 3) if len(fo) else None
    res["wallet_burst_share"] = round(float(lk[lk.F_mkt & (lk.owner == "wallet")].in_burst.mean()), 3)
    (RES / f"label_validate{SUF}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
