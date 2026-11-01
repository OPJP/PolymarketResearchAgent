"""Iteration 7, X92 steps 2-3 for H69 (mechanics panel iter6 P1): whose is the 1.5-s same-price re-post timer in the
wallet's books? BUILD-live (10-31 14:50-18:00 UTC), the 7 token-0 books of level_events_dev, server clock.

Pairs: a trade-free decrease (kind 'cancel') at (book, side, price) of size z, followed by an add of the same size z at the
same (book, side, price) after dt ms. Spike = dt in [1490, 1530); controls = [1290, 1330) and [1690, 1730) (two windows,
so the excess is spike - control / 2 x 2 ... reported as spike vs mean control window).
The re-add is attributed through calldata where it was later filled (linked_adds_dev.parquet: owner wallet / other),
else 'unlinked'. Also by size class (100 vs the wallet's odd in-market sizes vs other sizes).
Output: results/timer_attrib.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
import os as _os
# iteration 7: block parameters for re-use on later development blocks (defaults = BUILD-live 10-31 14:50-18:00);
# TOMMY_BLOCK_START / TOMMY_BLOCK_END (unix s) and TOMMY_BLOCK_SUFFIX (appended to every input / output file name)
SUF = _os.environ.get("TOMMY_BLOCK_SUFFIX", "")
WIN = {"spike": (1490, 1530), "ctrl_lo": (1290, 1330), "ctrl_hi": (1690, 1730)}


def main():
    A = pd.read_parquet(OUT / f"linked_adds_dev{SUF}.parquet")
    E = pd.read_parquet(OUT / f"level_events_dev{SUF}.parquet")
    E = E[E.a.isin(set(A.a))]
    C = E[E.kind == "cancel"].copy()
    C["size"] = C.d.abs().round(2)
    rows = []
    ag = {k: g.sort_values("s") for k, g in A.groupby(["a", "side", "p"])}
    for r in C.itertuples():
        g = ag.get((r.a, r.side, r.p))
        if g is None:
            continue
        s = g.s.to_numpy()
        lo, hi = np.searchsorted(s, r.s + 1290), np.searchsorted(s, r.s + 1730)
        for j in range(lo, hi):
            row = g.iloc[j]
            if abs(row["size"] - r.size) > 0.02:
                continue
            dt = row.s - r.s
            for nm, (a, b) in WIN.items():
                if a <= dt < b:
                    rows.append({"win": nm, "owner": row.owner, "size": float(r.size), "whole": bool(row.whole),
                                 "F_mkt": bool(row.F_mkt), "in_burst": bool(row.in_burst), "slug": row.slug,
                                 "maker": row.maker if isinstance(row.maker, str) else None})
    P = pd.DataFrame(rows)
    P["szc"] = np.where(P["size"] == 100, "100", np.where(P.F_mkt, "wallet_odd", "other_size"))
    res = {"pairs": int(len(P))}

    def tab(df):
        t = df.groupby("win").size().reindex(list(WIN), fill_value=0)
        sp, ctl = int(t["spike"]), (int(t["ctrl_lo"]) + int(t["ctrl_hi"])) / 2
        return {"spike": sp, "ctrl_mean": ctl, "excess": round(sp - ctl, 1), "ratio": round(sp / ctl, 2) if ctl else None}

    res["all"] = tab(P)
    res["by_size_class"] = {k: tab(g) for k, g in P.groupby("szc")}
    res["by_owner_of_readd"] = {k: tab(g) for k, g in P.groupby("owner")}
    res["by_owner_size100"] = {k: tab(g) for k, g in P[P.szc == "100"].groupby("owner")}
    res["by_slug_size100"] = {k: tab(g) for k, g in P[P.szc == "100"].groupby("slug")}
    sp = P[(P.win == "spike") & (P.owner == "other")]
    res["other_owner_makers_in_spike"] = sp.maker.str[:10].value_counts().head(8).to_dict()
    (RES / f"timer_attrib{SUF}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
