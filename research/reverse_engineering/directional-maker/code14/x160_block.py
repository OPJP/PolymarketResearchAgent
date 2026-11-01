"""directional-maker iteration 14, X160 runner: replicate the frozen event-time QUOTE presence (models fitted on 10-31
14-16 by code14/pres_quote.py, saved in code14/models/) and the frozen quote-unit side (code14/qu_dx.py) on any later
development span, from the slim exam recorder only (dx_clob 'pc' schedule-size deltas with the record's touch and 'x'
trades with tx hashes; dx_bnf / dm_bnf futures; Chainlink via cl_source; Gamma priceToBeat) plus the cluster's activity
(tx hashes, to drop cluster transactions from the activity features). No refit.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/x160_block.py <start> <end>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT))
import qu_dx  # noqa: E402
from qu_dx import _iter, _fut, _at, cl_source  # noqa: E402

CLU = ["0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
       "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"]
ACT = ["rel", "is15", "s_up", "last", "age", "lasthit_s", "mid_s", "n1", "n2", "n5", "n10", "n30",
       "sold1", "sold5", "sold10", "bought1", "bought5", "bought10"]
REF = ["edge_cl", "dF_cl", "new_rep", "fut1", "fut3", "edge_fut"]


def cluster_txs(a, b):
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData(); hs = set()
    for w in CLU:
        act, _, _ = pm.activity(w, start=a - 600, end=b)
        hs |= {str(r.get("transactionHash") or "").lower() for r in act}
    return hs


def quote_presence(a, b, allow_sealed=False, intervals=None, with_side=True):
    """Frozen event-time quote presence (and the quote-unit side) on [a, b); windows starting in `intervals` only."""
    adds, mids, xs, last = [], [], [], {}
    for r in _iter("dx_clob", a - 60, b, allow_sealed):
        k = r.get("k"); w = r.get("w") or ""
        if not w.startswith(("btc-updown-5m-", "btc-updown-15m-")):
            continue
        if k == "pc":
            bb, ba, s = r.get("bb"), r.get("ba"), r.get("s")
            if bb is None or ba is None or not s:
                continue
            mm = (bb + ba) / 2
            if last.get(w) != mm:
                last[w] = mm; mids.append((w, s, mm))
            for row in r.get("c") or []:
                if len(row) >= 4 and round(row[3], 2) in (500.0, 1000.0) and (
                        (row[0] == 1 and abs(round(row[1], 3) - bb) < 1e-9) or (row[0] == 0 and abs(round(row[1], 3) - ba) < 1e-9)):
                    adds.append((w, s, row[0]))
        elif k == "x":
            xs.append((w, r.get("s"), int(r.get("ai", -1)), float(r.get("p") or 0), float(r.get("z") or 0), str(r.get("d")),
                       (r.get("h") or "").lower()))
    if not mids:
        return {"cells": 0, "note": "no dx_clob records in the period"}
    A = pd.DataFrame(adds, columns=["w", "s", "sd"])
    Mi = pd.DataFrame(mids, columns=["w", "s", "mid"]).sort_values(["w", "s"], kind="stable")
    X = pd.DataFrame(xs, columns=["w", "s", "ai", "p", "z", "d", "h"]).sort_values("s", kind="stable")
    ctx = cluster_txs(a, b)
    X["cl"] = X.h.isin(ctx)
    clean = X[~X.cl].drop_duplicates("h").copy()
    d_ = clean.d.str.upper().str[0]
    clean["hit_up"] = (((clean.ai == 0) & (d_ == "S")) | ((clean.ai == 1) & (d_ == "B"))).astype(int)
    clean["p_up"] = np.where(clean.ai == 0, clean.p, 1 - clean.p)
    E, M = _fut(a - 3600, b, allow_sealed)
    s0, s1 = int(E[0] // 1000), int(E[-1] // 1000) + 1
    secs = np.arange(s0, s1 + 1)
    sig = pd.Series(np.diff(_at(E, M, secs * 1000 + 999), prepend=np.nan), index=secs).rolling(300, min_periods=150).std().shift(1)
    clv = cl_source.cl_values(list(range(a - 10, b + 1)), allow_sealed=allow_sealed, fetch=True, max_requests=300)
    from polyrea.workflows.updown_study import fetch_windows
    wins = sorted(w for w in set(Mi.w) if a <= int(w.rsplit("-", 1)[1]) < b)
    if intervals:
        wins = [w for w in wins if any(lo <= int(w.rsplit("-", 1)[1]) < hi for lo, hi in intervals)]
    raw = fetch_windows(wins); K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    rows = []
    for w in wins:
        st = int(w.rsplit("-", 1)[1]); L = 900 if "-15m-" in w else 300
        if st + L > b + 1 or w not in K:
            continue
        T = (st + np.arange(L)) * 1000
        g = clean[clean.w == w]; gs = g.s.to_numpy(np.int64); gz = g.z.to_numpy(float); gh = g.hit_up.to_numpy(int); gp = g.p_up.to_numpy(float)
        mb = Mi[Mi.w == w]; mid_up = _at(mb.s.to_numpy(np.int64), mb.mid.to_numpy(float), T - 1)
        lp = _at(gs, gp, T - 1)
        j = np.searchsorted(gs, T, side="left") - 1
        age = np.where(j >= 0, (T - gs[np.clip(j, 0, None)]) / 1000, 999.0)
        lasthit = np.where(j >= 0, gh[np.clip(j, 0, None)], -1)
        cz = np.concatenate([[0], np.cumsum(gz)]); czu = np.concatenate([[0], np.cumsum(gz * gh)])
        feats = {}
        for win in (1, 2, 5, 10, 30):
            i0 = np.searchsorted(gs, T - win * 1000, side="left"); i1 = np.searchsorted(gs, T, side="left")
            feats[f"n{win}"] = i1 - i0
            if win in (1, 5, 10):
                feats[f"zup{win}"] = czu[i1] - czu[i0]; feats[f"zdn{win}"] = (cz[i1] - cz[i0]) - (czu[i1] - czu[i0])
        cl0 = clv.reindex((T - 1432) // 1000).to_numpy(float); cl1 = clv.reindex((T - 2432) // 1000).to_numpy(float)
        sg = sig.reindex(T // 1000).to_numpy(float)
        tau = np.maximum(st + L - T / 1000, 1.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            F0 = norm.cdf((cl0 - K[w]) / (sg * np.sqrt(tau))); F1 = norm.cdf((cl1 - K[w]) / (sg * np.sqrt(tau)))
            f0 = _at(E, M, T - 50); f1 = _at(E, M, T - 1000); f3 = _at(E, M, T - 3000)
            Kf = np.nanmean(_at(E, M, (st - 60 + np.arange(60)) * 1000))
            Ff = norm.cdf((f0 - Kf) / (sg * 1.4 * np.sqrt(tau)))
        aw = A[A.w == w]
        for s_up in (1, 0):
            sgn = 1 if s_up else -1
            lab = np.zeros(L, int)
            k_ = ((aw[aw.sd == s_up].s.to_numpy(np.int64) - st * 1000) // 1000).astype(int)
            lab[k_[(k_ >= 0) & (k_ < L)]] = 1
            m_s = mid_up if s_up else 1 - mid_up
            r = pd.DataFrame({"y": lab, "w": w, "T": T // 1000, "rel": np.arange(L), "is15": int(L == 900), "s_up": s_up,
                              "last": lp if s_up else 1 - lp, "age": age,
                              "lasthit_s": np.where(lasthit < 0, -1, (lasthit == s_up).astype(int)), "mid_s": m_s,
                              "edge_cl": (F0 if s_up else 1 - F0) - m_s, "dF_cl": (F0 - F1) * sgn,
                              "new_rep": (np.abs(cl0 - cl1) > 1e-9).astype(int), "fut1": (f0 - f1) * sgn, "fut3": (f0 - f3) * sgn,
                              "edge_fut": (Ff if s_up else 1 - Ff) - m_s})
            for k2, v in feats.items():
                if k2.startswith("zup"):
                    r[("sold" if s_up else "bought") + k2[3:]] = v
                elif k2.startswith("zdn"):
                    r[("bought" if s_up else "sold") + k2[3:]] = v
                else:
                    r[k2] = v
            rows.append(r)
    if not rows:
        return {"cells": 0, "note": "no BTC 5m / 15m windows with dx_clob records and a strike in the period"}
    D = pd.concat(rows, ignore_index=True)
    D = D[D.mid_s.notna()]
    import lightgbm as lgb
    out = {"span": [a, b], "cells": int(len(D)), "positives": int(D.y.sum()), "windows": int(D.w.nunique()),
           "cluster_txs_dropped": int(X.cl.sum())}
    if D.y.nunique() == 2:
        for nm, cols in (("activity", ACT), ("activity_ref", ACT + REF), ("activity_chainlink", ACT + ["edge_cl", "dF_cl", "new_rep"])):
            m = lgb.Booster(model_file=str(HERE / "models" / f"quote_presence_{nm}.txt"))
            out[nm] = float(roc_auc_score(D.y, m.predict(D[cols])))
        out["gain"] = out["activity_ref"] - out["activity"]
        # decomposition: WHEN (a post on either outcome in the second) vs WHICH outcome (cells with a post on exactly one)
        D2 = D[["w", "rel", "s_up", "y"]].copy()
        for nm, cols in (("activity", ACT), ("activity_ref", ACT + REF)):
            D2[nm] = lgb.Booster(model_file=str(HERE / "models" / f"quote_presence_{nm}.txt")).predict(D[cols])
        g = D2.groupby(["w", "rel"]).agg(y=("y", "max"), a=("activity", "max"), r=("activity_ref", "max"))
        out["when_either_outcome"] = {"activity": float(roc_auc_score(g.y, g.a)), "activity_ref": float(roc_auc_score(g.y, g.r)),
                                      "seconds": int(len(g)), "pos_rate": float(g.y.mean())}
        pv = D2.pivot_table(index=["w", "rel"], columns="s_up", values=["y", "activity", "activity_ref"])
        one = pv[(pv["y"][1] + pv["y"][0]) == 1]
        out["which_outcome_one_sided_seconds"] = {"n": int(len(one)),
                                                  "activity": float(((one["activity"][1] > one["activity"][0]) == (one["y"][1] == 1)).mean()),
                                                  "activity_ref": float(((one["activity_ref"][1] > one["activity_ref"][0]) == (one["y"][1] == 1)).mean())}
    out["model"] = "code14/models/quote_presence_*.txt, LightGBM fitted on 10-31 14-16 (code14/pres_quote.py LAG 1432 ms, point-in-time safe), no refit"
    if with_side:
        out["quote_unit_side"] = qu_dx.quote_unit_side(a, b, allow_sealed=allow_sealed, intervals=intervals)
    return out


def main(a, b, allow_sealed=False):
    out = quote_presence(a, b, allow_sealed=allow_sealed)
    (HERE.parent / "results" / f"iter14_x160_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "quote_unit_side"}, indent=1, default=float))
    print("quote_unit_side", (out.get("quote_unit_side") or {}).get("side_accuracy"))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
