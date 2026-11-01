"""iteration 18, T15 = E3 screen of the report-innovation events (pre-registered in NOTES.md 13:20 UTC 11-01) on the live
BUILD blocks of iteration 17's screen (10-31 14-18 with dy_rtds from 17:29, 11-01 07:00-09:15), with the brief's machinery
(tools/indicators.py screen: swap null, hour strata, level + shape, signed version, BH). Decisions: the at-touch 500/1000
posts (it14_qu_rebuilt), sign +1 for an Up post. Events: public Chainlink BTC publishes (dy_rtds P) whose futures-only
innovation |u| >= $1 and >= $2 (T3's frozen beta), signed by u. Lag ranges +-2 s (0.1-s bins) and +-60 s (1-s bins),
300 null draws, one joint BH over the family."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import event_law as el  # noqa: E402
import indicators as ind  # noqa: E402

BLOCKS = [(1793455200, 1793469600), (1793516400, 1793524500)]
BETA = np.array([-0.0023, 0.0311, 0.2357, 0.5243, 0.3854])


def main():
    dec, dsg, units = [], [], []
    ev = {"cl_innov_u1": ([], []), "cl_innov_u2": ([], [])}
    for a, b in BLOCKS:
        A = pd.read_parquet(el.C / f"it14_qu_rebuilt_{a}_{b}.parquet")
        A = A[A.dz.isin([500.0, 1000.0])]
        dec.append(A.s.to_numpy(float) / 1000.0)
        dsg.append(np.where(A.sd == 1, 1.0, -1.0))
        units += [(t, t + 300) for t in range(a, b, 300)]
        E, M = el.fut_mid(a - 120, b + 60)
        sc, cl, P = el.publishes(a, b)
        if not sc:
            continue
        X = el.design(E, M, sc)
        y = np.array([cl[s] - cl[s - 1] for s in sc])
        ok = np.all(np.isfinite(X), axis=1)
        u = y - np.where(ok, np.c_[np.ones(len(X)), np.nan_to_num(X)] @ BETA, np.nan)
        Pp = np.array([P[s] for s in sc], float) / 1000.0
        for nm, thr in (("cl_innov_u1", 1.0), ("cl_innov_u2", 2.0)):
            m = np.isfinite(u) & (np.abs(u) >= thr)
            o = np.argsort(Pp[m])
            ev[nm][0].append(Pp[m][o])
            ev[nm][1].append(np.sign(u[m])[o])
    D = np.concatenate(dec)
    S = np.concatenate(dsg)
    U = np.array(units, float)
    hours = ((U[:, 0] % 86400) // 3600).astype(int)
    indic = {k: (np.concatenate(v[0]), np.concatenate(v[1])) for k, v in ev.items()}
    out = {"n_decisions": int(len(D)), "n_units": int(len(U)), "n_events": {k: int(len(v[0])) for k, v in indic.items()}}
    rows = []
    for nm, (ml, bs) in (("pm2s", (4.0, 0.1)), ("pm60s", (120.0, 1.0))):
        r = ind.screen(D, indic, U, max_lag_s=ml, bin_s=bs, n_null=300, strata=hours, decision_sign=S)
        for x in r:
            x["lag_range"] = nm
        rows += r
    ps = [x["p_link"] for x in rows] + [x["signed_p_link"] for x in rows if x["signed_p_link"] is not None]
    qs = ind.bh(ps)
    for x, q in zip(rows, qs[: len(rows)]):
        x["q_joint"] = float(q)
    for x, q in zip([x for x in rows if x["signed_p_link"] is not None], qs[len(rows):]):
        x["signed_q_joint"] = float(q)
    out["rows"] = rows
    (HERE.parent / "results" / "iter18_e3_innov.json").write_text(json.dumps(out, indent=1, default=str))
    for x in rows:
        print(x["lag_range"], x["name"], {k: x.get(k) for k in ("p_link", "q_joint", "signed_p_link", "signed_q_joint", "shape_peak_lag_s", "shape_lift", "signed_shape_peak_lag_s", "signed_shape_z", "null", "units_in_null")})


if __name__ == "__main__":
    main()
