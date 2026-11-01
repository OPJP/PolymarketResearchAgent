"""Iteration 7: Gamma priceToBeat (the strike, fixed at the window start) for the windows of the CL sample
(fetch_cl.py plan) plus every window of the lot days (for the strike; finalPrice kept only to verify settlement)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402

OUT = ROOT / ".cache/re/directional-maker/cl"
days = [1792713600 + 86400 * k for k in range(8)]
slugs = [f"btc-updown-5m-{d + 300 * i}" for d in days for i in range(288)]
rows = []
for k in range(0, len(slugs), 20):
    d = fetch_windows(slugs[k:k + 20])
    for cid, m in d.items():
        em = {}
        for e in m.get("events") or []:
            em = e.get("eventMetadata") or em
        rows.append({"cid": cid, "slug": m.get("slug"), "start_ts": int(str(m.get("slug")).rsplit("-", 1)[1]),
                     "ptb": em.get("priceToBeat"), "final": em.get("finalPrice")})
df = pd.DataFrame(rows).drop_duplicates("cid").sort_values("start_ts")
df.to_parquet(OUT / "ptb_lot.parquet", index=False)
print(len(df), df["ptb"].notna().mean(), df["start_ts"].min(), df["start_ts"].max())
