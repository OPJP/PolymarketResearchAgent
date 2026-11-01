"""Iteration 7 (panel iter6 information I1, reopens X42): historical Chainlink BTC/USD 1-s values from Polymarket's own
endpoint  GET https://polymarket.com/api/crypto/crypto-price?symbol=BTC&variant=fiveminute&eventStartTime=<ISO s>
(openPrice = the Chainlink value stamped at that second, closePrice = the value stamped 300 s later).

Pre-registered sample (iteration 7, before any CL data was looked at): in every day of STUDY (2026-10-23..26, fit) and
VALIDATE (2026-10-27..30, aggregate only), the window pairs (W_i, W_{i+1}) with i % 8 == 0 (i = window index in the UTC
day): requests at tau = st(W_i) + 10 j - 3, j = 0..29, which give the values stamped st + 10j - 3 (W_i's bin starts minus
3 s) and st + 300 + 10j - 3 (W_{i+1}'s). 30 requests per pair, 36 pairs per day. Plus verification: 3 STUDY windows at
1 s over [st-61, st-2] (=> priceToBeat and, through +300, the closing minute), and 10 overlap checks of close(tau) vs
open(tau+300).

Through the polyrea HttpClient (cached forever, 4 requests/s for polymarket.com, 4 threads). Output:
.cache/re/directional-maker/cl/cl_grid.parquet (tau, open, close) appended in chunks.

  .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code7/fetch_cl.py [--days ...]
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import HttpClient  # noqa: E402

OUT = ROOT / ".cache/re/directional-maker/cl"
BASE = "https://polymarket.com/api/crypto/crypto-price"
STUDY_DAYS = [1792713600 + 86400 * k for k in range(4)]
VALID_DAYS = [1793059200 + 86400 * k for k in range(4)]


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def plan(days, stride=8, offset=0):
    taus = []
    for d in days:
        for i in range(offset, 288, stride):
            st = d + 300 * i
            taus += [st + 10 * j - 3 for j in range(30)]
    return taus


def verify_plan():
    taus = []
    for st in (1792713600 + 300 * 101, 1792800000 + 300 * 157, 1792972800 + 300 * 233):  # three STUDY windows
        taus += list(range(st - 61, st - 1))
    taus += [1792713600 + 300 * 8 * k + 10 * k - 3 + 300 for k in range(10)]  # overlap checks (open at tau+300)
    return taus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", default="all")
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--offset", type=int, default=0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    # The shared HttpClient blocked on the shared sqlite cache (no 400 responses in 4 minutes on 2026-10-31 17:30 UTC,
    # single requests 0.9-3.2 s), so this bulk fetch uses httpx directly with its own limiter (<= 4 requests/s,
    # 4 threads) and keeps every response in its own parquet (cl_grid.parquet), which serves as its cache.
    import threading
    import httpx
    lock, nxt, gap = threading.Lock(), [time.time()], [0.3]
    cli = httpx.Client(timeout=20, headers={"User-Agent": "polyrea/0.1 (research)", "Accept": "application/json"})

    class _H:
        """Adaptive limiter: spacing starts at 0.3 s (3.3/s), +0.05 s after each 429 (max 1 s), -0.002 s per success
        (min 0.25 s = 4/s)."""
        def get_json(self, base, params, adapter=None, max_age=None):
            while True:
                with lock:
                    wait = nxt[0] - time.time()
                    nxt[0] = max(nxt[0], time.time()) + gap[0]
                if wait > 0:
                    time.sleep(wait)
                r = cli.get(base, params=params)
                if r.status_code == 429:
                    with lock:
                        gap[0] = min(1.0, gap[0] + 0.05)
                        nxt[0] = max(nxt[0], time.time() + 2.0)
                    continue
                r.raise_for_status()
                with lock:
                    gap[0] = max(0.25, gap[0] - 0.002)
                return r.json(), None
    h = _H()
    order = []
    vt = verify_plan()
    s_taus, v_taus = plan(STUDY_DAYS, a.stride, a.offset), plan(VALID_DAYS, a.stride, a.offset)
    # interleave STUDY and VALIDATE days so partial data is balanced
    per = len(range(a.offset, 288, a.stride)) * 30
    for k in range(4):
        order += s_taus[k * per:(k + 1) * per] + v_taus[k * per:(k + 1) * per]
    order = vt + order
    done = set()
    f = OUT / "cl_grid.parquet"
    if f.exists():
        done = set(pd.read_parquet(f)["tau"].astype(int))
    todo = [t for t in order if t not in done]
    print("todo", len(todo), "done", len(done), flush=True)

    def one(t):
        for k in range(5):
            try:
                d, _ = h.get_json(BASE, {"symbol": "BTC", "variant": "fiveminute", "eventStartTime": iso(t)},
                                  adapter="pm.cryptoprice", max_age=None)
                return (t, d.get("openPrice"), d.get("closePrice"), bool(d.get("completed")))
            except Exception as e:  # noqa: BLE001
                err = repr(e)[:200]
                time.sleep(2 * (k + 1))
        print("FAIL", t, err, flush=True)
        return (t, None, None, False)

    rows, t0 = [], time.time()
    with ThreadPoolExecutor(4) as ex:
        for i, r in enumerate(ex.map(one, todo)):
            rows.append(r)
            if len(rows) >= 200 or i == len(todo) - 1:
                df = pd.DataFrame(rows, columns=["tau", "open", "close", "completed"])
                if f.exists():
                    df = pd.concat([pd.read_parquet(f), df]).drop_duplicates("tau")
                df.to_parquet(f, index=False)
                rows = []
                print(time.strftime("%H:%M:%S"), "saved", len(df), "rate", round((i + 1) / (time.time() - t0), 2), "gap", round(gap[0], 3), flush=True)


if __name__ == "__main__":
    main()
