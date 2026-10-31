"""Are any cumulative FIELDS null/missing mid-series (which ffill+fillna(0) would turn into a fake
zero day followed by a lump, or a lifetime-level jump)? Where do histories start?"""
import collections
from common import AS_OF, board, points
from polyrea.analysis.pnl import FIELDS
nulls = collections.Counter(); missing = collections.Counter(); first_days = collections.Counter(); neg_vol = 0
for r in board():
    pts = points(r["user_id"]) or []
    pts = [p for p in pts if p["timestamp"] <= AS_OF and p["timestamp"] % 86400 == 0]
    for f in FIELDS:
        if any(f not in p for p in pts): missing[f] += 1
        if any(p.get(f) is None for p in pts if f in p): nulls[f] += 1
    if pts:
        first_days[(pts[0]["timestamp"] // 86400 * 86400)] += 1
    vols = [p.get("volume_usdc") for p in pts]
    neg_vol += any(b is not None and a is not None and b < a - 1e-6 for a, b in zip(vols, vols[1:]))
print("wallets with a FIELD missing:", dict(missing)); print("wallets with a FIELD null:", dict(nulls))
import datetime as dt
print("most common first-point dates:", [(dt.datetime.utcfromtimestamp(t).date().isoformat(), c) for t, c in first_days.most_common(5)])
print("wallets whose cumulative volume_usdc ever decreases:", neg_vol)
