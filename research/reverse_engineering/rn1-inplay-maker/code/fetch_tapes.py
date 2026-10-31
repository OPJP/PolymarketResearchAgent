"""Gamma events + full public tapes (taker rows and maker rows) for a seeded random sample of the
events RN1 traded in a period, including every sibling market of each sampled event (to see what it avoids).

Tape window per market: [gameStart - 2 h, gameStart + 5 h], clipped to < H (no holdout data).
Market selection uses only the period's event list; the tape window uses only listing metadata.
Output: .cache/re/rn1-inplay-maker/tapes/<event_slug>.parquet  (one row per tape row, role = taker/maker)
        .cache/re/rn1-inplay-maker/gamma/<event_slug>.json
Usage: python fetch_tapes.py <period_start> <period_end> <n_events> <seed>
"""
from __future__ import annotations

import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

H = 1792713600
C = ROOT / ".cache/re/rn1-inplay-maker"
(C / "tapes").mkdir(parents=True, exist_ok=True)
(C / "gamma").mkdir(parents=True, exist_ok=True)
pm = PolymarketData()


def parse_ts(s):
    if not s:
        return None
    s = str(s).replace("Z", "+00:00").replace(" ", "T")
    if s.endswith("+00"):
        s = s + ":00"
    try:
        return int(datetime.fromisoformat(s).astimezone(timezone.utc).timestamp())
    except ValueError:
        return None


def gamma_event(slug):
    f = C / "gamma" / f"{slug}.json"
    if f.exists():
        return json.load(open(f))
    d, _ = pm.http.get_json("https://gamma-api.polymarket.com/events", {"slug": slug}, adapter="gamma.events", max_age=None)
    e = d[0] if d else None
    json.dump(e, open(f, "w"))
    return e


def tape_rows(cid, tokens, a, b):
    taker, _, c1 = pm.market_trades(cid, start=a, end=b, taker_only=True, max_rows=80_000)
    full, _, c2 = pm.market_trades(cid, start=a, end=b, taker_only=False, max_rows=160_000)
    keys = {}
    out = []
    for r in taker:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        keys[k] = keys.get(k, 0) + 1
        if str(r.get("asset")) in tokens:
            out.append((cid, int(r["timestamp"]), tokens.index(str(r["asset"])), r.get("side"), float(r["price"]),
                        float(r["size"]), (r.get("proxyWallet") or "").lower(), r.get("transactionHash"), "taker"))
    for r in full:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        if keys.get(k, 0) > 0:
            keys[k] -= 1
            continue
        if str(r.get("asset")) in tokens:
            out.append((cid, int(r["timestamp"]), tokens.index(str(r["asset"])), r.get("side"), float(r["price"]),
                        float(r["size"]), (r.get("proxyWallet") or "").lower(), r.get("transactionHash"), "maker"))
    return out, c1.status + "/" + c2.status


def do_event(slug):
    f = C / "tapes" / f"{slug}.parquet"
    if f.exists():
        return slug, "cached"
    e = gamma_event(slug)
    if not e:
        return slug, "no-gamma"
    rows, stat = [], []
    for m in e.get("markets") or []:
        try:
            tokens = json.loads(m.get("clobTokenIds") or "[]")
        except ValueError:
            tokens = []
        if len(tokens) != 2:
            continue
        gst = parse_ts(m.get("gameStartTime")) or parse_ts(e.get("startTime")) or parse_ts(m.get("endDate"))
        if gst is None:
            continue
        a, b = gst - 7200, min(gst + 5 * 3600, H - 1)
        if a >= b:
            continue
        r, s = tape_rows(m["conditionId"], tokens, a, b)
        rows += r
        stat.append(s)
    df = pd.DataFrame(rows, columns=["cid", "ts", "outcome", "side", "price", "size", "wallet", "tx", "role"])
    df.to_parquet(f, index=False)
    return slug, f"{len(df)} rows {len(stat)} mkts"


def main(p0, p1, n, seed):
    acts = []
    for day in range(p0, p1, 86400):
        g = C / "activity" / f"act_{day}.parquet"
        if g.exists():
            acts.append(pd.read_parquet(g, columns=["type", "timestamp", "eventSlug"]))
    a = pd.concat(acts)
    a = a[(a["type"] == "TRADE") & (a["timestamp"] >= p0) & (a["timestamp"] < p1)]
    ev = sorted(set(a["eventSlug"].dropna()) - {""})
    rng = random.Random(seed)
    sample = rng.sample(ev, min(n, len(ev)))
    json.dump({"period": [p0, p1], "seed": seed, "n_events_total": len(ev), "sample": sample},
              open(C / f"tape_sample_{p0}_{p1}.json", "w"))
    print("events in period", len(ev), "sampled", len(sample), flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(3) as ex:
        for i, (slug, msg) in enumerate(ex.map(do_event, sample)):
            if i % 10 == 0:
                print(i, slug, msg, f"{time.time()-t0:.0f}s", flush=True)
    print("done", f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
