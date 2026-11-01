"""Iteration 8, X111 (mechanics panel iter7 P5): one stream or two? The wallet - P4e signing lag on co-signed takes
(same token, P4e within [-120, +20] ms of the wallet) by event class, against the 0x2005d16a - P4e lag as a
subscriber-to-subscriber control. Class of the burst: reversal (previous census burst in the market 5-120 s earlier
on the other outcome), follow-on (same outcome), isolated (none). Fixed terms: class, price tercile of the take, P4e
multi-order cluster (>= 2 P4e orders on the token within +-500 ms), day; random effect: event. Signature of one
fan-out with a kind filter (A): no class effect (< 10 ms) and no order-count effect. Two detectors (B): a
class-dependent offset >= 20 ms. Historical 16-22 Oct full matched-order record. Output: results/lag_by_class.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter7"))
import coreceivers as CR  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = CR.W
P4E, R2 = "0x4ebc2722", "0x2005d16a"


def classify(cb_by_cid, cid, t, oi):
    b = cb_by_cid.get(cid)
    if b is None:
        return "isolated"
    t0, o = b
    m = (t0 <= t - 5) & (t0 >= t - 120)
    if not m.any():
        return "isolated"
    j = np.where(m)[0][-1]
    return "reversal" if o[j] != oi else "follow_on"


def pairs(T, lead, follow, lo, hi, cb_by_cid):
    g = {k: v.sign_ms.to_numpy() for k, v in T[T.maker.str.startswith(lead)].groupby("token_id")}
    rows = []
    for r in T[T.maker.str.startswith(follow)].itertuples():
        a = g.get(r.token_id)
        if a is None:
            continue
        x = a - r.sign_ms
        mm = (x >= lo) & (x <= hi)
        if not mm.any():
            continue
        c = (lo + hi) / 2
        d = float(x[mm][np.argmin(np.abs(x[mm] - c))])
        nlead = int(((x >= -500) & (x <= 500)).sum())
        rows.append({"d": -d, "event": r.event, "cid": r.cid, "price": float(r.price), "nlead": nlead,
                     "day": pd.to_datetime(r.sign_ms, unit="ms").strftime("%m-%d"),
                     "cls": classify(cb_by_cid, r.cid, r.sign_ms / 1000, int(r.oi))})
    D = pd.DataFrame(rows)
    D["pt3"] = pd.qcut(D.price, 3, labels=["low", "mid", "high"]).astype(str)
    D["multi"] = np.where(D.nlead >= 2, "multi", "single")
    return D


def fit(D):
    import statsmodels.formula.api as smf
    o = {"n": int(len(D)), "events": int(D.event.nunique()), "median_lag_ms": round(float(D.d.median()), 1),
         "by_class": D.groupby("cls").d.agg(["count", "median", "mean"]).round(1).to_dict("index"),
         "by_multi": D.groupby("multi").d.agg(["count", "median"]).round(1).to_dict("index"),
         "by_price": D.groupby("pt3").d.agg(["count", "median"]).round(1).to_dict("index")}
    try:
        m = smf.mixedlm("d ~ C(cls, Treatment('isolated')) + C(pt3) + C(multi) + C(day)", D, groups=D["event"]).fit(reml=True)
        o["mixedlm"] = {"event_sd_ms": round(float(np.sqrt(max(m.cov_re.iloc[0, 0], 0))), 2), "resid_sd_ms": round(float(np.sqrt(m.scale)), 2),
                        "fe": {k: [round(float(v), 2), round(float(m.pvalues[k]), 4)] for k, v in m.params.items()
                               if k != "Group Var" and "day" not in k}}
    except Exception as e:  # noqa: BLE001
        o["mixedlm"] = str(e)[:200]
    # event bootstrap of the reversal - follow-on median difference
    ev = D.event.unique()
    byev = {e: D[D.event == e] for e in ev}
    rng = np.random.default_rng(3)
    bd = []
    for _ in range(2000):
        s = pd.concat([byev[e] for e in rng.choice(ev, len(ev))])
        a, b = s[s.cls == "reversal"].d, s[s.cls == "follow_on"].d
        if len(a) > 3 and len(b) > 3:
            bd.append(a.median() - b.median())
    if bd:
        o["reversal_minus_follow_on_median_ms_ci95"] = [round(float(x), 1) for x in np.percentile(bd, [2.5, 50, 97.5])]
    return o


def main():
    T = CR.load_takers()
    cb = pd.read_parquet(OUT / "census_bursts.parquet")
    cb_by_cid = {c: (g.sort_values("t0").t0.to_numpy(float), g.sort_values("t0").oi.to_numpy(int)) for c, g in cb.groupby("cid")}
    res = {"wallet_after_p4e": fit(pairs(T, P4E, W[:10], -120, 20, cb_by_cid)),
           "r2_after_p4e_control": fit(pairs(T, P4E, R2, -100, 40, cb_by_cid))}
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(RES / "lag_by_class.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
