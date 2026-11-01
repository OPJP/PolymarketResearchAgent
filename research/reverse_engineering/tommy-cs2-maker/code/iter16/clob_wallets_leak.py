"""X222 (information panel iter-15 P4): is the shared recorder's clob_wallets feed conditioned on the wallet's presence?
Pre-registered in NOTES iteration 16. Development block 10-31 12-18 (the only development block with wallet trades and a
live recording; 10-31 00-06 predates the recorder, 11-01 06-12 has no wallet trade). Per market the wallet traded: the
first clob_wallets subscription (subs feed) against its first trade (data-api activity of the block); coverage of the
CS2 markets that tommy_cs2_near recorded in the block. Leaky iff >= 90% of traded markets are first subscribed after the
wallet's first trade. Output: results/clob_wallets_leak.json"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
A, B = 1793448000, 1793469600
first = {}
bad_slices = []


def sliced(feed, a, b, step=900):
    """iter_live in 15-min slices; a corrupted hour file (zlib 'invalid block type') loses only its slice."""
    t = a
    while t < b:
        try:
            for r in live.iter_live(feed, t, min(t + step, b)):
                yield r
        except Exception as e:  # noqa: BLE001
            bad_slices.append((feed, t, repr(e)[:80]))
        t += step


for r in sliced("subs", A, B):
    if r.get("feed") != "clob_wallets":
        continue
    for cid in r.get("markets") or {}:
        first.setdefault(cid.lower(), r["t"] / 1000.0)
act = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/activity_devblocks.parquet")
act = act[(act.type == "TRADE") & (act.timestamp >= A) & (act.timestamp < B)]
ft = act.groupby(act.conditionId.str.lower()).timestamp.min()
rows = []
for cid, t0 in ft.items():
    s = first.get(cid)
    rows.append({"cid": cid[:12], "event": act.loc[act.conditionId.str.lower() == cid, "eventSlug"].iloc[0],
                 "first_trade": float(t0), "first_sub": s, "sub_minus_trade_s": round(s - t0, 1) if s else None})
R = pd.DataFrame(rows)
near = set()
for r in sliced("tommy_cs2_near", A, B):
    c = r.get("c") or r.get("cid") or r.get("m")
    if c:
        near.add(str(c).lower())
after = R.sub_minus_trade_s.isna() | (R.sub_minus_trade_s > 0)
out = {"block": "10-31 12-18", "traded_markets": int(len(R)), "share_first_sub_after_first_trade": round(float(after.mean()), 3),
       "rows": R.to_dict("records"), "clob_wallets_markets_in_block": int(sum(1 for c, t in first.items() if A <= t < B)),
       "tommy_cs2_near_markets": int(len(near)),
       "cs2_near_markets_never_in_clob_wallets": int(len(near - set(first))) if near else None,
       "leaky": bool(after.mean() >= 0.9), "unreadable_slices": bad_slices}
(RES / "clob_wallets_leak.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))
