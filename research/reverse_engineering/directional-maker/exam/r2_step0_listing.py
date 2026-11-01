"""Examiner round 2, step 0: sufficiency and the half split, from LISTING METADATA ONLY (no fills, no outcomes).

Fetches Gamma markets of every crypto Up/Down family whose window starts in lot f1 (through the exam cache) and keeps a
projection without post-hoc fields: cid, slug, family, start, end, tokens, fee rate. Writes
.cache/exam/directional-maker/listing_f1.parquet and results/exam_r2_step0.json.
The half cut = the median listed start of the BTC 5m windows in the lot (the rule's primary unit); every unit is
assigned by its listed start. Truncation sample: 30 BTC 5m windows drawn with seed 20261101 from the listing.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from r2_common import EXC, LOT, RES, in_lot

from polyrea.workflows.updown_study import fetch_windows  # noqa: E402

ET = ZoneInfo("America/New_York")
COINS = ("btc", "eth", "sol", "xrp", "bnb", "doge", "hype")
LONG = {"btc": "bitcoin", "eth": "ethereum", "sol": "solana", "xrp": "xrp", "bnb": "bnb", "doge": "dogecoin", "hype": "hype"}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def slugs():
    out = []
    a, b = LOT[0][0], LOT[-1][1]
    for c in COINS:
        for tag, step in (("5m", 300), ("15m", 900), ("4h", 14400)):
            t = a - a % step
            while t < b:
                if in_lot(t):
                    out.append((f"{c}-{tag}", f"{c}-updown-{tag}-{t}", t, step))
                t += step
    # hourly: <long>-up-or-down-<month>-<day>-<year>-<h><am|pm>-et, starting at the ET hour
    for c in COINS:
        t = a
        while t < b:
            dt = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(ET)
            h = dt.hour
            hs = f"{h % 12 or 12}{'am' if h < 12 else 'pm'}"
            if in_lot(t):
                out.append((f"{c}-hourly", f"{LONG[c]}-up-or-down-{MONTHS[dt.month - 1]}-{dt.day}-{dt.year}-{hs}-et", t, 3600))
            t += 3600
    return out


def main():
    t0 = time.time()
    S = slugs()
    raw = fetch_windows([s[1] for s in S])
    by_slug = {}
    for cid, m in raw.items():
        by_slug[str(m.get("slug"))] = (cid, m)
    rows = []
    for fam, slug, t, step in S:
        if slug not in by_slug:
            rows.append(dict(fam=fam, slug=slug, sched_start=t, listed=False))
            continue
        cid, m = by_slug[slug]
        try:
            toks = json.loads(m.get("clobTokenIds") or "[]")
        except ValueError:
            toks = []
        st = pd.Timestamp(m.get("eventStartTime")).timestamp() if m.get("eventStartTime") else np.nan
        en = pd.Timestamp(m.get("endDate")).timestamp() if m.get("endDate") else np.nan
        fs = m.get("feeSchedule") or {}
        rows.append(dict(fam=fam, slug=slug, sched_start=t, listed=True, cid=cid, start_ts=st, end_ts=en,
                         tok0=str(toks[0]) if toks else None, tok1=str(toks[1]) if len(toks) > 1 else None,
                         fee_rate=fs.get("rate"), created=str(m.get("createdAt") or "")))
    L = pd.DataFrame(rows)
    # keep listing fields only (no outcome, volume, liquidity, closed flags)
    L.to_parquet(EXC / "listing_f1.parquet", index=False)
    Ll = L[L.listed].copy()
    Ll["unit_start"] = Ll["start_ts"].fillna(Ll["sched_start"]).astype(np.int64)
    # hourly windows: listed start = eventStartTime; keep units that start in the lot
    Ll = Ll[[in_lot(x) for x in Ll["unit_start"]]]
    b5 = Ll[Ll.fam == "btc-5m"].sort_values("unit_start")
    cut = int(np.median(b5["unit_start"].to_numpy()))
    cut = cut - cut % 300
    Ll["half"] = np.where(Ll["unit_start"] < cut, "early", "late")
    cnt = Ll.groupby(["fam", "half"]).size().unstack(fill_value=0)
    gaps = L[(~L.listed) & L.fam.isin(["btc-5m", "btc-15m"])]
    rng = np.random.default_rng(20261101)
    samp = sorted(rng.choice(b5["unit_start"].to_numpy(), size=min(30, len(b5)), replace=False).tolist())
    out = {"lot": LOT, "fetched_slugs": len(S), "listed": int(L.listed.sum()), "cut_ts": cut,
           "cut_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(cut)),
           "units_by_family_half": {f: {h: int(v) for h, v in r.items()} for f, r in cnt.iterrows()},
           "btc5m_windows": int(len(b5)), "btc15m_windows": int((Ll.fam == "btc-15m").sum()),
           "btc_5m_15m_not_listed": [(r.slug, time.strftime("%m-%d %H:%M", time.gmtime(r.sched_start))) for r in gaps.itertuples()],
           "fee_rates_btc5m": sorted(set(b5["fee_rate"].dropna().astype(float).tolist())),
           "truncation_sample_starts": [int(x) for x in samp], "seed": 20261101, "secs": round(time.time() - t0, 1)}
    (RES / "exam_r2_step0.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "truncation_sample_starts"}, indent=1, default=str))


if __name__ == "__main__":
    main()
