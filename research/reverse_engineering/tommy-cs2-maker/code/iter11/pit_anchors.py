"""X152 (mechanics panel iter-10 P4): every own-state price anchor re-derived POINT-IN-TIME on the on-chain record.

Rows: the wallet's filled maker orders (ledger_rows_iter10: 24,180 orders, 16-22 Oct, development), with the iteration-10
anchors a_last (last public print, rounded to the cent) and a_own (previous FILLED own order on the token by signing
time, which needs that order's later fill: a censoring lookahead).
Point-in-time versions (inputs with block time <= the order's signing time only):
  own_pit      price of the own order on the token whose FIRST fill block time is the latest one <= sign time
               (the own level the chain had revealed at signing);
  own_pit_last price of the own order on the token whose LAST fill block time is the latest one <= sign time;
  own_nosweep  the fill-selected a_own, but skipping predecessors whose first fill is in the same block as this order's
               first fill (same-sweep co-fills excluded): still not point-in-time, shows the sweep share;
  union_pit    oracle union {own_pit, last print} (an upper bound of any rule choosing between the two).
Within one tick = 1c for anchors in [0.04, 0.96], else 0.1c (as iteration 10). BUILD (game start < 10-21) and
VALIDATE separately, plus the persistence-by-gap table with the point-in-time anchor.
Output: results/pit_anchors.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
C = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
VAL0, H = 1792540800, 1792713600


def wt(p, a):
    p, a = np.asarray(p, float), np.asarray(a, float)
    ok = np.isfinite(a) & np.isfinite(p)
    if not ok.any():
        return None, 0
    tick = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
    return round(float((np.abs(p - a) <= tick + 1e-9)[ok].mean()), 3), int(ok.sum())


def main():
    L = pd.read_parquet(C / "ledger_rows_iter10.parquet")
    o = pd.read_parquet(C / "orders.parquet", columns=["salt", "token_id", "first_fill_ts", "last_fill_ts", "sign_ts", "role"])
    o = o[o.role == "maker"]
    L = L.merge(o[["salt", "token_id", "first_fill_ts", "last_fill_ts", "sign_ts"]], on="salt", how="left")
    L = L.sort_values(["token_id", "sign_ms"]).reset_index(drop=True)
    own_pit = np.full(len(L), np.nan)
    own_pit_last = np.full(len(L), np.nan)
    own_nosweep = np.full(len(L), np.nan)
    gap_pit = np.full(len(L), np.nan)
    for tok, g in L.groupby("token_id", sort=False):
        idx = g.index.to_numpy()
        st = g.sign_ts.to_numpy(float)
        ff = g.first_fill_ts.to_numpy(float)
        lf = g.last_fill_ts.to_numpy(float)
        pr = g.price.to_numpy(float)
        # point-in-time: among orders with first fill <= sign time (strictly earlier block second), latest first fill
        of = np.argsort(ff, kind="stable")
        ffs, prs, sts = ff[of], pr[of], st[of]
        ol = np.argsort(lf, kind="stable")
        lfs, prl = lf[ol], pr[ol]
        for k in range(len(idx)):
            j = np.searchsorted(ffs, np.floor(st[k]), side="right") - 1
            if j >= 0:
                own_pit[idx[k]] = prs[j]
                gap_pit[idx[k]] = st[k] - sts[j]
            j2 = np.searchsorted(lfs, np.floor(st[k]), side="right") - 1
            if j2 >= 0:
                own_pit_last[idx[k]] = prl[j2]
            # fill-selected predecessor excluding same-block co-fills
            for q in range(k - 1, -1, -1):
                if ff[q] != ff[k]:
                    own_nosweep[idx[k]] = pr[q]
                    break
    L["own_pit"], L["own_pit_last"], L["own_nosweep"], L["gap_pit"] = own_pit, own_pit_last, own_nosweep, gap_pit
    L["gap_fs"] = L.groupby("token_id").sign_ms.diff() / 1000.0
    out = {}
    for name, sub in (("BUILD", L[L.gs_ts < VAL0]), ("VALIDATE", L[(L.gs_ts >= VAL0) & (L.gs_ts < H)])):
        p = sub.price.to_numpy(float)
        r = {"orders": int(len(sub))}
        for nm, col in (("last_print", "a_last"), ("own_prev_fill_selected", "a_own"), ("own_pit_first_fill", "own_pit"),
                        ("own_pit_last_fill", "own_pit_last"), ("own_prev_no_same_block", "own_nosweep")):
            r[nm] = wt(p, sub[col])
        a, b = sub.own_pit.to_numpy(float), sub.a_last.to_numpy(float)
        tick_a = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
        tick_b = np.where((b >= 0.04) & (b <= 0.96), 0.01, 0.001)
        ok = np.isfinite(a) | np.isfinite(b)
        hit = (np.isfinite(a) & (np.abs(p - a) <= tick_a + 1e-9)) | (np.isfinite(b) & (np.abs(p - b) <= tick_b + 1e-9))
        r["oracle_union_pit_and_last"] = round(float(hit[ok].mean()), 3)
        a2 = sub.a_own.to_numpy(float)
        t2 = np.where((a2 >= 0.04) & (a2 <= 0.96), 0.01, 0.001)
        hit2 = (np.isfinite(a2) & (np.abs(p - a2) <= t2 + 1e-9)) | (np.isfinite(b) & (np.abs(p - b) <= tick_b + 1e-9))
        r["oracle_union_fill_selected_and_last (iteration 10, 0.599)"] = round(float(hit2[ok].mean()), 3)
        # persistence by the gap since the predecessor (fill-selected gap vs point-in-time gap)
        gt = {}
        for lo, hi in ((0, 2), (2, 10), (10, 60), (60, 1e9)):
            m1 = (sub.gap_fs >= lo) & (sub.gap_fs < hi)
            m2 = (sub.gap_pit >= lo) & (sub.gap_pit < hi)
            gt[f"{lo}-{hi if hi < 1e9 else 'inf'}s"] = {"fill_selected": [wt(p[m1.to_numpy()], sub.a_own[m1])[0], int(m1.sum())],
                                                       "pit": [wt(p[m2.to_numpy()], sub.own_pit[m2])[0], int(m2.sum())]}
        r["persistence_by_gap"] = gt
        r["share_same_block_as_predecessor"] = round(float(np.mean(sub.groupby("token_id").first_fill_ts.diff().fillna(1) == 0)), 3)
        out[name] = r
    (RES / "pit_anchors.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
