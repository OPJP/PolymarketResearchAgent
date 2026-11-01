"""Iteration 8, X107 (mechanics panel iter7 P1): ground-truth cancels for the maker leg's pull label (BUILD-live).

Ground truth (GT): a maker BUY order in calldata_dev that was partially filled (remainder R = shares - total fill >= 1)
and whose remainder later leaves its book level in a trade-free decrease of exactly R (+-0.011 shares), after the
first trade-consumption at that level that follows its add; rejected if any other add of size R sits at the level
between its add and that decrease (ambiguous). Owner = the order's maker. Level = (token-0 book, BUY p) for token-0
orders, (token-0 book, SELL 1-p) for token-1 orders, as in the recorder's token-0 books.

Because the frozen pull label only marks cancels whose size is an in-market wallet add size, remainder cancels test
it through co-burst attribution: a labelled own pull burst (validated multi-level or odd-size cancels on one book and
side within 5 ms) that has a GT cancel on the same book and side within +-5 ms is attributed to the GT owner (one
process strips several levels in one batch). Reported: precision of the label by class (multi-level / single odd) and
by trigger class (untriggered-all / triggered), recall of GT wallet remainder cancels inside labelled bursts, and the
untriggered markout restricted to bursts with a GT-wallet co-cancel and to the complement (placebo: GT other owner).
Output: results/cancel_truth.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SUF = os.environ.get("TOMMY_BLOCK_SUFFIX", "")


def main():
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    dm = pd.read_parquet(OUT / f"dev_markets{SUF}.parquet")
    E = pd.read_parquet(OUT / f"level_events_dev{SUF}.parquet")
    B = pd.read_parquet(OUT / f"own_bursts_markouts_dev{SUF}.parquet")
    tok0 = {str(r.tok0): (str(r.tok0), 0) for r in dm.itertuples()}
    tok0.update({str(r.tok1): (str(r.tok0), 1) for r in dm.itertuples()})
    books = set(E.a)
    mk = cd[(cd.idx >= 0) & (cd.side == 0)].copy()
    mk["tok"] = mk.token_id.astype(str)
    mk = mk[mk.tok.isin(tok0)]
    g = mk.groupby(["maker", "salt", "sign_ms", "tok"]).agg(price=("price", "first"), shares=("shares", "first"),
                                                            filled=("fill", "sum"), nf=("fill", "size")).reset_index()
    g["R"] = (g.shares - g.filled).round(2)
    g = g[g.R >= 1].copy()
    g["a"] = g.tok.map(lambda t: tok0[t][0])
    g["oi"] = g.tok.map(lambda t: tok0[t][1])
    g = g[g.a.isin(books)]
    g["side"] = np.where(g.oi == 0, "BUY", "SELL")
    g["p"] = np.where(g.oi == 0, g.price.round(3), (1 - g.price).round(3))
    lev = {k: v.sort_values("s") for k, v in E.groupby(["a", "side", "p"])}
    gt = []
    for r in g.itertuples():
        L = lev.get((r.a, r.side, round(float(r.p), 3)))
        if L is None:
            continue
        s_, k_, d_ = L.s.to_numpy(float), L.kind.to_numpy(), L.d.to_numpy(float)
        ia = np.where((k_ == "add") & (np.abs(d_ - r.shares) < 0.011) & (s_ >= r.sign_ms - 300) & (s_ <= r.sign_ms + 3000))[0]
        if len(ia) == 0:
            continue
        sa = s_[ia[0]]
        ic = np.where((k_ == "cons") & (s_ > sa))[0]
        if len(ic) == 0:
            continue
        sc0 = s_[ic[0]]
        ix = np.where((k_ == "cancel") & (np.abs(-d_ - r.R) < 0.011) & (s_ > sc0))[0]
        if len(ix) == 0:
            continue
        sx = s_[ix[0]]
        amb = np.any((k_ == "add") & (np.abs(d_ - r.R) < 0.011) & (s_ > sa) & (s_ < sx))
        if amb:
            continue
        gt.append({"a": r.a, "side": r.side, "p": float(r.p), "s": sx, "R": float(r.R), "owner": "wallet" if r.maker.lower() == WALLET else r.maker.lower(),
                   "shares": float(r.shares), "life_s": (sx - r.sign_ms) / 1000})
    G = pd.DataFrame(gt)
    res = {"partial_orders_on_recorded_books": int(len(g)), "partial_orders_wallet": int((g.maker.str.lower() == WALLET).sum()),
           "gt_cancels": int(len(G)), "gt_cancels_wallet": int((G.owner == "wallet").sum()) if len(G) else 0}
    if len(G) == 0:
        print(json.dumps(res, indent=1))
        return
    res["gt_owner_top"] = G.owner.value_counts().head(8).to_dict()
    # labelled own pull bursts (frozen validated label, iteration 7) and co-burst attribution
    P = B[B.kind == "pull"].copy().reset_index(drop=True)
    P["cls"] = np.where(P.n >= 2, "multi", "single_odd")
    gidx = {k: v for k, v in G.groupby(["a", "side"])}
    own, other = [], []
    for r in P.itertuples():
        x = gidx.get((r.a, r.side))
        if x is None:
            own.append(False); other.append(False)
            continue
        m = np.abs(x.s.to_numpy(float) - r.s) <= 5
        own.append(bool((x.owner[m] == "wallet").any()))
        other.append(bool((x.owner[m] != "wallet").any()))
    P["gt_wallet"], P["gt_other"] = own, other
    P["grp"] = np.where(P.trig_code == 0, "untrig_all", np.where(P.trig_code == 2, "trig_cross_only", "trig"))
    att = {}
    for key, sub in [("all", P)] + [(f"cls_{c}", P[P.cls == c]) for c in ("multi", "single_odd")] + \
                    [(f"grp_{c}", P[P.grp == c]) for c in ("untrig_all", "trig", "trig_cross_only")] + \
                    [(f"multi_{c}", P[(P.cls == "multi") & (P.grp == c)]) for c in ("untrig_all", "trig")]:
        a_ = sub[sub.gt_wallet | sub.gt_other]
        att[key] = {"bursts": int(len(sub)), "with_gt_cocancel": int(len(a_)),
                    "precision_wallet": round(float(a_.gt_wallet.mean()), 3) if len(a_) else None,
                    "n_gt_wallet": int(a_.gt_wallet.sum()), "n_gt_other_only": int((a_.gt_other & ~a_.gt_wallet).sum())}
    res["label_precision_by_cocancel"] = att
    # recall: GT wallet cancels that sit inside a labelled pull burst (+-5 ms, same book and side)
    pidx = {k: np.sort(v.s.to_numpy(float)) for k, v in P.groupby(["a", "side"])}
    inb = []
    for r in G.itertuples():
        x = pidx.get((r.a, r.side))
        inb.append(bool(x is not None and np.any(np.abs(x - r.s) <= 5)))
    G["in_label_burst"] = inb
    res["gt_wallet_in_label_burst"] = round(float(G.loc[G.owner == "wallet", "in_label_burst"].mean()), 3) if (G.owner == "wallet").any() else None
    res["gt_other_in_label_burst"] = round(float(G.loc[G.owner != "wallet", "in_label_burst"].mean()), 3) if (G.owner != "wallet").any() else None
    # markouts of labelled pull bursts by attribution (the frozen 10-s others'-mid markout, from own_bursts_markouts_dev)
    mko = {}
    for key, sub in (("untrig_gt_wallet", P[(P.grp == "untrig_all") & P.gt_wallet]),
                     ("untrig_gt_other_only", P[(P.grp == "untrig_all") & P.gt_other & ~P.gt_wallet]),
                     ("untrig_no_gt", P[(P.grp == "untrig_all") & ~P.gt_wallet & ~P.gt_other]),
                     ("trig_gt_wallet", P[(P.grp == "trig") & P.gt_wallet]),
                     ("trig_gt_other_only", P[(P.grp == "trig") & P.gt_other & ~P.gt_wallet])):
        v = sub.mk10.dropna().to_numpy()
        mko[key] = {"n": int(len(v)), "mk10_mean_c": round(float(v.mean() * 100), 3) if len(v) else None,
                    "mk2_mean_c": round(float(sub.mk2.dropna().mean() * 100), 3) if len(v) else None,
                    "mk30_mean_c": round(float(sub.mk30.dropna().mean() * 100), 3) if len(v) else None}
    res["markouts_by_attribution"] = mko
    # GT wallet remainder cancels as their own unit: lifetime and size
    gw = G[G.owner == "wallet"]
    res["gt_wallet_life_s_p25_50_75"] = [round(float(x), 1) for x in np.percentile(gw.life_s, [25, 50, 75])] if len(gw) else None
    res["gt_wallet_orig_shares"] = gw.shares.round(0).value_counts().head(5).to_dict() if len(gw) else None
    G.to_parquet(OUT / f"gt_cancels_dev{SUF}.parquet", index=False)
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(RES / f"cancel_truth{SUF}.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
