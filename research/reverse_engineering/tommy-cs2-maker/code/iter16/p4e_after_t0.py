"""X230 qualifier: did P4e (0x4ebc2722, the fan-out's first signer in 16-22 Oct) trade at all in the development blocks
after T0? data-api activity of P4e in 10-31 12-18 and 11-01 06-12 (the blocks with live development units); rows are
kept only for events whose start is a development unit (universe_t0 / dev_markets listing projection), others are
dropped unread (counted only). Also the same counts for RN1 and the trio. Output: results/p4e_after_t0.json"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
ACC = {"P4e": "0x4ebc2722adc772bde8680792d0a6fdf15499a33d", "RN1": "0x2005d16a84ceefa912d4e380cd32e7ff827875ea",
       "trio1": "0x72aaaaf9f6b0286e390de5b568af0f99a00c90e0"}
BLOCKS = [(1793448000, 1793469600), (1793512800, 1793534400)]
u = pd.read_parquet(OUT / "universe_t0.parquet")
egs = u.groupby("event_slug").gs_ts.min().to_dict()
v = pd.read_parquet(OUT / "dev_markets_v1101a.parquet")
for ev, g in v.groupby("event"):
    egs.setdefault(ev, float(g.gs.min()))
pm = PolymarketData()
out = {}
for nm, a in ACC.items():
    o = {}
    for (s0, s1) in BLOCKS:
        rws, _, _ = pm.activity(a, s0, s1 - 1)
        rows = [dict(x) for x in rws if dict(x).get("type") == "TRADE"]
        keep, drop = [], 0
        for x in rows:
            ev = x.get("eventSlug")
            g0 = egs.get(ev)
            if g0 is None or sealed.is_sealed(float(g0), "tommy-cs2-maker"):
                drop += 1  # unknown or sealed-start unit: not read further
                continue
            keep.append(ev)
        o[f"{s0}"] = {"trade_rows_total": len(rows), "rows_in_known_development_units": len(keep), "rows_dropped_unread": drop,
                      "events": pd.Series(keep).value_counts().head(8).to_dict() if keep else {}}
    out[nm] = o
(RES / "p4e_after_t0.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
