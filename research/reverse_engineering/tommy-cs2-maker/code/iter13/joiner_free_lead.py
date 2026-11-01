"""X186 / X182 step 2 (assumptions panel iter-12 P3): the lead of its quote level on a JOINER-FREE others' mid.
BUILD-live (10-31 12-18). Joiners = non-own BUY adds at its new top price +-1c on the same token within (0, 2] s after
any of its add bursts (own_bursts_dev), as in follower_census.py. The others' mid is rebuilt from the recording with
the iteration-7 builder (code/iter7/untriggered_v2.mids_from_feed) with those joiner adds treated like own adds
(excluded from the others' book until cancelled). Then the iteration-9 statistic (add_level_info.py): Spearman of the
add's offset from the mid 100 ms before against the mid move to +2 / +10 / +30 s, for its adds vs other makers' adds,
on the original and the joiner-free mid.
Output: results/joiner_free_lead.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter7"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import untriggered_v2 as U  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def lead(A, mids):
    rows = []
    for r in A.itertuples():
        x = mids.get(r.a)
        if x is None:
            continue
        ts, md = x
        j0 = np.searchsorted(ts, r.s - 100, side="right") - 1
        if j0 < 0:
            continue
        tok0 = r.side == "BUY"
        bid = r.p if tok0 else 1 - r.p
        m0 = md[j0] if tok0 else 1 - md[j0]
        rec = {"own": bool(r.vown), "off": (bid - m0) * 100}
        for hh in (2, 10, 30):
            j = np.searchsorted(ts, r.s + hh * 1000, side="right") - 1
            mh = md[j] if tok0 else 1 - md[j]
            rec[f"dm{hh}"] = (mh - m0) * 100
        rows.append(rec)
    X = pd.DataFrame(rows)
    X = X[np.isfinite(X.off) & (X.off.abs() <= 15)]
    o, p = X[X.own], X[~X.own]
    return {f"h{hh}s": {"own": round(float(spearmanr(o.off, o[f"dm{hh}"])[0]), 4), "other": round(float(spearmanr(p.off, p[f"dm{hh}"])[0]), 4)}
            for hh in (2, 10, 30)} | {"own_adds": int(len(o)), "other_adds": int(len(p))}


def main():
    A = pd.read_parquet(OUT / "linked_adds_dev.parquet")
    A["a"] = A.a.astype(str)
    A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
    books = set(A.a)
    own_sz = {a: set(g["size"]) for a, g in A[A.vown].groupby("a")}
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in A[A.vown].itertuples()}
    # joiners from the level events
    ob = pd.read_parquet(OUT / "own_bursts_dev.parquet")
    ob["a"] = ob.a.astype(str)
    le = pd.read_parquet(OUT / "level_events_dev.parquet", columns=["a", "s", "side", "p", "kind", "size"])
    le["a"] = le.a.astype(str)
    adds = le[(le.kind == "add")]
    own_t = {a: np.sort(g.s.to_numpy(float)) for a, g in ob.groupby("a")}
    jset = set()
    oa = ob[(ob.kind == "add")]
    by = {(a, sd): g.sort_values("s") for (a, sd), g in adds.groupby(["a", "side"])}
    for r in oa.itertuples():
        g = by.get((r.a, r.side))
        if g is None:
            continue
        ss = g.s.to_numpy(float)
        i0, i1 = np.searchsorted(ss, r.s, side="right"), np.searchsorted(ss, r.s + 2000, side="right")
        if i1 <= i0:
            continue
        sub = g.iloc[i0:i1]
        sub = sub[np.abs(sub.p.astype(float) - float(r.pmax)) <= 0.0101]
        arr = own_t.get(r.a, np.array([]))
        for x in sub.itertuples():
            k = np.searchsorted(arr, x.s)
            dmin = min(abs(x.s - arr[k - 1]) if k > 0 else 1e9, abs(arr[k] - x.s) if k < len(arr) else 1e9)
            if dmin > 3:
                jset.add((x.a, x.side, round(float(x.p), 3), int(x.s)))
    M0 = pd.read_parquet(OUT / "others_mid_dev.parquet")
    M0["a"] = M0.a.astype(str)
    mids0 = {a: (g.s.to_numpy(float), g.mid.to_numpy(float)) for a, g in M0.groupby("a")}
    M1 = U.mids_from_feed(books, vset | jset, own_sz)
    mids1 = {a: (np.asarray(v[0], float), np.asarray(v[1], float)) for a, v in M1.items() if len(v[0])}
    Aa = A[A.kind == "add"]
    out = {"joiner_levels_removed": len(jset), "original_mid": lead(Aa, mids0), "joiner_free_mid": lead(Aa, mids1)}
    (RES / "joiner_free_lead.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
