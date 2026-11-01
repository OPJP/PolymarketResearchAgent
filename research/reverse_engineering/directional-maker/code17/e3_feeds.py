"""iteration 17, T13 = E3 screen of the reference-feed family on the live BUILD blocks (pre-registered in NOTES.md
11:26 UTC): decisions = the cluster's at-touch 500/1000 posts (it14_qu_rebuilt), events = futures mid jumps (k 3 over
0.5 / 2 / 10 s) and Chainlink report changes (exact publish clock), +-2 s and +-60 s lag ranges, swap null, BH."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code14"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from lagged_quote import fut_mid, live  # noqa: E402
import indicators as ind  # noqa: E402

BLOCKS = [(1793455200, 1793469600), (1793516400, 1793524500)]


def main():
    dec, dsg, units, ev = [], [], [], {f"fut_jump_h{h}": ([], []) for h in (0.5, 2.0, 10.0)}
    ev["cl_publish_change"] = ([], [])
    for a, b in BLOCKS:
        A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet")
        A = A[A.dz.isin([500.0, 1000.0])]
        dec.append(A.s.to_numpy(float) / 1000.0)
        dsg.append(np.where(A.sd == 1, 1.0, -1.0))
        units += [(t, t + 300) for t in range(a, b, 300)]
        E, M = fut_mid(a - 120, b + 60)
        t = ind.grid(a - 60, b + 30, 0.1)
        mid = ind.asof(t, np.asarray(E, float) / 1000.0, np.asarray(M, float))
        for h in (0.5, 2.0, 10.0):
            ts, sg = ind.jumps(t, mid, horizon=int(round(h / 0.1)), k=3.0, refractory_s=0.5)
            ev[f"fut_jump_h{h}"][0].append(ts)
            ev[f"fut_jump_h{h}"][1].append(sg)
        pub = []
        for r in live.iter_live("dy_rtds", a - 60, b + 30):
            if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
                pub.append((int(r["P"]) / 1000.0, float(r["v"])))
        pub.sort()
        if pub:
            P = np.array([x[0] for x in pub])
            V = np.array([x[1] for x in pub])
            ch = np.r_[0.0, np.diff(V)]
            m = ch != 0
            ev["cl_publish_change"][0].append(P[m])
            ev["cl_publish_change"][1].append(np.sign(ch[m]))
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
        print(nm, json.dumps([{k: x[k] for k in ("name", "p_link", "q_bh", "signed_p_link", "signed_q_bh", "shape_peak_lag_s", "shape_lift", "signed_shape_peak_lag_s", "signed_shape_z", "null")} for x in r], default=str), flush=True)
    # one joint BH over both lag ranges
    ps = [x["p_link"] for x in rows] + [x["signed_p_link"] for x in rows if x["signed_p_link"] is not None]
    qs = ind.bh(ps)
    for x, q in zip(rows, qs[: len(rows)]):
        x["q_joint"] = float(q)
    for x, q in zip([x for x in rows if x["signed_p_link"] is not None], qs[len(rows):]):
        x["signed_q_joint"] = float(q)
    out["rows"] = rows
    (HERE.parent / "results" / "iter17_e3_feeds.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("n_decisions", "n_units", "n_events")}))


if __name__ == "__main__":
    main()
