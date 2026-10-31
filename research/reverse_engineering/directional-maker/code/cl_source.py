"""Chainlink BTC/USD 1-s values (the Up/Down settlement stream) by value stamp, for final_rule.py (iteration 7).

Sources, in order:
1. live recordings (development blocks only unless the caller sets ALLOW_SEALED): the own streaming RTDS recorder
   dy_rtds (code7/rtdsstream.py: records {"k":"u","tp":"cl","sy":"btc","v","ts","P","t"}) and the staggered snapshot
   recorders dx_rtds / dm_rtds ({"t","q":"crypto_prices_chainlink","m": raw RTDS JSON with payload.data[{timestamp,
   value}]});
2. the endpoint cache (.cache/re/directional-maker/cl/*.parquet: tau, open, close);
3. Polymarket's endpoint GET https://polymarket.com/api/crypto/crypto-price?symbol=BTC&variant=fiveminute&
   eventStartTime=<ISO s> (openPrice = value stamped tau, closePrice = value stamped tau + 300; verified in iteration
   6/7: equals the RTDS Chainlink value at the same stamp to every decimal and reproduces Gamma priceToBeat), fetched
   with an adaptive limiter (<= 4 requests/s, slower after HTTP 429; the endpoint sustains about 1.5/s).
"""
from __future__ import annotations

import calendar
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CLDIR = ROOT / ".cache/re/directional-maker/cl"
BASE = "https://polymarket.com/api/crypto/crypto-price"


def _live(start_ts: int, end_ts: int, allow_sealed: bool) -> dict:
    sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
    import sealed as _sealed
    sys.path.insert(0, str(HERE.parent / "code5"))
    import rawread
    out = {}
    parts = ["dev", "sealed"] if allow_sealed else ["dev"]
    for feed in ("dy_rtds", "dx_rtds", "dm_rtds"):
        files = sorted((p for part in parts for p in (ROOT / ".cache/live" / part / feed).glob("*.jsonl.gz")), key=lambda p: p.name)
        for p in files:
            hour = calendar.timegm(time.strptime(p.name[:11], "%Y%m%dT%H"))
            if hour + 3600 <= start_ts - 120 or hour >= end_ts + 120:
                continue
            try:
                raw = p.read_bytes()
            except OSError:
                continue
            for chunk in rawread._members(raw):
                for line in chunk.split(b"\n"):
                    if not line or (b"chainlink" not in line and b'"tp":"cl"' not in line):
                        continue
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    t = r.get("t", 0) / 1000.0
                    if not allow_sealed and _sealed.future_block_sealed(t):
                        continue
                    if r.get("k") == "u":
                        if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("ts") and r.get("v") is not None:
                            out.setdefault(int(r["ts"]) // 1000, float(r["v"]))
                    elif r.get("q") == "crypto_prices_chainlink":
                        try:
                            j = json.loads(r["m"])
                        except (ValueError, KeyError, TypeError):
                            continue
                        pl = j.get("payload") or {}
                        if str(pl.get("symbol", "btc/usd")).lower() not in ("btc/usd", "btc"):
                            continue
                        for x in pl.get("data", []) or []:
                            try:
                                out.setdefault(int(x["timestamp"]) // 1000, float(x["value"]))
                            except (KeyError, TypeError, ValueError):
                                pass
    return out


def _cache() -> dict:
    out = {}
    for f in sorted(CLDIR.glob("*.parquet")):
        try:
            g = pd.read_parquet(f)
        except Exception:  # noqa: BLE001
            continue
        if not {"tau", "open", "close"} <= set(g.columns):
            continue
        g = g.dropna(subset=["open"])
        for t, o, c in zip(g["tau"].astype(np.int64), g["open"], g["close"]):
            out.setdefault(int(t), float(o))
            if c is not None and np.isfinite(c):
                out.setdefault(int(t) + 300, float(c))
    return out


def _fetch(missing: list[int]) -> dict:
    import httpx
    miss = set(missing)
    taus = []
    for m in sorted(miss):
        if m not in miss:
            continue
        if m + 300 in miss:
            taus.append(m)
            miss.discard(m + 300)
        elif m - 300 in miss:
            taus.append(m - 300)
            miss.discard(m - 300)
        else:
            taus.append(m)
        miss.discard(m)
    lock, nxt, gap = threading.Lock(), [time.time()], [0.4]
    cli = httpx.Client(timeout=20, headers={"User-Agent": "polyrea/0.1 (research)", "Accept": "application/json"})

    def one(t):
        for _ in range(60):
            with lock:
                wait = nxt[0] - time.time()
                nxt[0] = max(nxt[0], time.time()) + gap[0]
            if wait > 0:
                time.sleep(wait)
            try:
                r = cli.get(BASE, params={"symbol": "BTC", "variant": "fiveminute",
                                          "eventStartTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))})
            except Exception:  # noqa: BLE001
                time.sleep(2)
                continue
            if r.status_code == 429:
                with lock:
                    gap[0] = min(1.5, gap[0] + 0.05)
                    nxt[0] = max(nxt[0], time.time() + 2.0)
                continue
            if r.status_code != 200:
                time.sleep(1)
                continue
            with lock:
                gap[0] = max(0.25, gap[0] - 0.002)
            d = r.json()
            return t, d.get("openPrice"), d.get("closePrice"), bool(d.get("completed"))
        return t, None, None, False

    rows = []
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(one, taus))
    df = pd.DataFrame(rows, columns=["tau", "open", "close", "completed"])
    CLDIR.mkdir(parents=True, exist_ok=True)
    f = CLDIR / "cl_eval_cache.parquet"
    # only completed responses (both values final) are cached
    keep = df[df["completed"] & df["open"].notna()]
    if f.exists():
        keep = pd.concat([pd.read_parquet(f), keep]).drop_duplicates("tau")
    keep.to_parquet(f, index=False)
    out = {}
    for t, o, c in zip(df["tau"], df["open"], df["close"]):
        if o is not None:
            out[int(t)] = float(o)
        if c is not None:
            out[int(t) + 300] = float(c)
    return out


def cl_values(stamps, allow_sealed: bool = False, fetch: bool = True, max_requests: int = 3000) -> pd.Series:
    """Chainlink BTC/USD value for each requested stamp second (NaN where unavailable). Missing stamps are fetched from
    the endpoint only when they need at most max_requests requests (about 1.5 requests/s), otherwise left NaN."""
    stamps = np.unique(np.asarray(stamps, dtype=np.int64))
    if len(stamps) == 0:
        return pd.Series(dtype=float)
    vals = _live(int(stamps.min()), int(stamps.max()) + 1, allow_sealed)
    for k, v in _cache().items():
        vals.setdefault(k, v)
    miss = [int(s) for s in stamps if int(s) not in vals]
    if miss and fetch and len(miss) <= 2 * max_requests:
        for k, v in _fetch(miss).items():
            vals.setdefault(k, v)
    return pd.Series({int(s): vals.get(int(s), np.nan) for s in stamps}, dtype=float).sort_index()
