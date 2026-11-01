"""directional-maker iteration 15, T5-fit (X163 / X169 fitted form, post hoc on the current block; see pub_unit.py for the unit).
Original docstring of pub_unit.py follows.

directional-maker iteration 15, T5 (X163 information I14-1 / X169 mechanics P2): the publish-anchored quote unit.

Pre-registered in NOTES (about 07:27 UTC 11-01), no fitting. Units: (BTC 5m/15m window w live at P_i, outcome s, public
Chainlink publish P_i from dy_rtds 'P'). Label Q: an at-touch add of a schedule size on s in [P_i, P_i + 300 ms)
(full-depth dm_clob_raw; Up bid add at the best bid -> Up, Up ask add at the best ask -> Down), non-extreme bids only
(0.03 < bid < 0.97); classes 'sched' = {62, 100, 250, 500} and '500' alone. Scores at P_i (point in time: report i is
public at P_i; the book and futures strictly before P_i):
  rule_level = sgn_s x (F_i - mid), F_i = Phi((v_i - K) / (1.0 x futures sigma300 x sqrt(tau)));
  rule_change = sgn_s x (F_i - F_{i-1}) (what the new report changed);
  act_when = number of mid changes of w in [P_i - 1 s, P_i); act_which = sgn_s x (mid(P_i) - mid(P_i - 1 s)).
Placebo: the same scores against the label in [P_i - 300 ms, P_i) (before report i is public).
AUC pooled over cells; WHICH = accuracy of sign(rule_level) on the (w, i) with a post on exactly one outcome.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code15/pub_unit.py <start> <end>
"""
from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code14"))
from lagged_quote import fut_mid, at, sec_sigma, live  # noqa: E402

SCHED = {62.0, 100.0, 250.0, 500.0}


