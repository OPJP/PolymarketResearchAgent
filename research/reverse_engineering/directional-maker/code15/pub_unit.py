"""directional-maker iteration 15, T5 (X163 information I14-1 / X169 mechanics P2): the publish-anchored quote unit.

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
        mid0 = at(ms, mv, P - 1); mid1 = at(ms, mv, P - 1000)
        nchg = np.searchsorted(ms, P, side="left") - np.searchsorted(ms, P - 1000, side="left")
        tau = np.maximum(en - P / 1000.0, 1.0)
        s0 = sig.reindex(P // 1000 - 1).to_numpy(float)
        Fi = norm.cdf((live_.v.to_numpy(float) - K[w]) / (s0 * np.sqrt(tau)))
        Fp = norm.cdf((live_.v_prev.to_numpy(float) - K[w]) / (s0 * np.sqrt(tau)))
        ga = A[A.w == w]
        for sd_, sgn in ((1, 1.0), (0, -1.0)):
            ts = np.sort(ga[ga.sd == sd_].s.to_numpy(np.int64))
            ts5 = np.sort(ga[(ga.sd == sd_) & (ga.dz == 500.0)].s.to_numpy(np.int64))
            q = np.searchsorted(ts, P + 300, side="left") - np.searchsorted(ts, P, side="left")
            q5 = np.searchsorted(ts5, P + 300, side="left") - np.searchsorted(ts5, P, side="left")
            qb = np.searchsorted(ts, P, side="left") - np.searchsorted(ts, P - 300, side="left")
            qb5 = np.searchsorted(ts5, P, side="left") - np.searchsorted(ts5, P - 300, side="left")
            ql5 = np.searchsorted(ts5, P + 600, side="left") - np.searchsorted(ts5, P + 300, side="left")
            for j in range(len(P)):
                cells.append((w, j, sd_, sgn * (Fi[j] - mid0[j]), sgn * (Fi[j] - Fp[j]), nchg[j], sgn * (mid0[j] - mid1[j]),
                              int(q[j] > 0), int(q5[j] > 0), int(qb[j] > 0), int(qb5[j] > 0), int(ql5[j] > 0), P[j]))
    D = pd.DataFrame(cells, columns=["w", "i", "sd", "rule_level", "rule_change", "act_when", "act_which", "y", "y500", "y_before",
                                     "y500_before", "y500_later", "P"])
    D = D.dropna(subset=["rule_level", "act_which"])
    out = {"span": [a, b], "cells": int(len(D)), "pos_sched": int(D.y.sum()), "pos_500": int(D.y500.sum()),
           "pos_before": int(D.y_before.sum()), "pos_500_before": int(D.y500_before.sum()), "pos_500_later": int(D.y500_later.sum()), "publishes": int(len(Pb)), "windows": int(D.w.nunique())}

    def auc(y, s):
        y = np.asarray(y); s = np.asarray(s, float)
        ok = np.isfinite(s)
        return round(float(roc_auc_score(y[ok], s[ok])), 4) if ok.sum() and 0 < y[ok].sum() < ok.sum() else None
    for lab in ("y", "y500", "y_before", "y500_before", "y500_later"):
        out[lab] = {"rule_level": auc(D[lab], D.rule_level), "rule_change": auc(D[lab], D.rule_change),
                    "act_when": auc(D[lab], D.act_when), "act_which": auc(D[lab], D.act_which),
                    "rule_level_plus_when": auc(D[lab], D.rule_level.rank(pct=True) + D.act_when.rank(pct=True)),
                    "act_which_plus_when": auc(D[lab], D.act_which.rank(pct=True) + D.act_when.rank(pct=True))}
    # WHICH: (w, i) with a post on exactly one outcome
    for lab in ("y", "y500", "y_before", "y500_before", "y500_later"):
        g = D.groupby(["w", "i"])
        one = g[lab].transform("sum") == 1
        x = D[one & (D[lab] == 1)]
        out[f"which_{lab}"] = {"n": int(len(x)), "rule_level_sign": round(float((x.rule_level > 0).mean()), 4) if len(x) else None,
                               "act_which_sign": round(float((x.act_which > 0).mean()), 4) if len(x) else None,
                               "rule_change_sign": round(float((x.rule_change > 0).mean()), 4) if len(x) else None}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / f"iter15_pub_unit_{a}_{b}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
