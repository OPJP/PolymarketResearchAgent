"""Iteration 8, X106 step 1 (information panel iter7 P6): during the wallet's idle-but-up gaps (>= 30 min without
any own order while its merge loop runs, 16-22 Oct) is the feed up? Count P4e taker prints and the other subscribers'
prints in CS2 universe tapes (every CS2 match / map market, untraded included) inside each gap, against the same
subscribers' rate in the rest of that day's run. Output: results/outage_gaps.json"""
from __future__ import annotations
import glob, json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
SUBS = {P4E, "0x2005d16a84ceefa912d4e380cd32e7ff827875ea", "0x8a80528dce46711a54aa3455c2cc81dea51e11c5",
        "0xddb6e6246546230503f153506ac1e9914978b9b3", "0xf1ee4842fa0c7283632185e42577027452d4519c",
        "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3"}
RUNS = [("2026-10-16 13:45:00", "2026-10-16 18:54:40"), ("2026-10-17 08:10:03", "2026-10-17 20:21:36"),
        ("2026-10-18 14:17:06", "2026-10-18 16:40:30"), ("2026-10-19 08:10:57", "2026-10-19 21:58:43"),
        ("2026-10-20 09:04:07", "2026-10-20 20:12:06"), ("2026-10-21 08:22:32", "2026-10-21 23:29:35"),
        ("2026-10-22 08:29:56", "2026-10-22 23:17:54")]


def main():
    o = pd.read_parquet(OUT / "orders.parquet")
    st = np.sort(o.sign_ms.to_numpy(float) / 1000)
    st = st[(st > 1.79e9) & (st < 1.7928e9)]
    runs = [(pd.Timestamp(a, tz="UTC").timestamp(), pd.Timestamp(b, tz="UTC").timestamp()) for a, b in RUNS]
    gaps = []
    for a, b in runs:
        x = st[(st >= a) & (st <= b)]
        if len(x) < 2:
            continue
        d = np.diff(x)
        for i in np.where(d >= 1800)[0]:
            gaps.append((x[i], x[i + 1], a, b))
    pr = []
    for f in glob.glob(str(OUT / "tapes" / "*_tkw.parquet")):
        d = pd.read_parquet(f, columns=["proxyWallet", "timestamp"])
        d = d[d.proxyWallet.str.lower().isin(SUBS)]
        if len(d):
            pr.append(d.assign(w=d.proxyWallet.str.lower()))
    P = pd.concat(pr)
    res = {"gaps": []}
    for g0, g1, a, b in gaps:
        m_in = (P.timestamp >= g0) & (P.timestamp < g1)
        m_run = (P.timestamp >= a) & (P.timestamp < b) & ~m_in
        dur_in, dur_run = (g1 - g0) / 3600, ((b - a) - (g1 - g0)) / 3600
        res["gaps"].append({"start": pd.Timestamp(g0, unit="s").strftime("%m-%d %H:%M"), "end": pd.Timestamp(g1, unit="s").strftime("%H:%M"),
                            "hours": round(dur_in, 2),
                            "p4e_prints_per_h_in_gap": round(float((m_in & (P.w == P4E)).sum() / dur_in), 1),
                            "p4e_prints_per_h_rest_of_run": round(float((m_run & (P.w == P4E)).sum() / max(dur_run, 1e-9)), 1),
                            "other_subs_per_h_in_gap": round(float((m_in & (P.w != P4E)).sum() / dur_in), 1),
                            "other_subs_per_h_rest_of_run": round(float((m_run & (P.w != P4E)).sum() / max(dur_run, 1e-9)), 1)})
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "outage_gaps.json", "w"), indent=1)


if __name__ == "__main__":
    main()