def main(a, b):
    book, adds, mids = {}, [], []
    lastm = {}
    for h in range(a - a % 3600, b, 3600):
        try:
            for r in live.iter_live("dm_clob_raw", max(h, a), min(h + 3600, b)):
                k = r.get("k")
                if k == "bk":
                    bw = {1: {}, 0: {}}
                    for p, z in r.get("b", []):
                        bw[1][round(p, 3)] = z
                    for p, z in r.get("o", []):
                        bw[0][round(p, 3)] = z
                    book[r["w"]] = bw
                elif k == "pc":
                    w = r["w"]; s = r["s"]; bw = book.get(w)
                    if bw is None:
                        continue
                    for row in r["c"]:
                        sd, p, z = row[0], round(row[1], 3), row[2]
                        if sd >= 2:
                            continue
                        old = bw[sd].get(p, 0.0)
                        bw[sd][p] = z
                        bb, ba = row[3], row[4]
                        mm = (bb + ba) / 2
                        if lastm.get(w) != mm:
                            lastm[w] = mm
                            mids.append((w, s, mm))
                        dz = round(z - old, 2)
                        if dz in SCHED and ((sd == 1 and abs(p - bb) < 1e-9) or (sd == 0 and abs(p - ba) < 1e-9)):
                            adds.append((w, s, sd, p, dz))
        except (zlib.error, EOFError, OSError) as e:
            print("read stop in hour", h, repr(e)[:60])
    A = pd.DataFrame(adds, columns=["w", "s", "sd", "p", "dz"])
    Mi = pd.DataFrame(mids, columns=["w", "s", "mid"]).sort_values(["w", "s"], kind="stable")
    A["bid"] = np.where(A.sd == 1, A.p, 1 - A.p)
    A = A[(A.bid > 0.03) & (A.bid < 0.97)]
    print("non-extreme schedule adds", len(A), A.dz.value_counts().to_dict(), "windows", Mi.w.nunique(), flush=True)
    pub = []
    for r in live.iter_live("dy_rtds", a - 60, b):
        if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
            pub.append((int(r["P"]), int(r["ts"]) // 1000, float(r["v"])))
    Pb = pd.DataFrame(pub, columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts").sort_values("P").reset_index(drop=True)
    Pb = Pb[(Pb.P >= a * 1000) & (Pb.P < b * 1000)].reset_index(drop=True)
    Pb["v_prev"] = Pb.v.shift(1)
    E, M = fut_mid(a - 600, b)
    sig = sec_sigma(E, M, 300)
    from polyrea.workflows.updown_study import fetch_windows
    wins = sorted(set(Mi.w))
    raw = fetch_windows(wins)
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    cells = []
    for w in wins:
        if w not in K:
            continue
        st = int(w.rsplit("-", 1)[1]); en = st + (900 if "-15m-" in w else 300)
        g = Mi[Mi.w == w]; ms, mv = g.s.to_numpy(np.int64), g.mid.to_numpy(float)
        live_ = Pb[(Pb.P >= st * 1000 + 5000) & (Pb.P < en * 1000 - 1000)]
        if not len(live_):
            continue
        P = live_.P.to_numpy(np.int64)
        mid0 = at(ms, mv, P - 1); m1 = at(ms, mv, P - 1000); m5 = at(ms, mv, P - 5000)
        c025 = np.searchsorted(ms, P, side="left") - np.searchsorted(ms, P - 250, side="left")
        c1 = np.searchsorted(ms, P, side="left") - np.searchsorted(ms, P - 1000, side="left")
        c5 = np.searchsorted(ms, P, side="left") - np.searchsorted(ms, P - 5000, side="left")
        tau = np.maximum(en - P / 1000.0, 1.0)
        s0 = sig.reindex(P // 1000 - 1).to_numpy(float)
        Fi = norm.cdf((live_.v.to_numpy(float) - K[w]) / (s0 * np.sqrt(tau)))
        Fp = norm.cdf((live_.v_prev.to_numpy(float) - K[w]) / (s0 * np.sqrt(tau)))
        ga = A[A.w == w]
        for sd_, sgn in ((1, 1.0), (0, -1.0)):
            ts5 = np.sort(ga[(ga.sd == sd_) & (ga.dz == 500.0)].s.to_numpy(np.int64))
            q5 = np.searchsorted(ts5, P + 300, side="left") - np.searchsorted(ts5, P, side="left")
            qb5 = np.searchsorted(ts5, P, side="left") - np.searchsorted(ts5, P - 300, side="left")
            lev = mid0 if sd_ == 1 else 1 - mid0
            for j in range(len(P)):
                cells.append((w, j, sd_, P[j], tau[j], lev[j], sgn * (mid0[j] - m1[j]), sgn * (mid0[j] - m5[j]), c025[j], c1[j], c5[j],
                              sgn * (Fi[j] - mid0[j]), sgn * (Fi[j] - Fp[j]), abs(Fi[j] - mid0[j]), int(q5[j] > 0), int(qb5[j] > 0)))
    D = pd.DataFrame(cells, columns=["w", "i", "sd", "P", "tau", "lev", "d1", "d5", "c025", "c1", "c5", "rule_level", "rule_change",
                                     "abs_edge", "y", "y_before"]).dropna(subset=["rule_level", "d1"]).sort_values("P").reset_index(drop=True)
    import lightgbm as lgb
    ACT = ["tau", "lev", "d1", "d5", "c025", "c1", "c5"]
    REF = ACT + ["rule_level", "rule_change", "abs_edge"]
    cut = int(np.quantile(D.P, 0.6))
    tr, te = D[D.P < cut], D[D.P >= cut]
    out = {"span": [a, b], "cells": int(len(D)), "pos": int(D.y.sum()), "train_pos": int(tr.y.sum()), "test_pos": int(te.y.sum())}
    prm = dict(objective="binary", num_leaves=7, learning_rate=0.05, min_data_in_leaf=50, max_bin=63, verbose=-1, feature_fraction=0.9)
    preds = {}
    for nm, cols in (("activity", ACT), ("activity_ref", REF)):
        for lab in ("y", "y_before"):
            m = lgb.train(prm, lgb.Dataset(tr[cols], tr[lab]), num_boost_round=200)
            p = m.predict(te[cols]); preds[(nm, lab)] = p
            out[f"{nm}_{lab}"] = round(float(roc_auc_score(te[lab], p)), 4) if 0 < te[lab].sum() < len(te) else None
    # 10-min block bootstrap of the gain on the test part
    blk = (te.P // 600000).to_numpy(); ub = np.unique(blk); rng = np.random.default_rng(0); gains = []
    yv = te.y.to_numpy(); pa, pr = preds[("activity", "y")], preds[("activity_ref", "y")]
    for _ in range(400):
        sel = np.concatenate([np.where(blk == u)[0] for u in rng.choice(ub, len(ub))])
        if 0 < yv[sel].sum() < len(sel):
            gains.append(roc_auc_score(yv[sel], pr[sel]) - roc_auc_score(yv[sel], pa[sel]))
    out["gain_y"] = round(out["activity_ref_y"] - out["activity_y"], 4) if out["activity_y"] else None
    out["gain_y_boot95"] = [round(float(np.percentile(gains, 2.5)), 4), round(float(np.percentile(gains, 97.5)), 4)] if gains else None
    out["gain_placebo_before"] = round(out["activity_ref_y_before"] - out["activity_y_before"], 4) if out["activity_y_before"] else None
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / f"iter15_pub_fit_{a}_{b}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
