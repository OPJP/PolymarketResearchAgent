"""directional-maker iteration 10: slim family recorder (panel iter9 information I9-2 step 3 = X88, mechanics M4 = X95).

Why: the shared recorder's clob_crypto `q` snapshots are too sparse in its files to label the quote unit (recall 1-4%
against the raw label, code10/i92_label.py), and nothing records XRP / BNB / DOGE. The own exam recorder (code6/examrec.py,
dx_clob) covers only BTC 5m current+next and BTC 15m current. This recorder applies examrec's reduction (schedule-size
deltas within 3 ticks of the touch with server ms, the touch queue every 200 ms, trades with tx hash, books within 3
ticks every 5 s) to the other crypto Up/Down families: ETH, SOL, XRP, BNB, DOGE 5m (current + next) and 15m (current).
Feed name dw_clob, filed by tools/live.py Writer (dev / sealed by receive time); agents read dev blocks only.
Hard stop --until; disk cap 280 MB over dw_*; memory: one level dict per market (< 100 MB).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code10/famrec.py --until 1793664000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
sys.path.insert(0, str(HERE.parent / "code6"))
import live  # noqa: E402
import examrec as X  # noqa: E402  (reuses clob_market and gamma_tokens; its own main is not run)

LIVE = ROOT / ".cache" / "live"
STATUS = ROOT / ".cache" / "re" / "directional-maker" / "famrec_status.json"
DISK_CAP_MB = 280
ASSETS = ("eth", "sol", "xrp", "bnb", "doge", "hype")


def disk_mb():
    tot = 0
    for part in ("dev", "sealed"):
        base = LIVE / part
        if base.exists():
            for d in base.glob("dw_*"):
                for p in d.glob("*.gz"):
                    try:
                        tot += p.stat().st_size
                    except OSError:
                        pass
    return tot / 1e6


async def manager(stop, hard_stop):
    w = live.Writer("dw_clob")
    cache: dict = {}
    running: dict[str, asyncio.Task] = {}
    missing: dict[str, float] = {}
    flush_t = time.time()
    while not stop.is_set():
        now = time.time()
        want = []
        b5 = int(now // 300 * 300)
        b15 = int(now // 900 * 900)
        for a in ASSETS:
            for k in (0, 1):
                want.append((f"{a}-updown-5m-{b5 + 300 * k}", b5 + 300 * k + 320))
            want.append((f"{a}-updown-15m-{b15}", b15 + 920))
        for slug, until_ts in want:
            if slug in running and not running[slug].done():
                continue
            if time.time() >= until_ts or missing.get(slug, 0) > time.time():
                continue
            toks = await X.gamma_tokens(slug, cache)
            if len(toks) == 2:
                running[slug] = asyncio.create_task(X.clob_market(slug, toks, w, stop, min(until_ts, hard_stop)))
            else:
                missing[slug] = time.time() + 60  # retry a missing listing once a minute
        for slug in [s for s, t in running.items() if t.done()]:
            del running[slug]
        if len(cache) > 200:
            for k in list(cache)[:-60]:
                del cache[k]
        if len(missing) > 500:
            missing = {k: v for k, v in missing.items() if v > time.time()}
        X.STATE["running"] = sorted(running)
        if time.time() - flush_t > 3:
            w.flush()
            flush_t = time.time()
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
    for t in running.values():
        t.cancel()
    w.close()


async def supervisor(stop, hard_stop):
    while not stop.is_set():
        mb = disk_mb()
        if mb > DISK_CAP_MB or time.time() >= hard_stop:
            X.STATE["stop_reason"] = "disk" if mb > DISK_CAP_MB else "hard_stop"
            stop.set()
        X.STATE.update({"pid": os.getpid(), "updated": int(time.time()), "disk_mb": round(mb, 1), "hard_stop": int(hard_stop)})
        STATUS.write_text(json.dumps(X.STATE, indent=1), encoding="utf-8")
        try:
            await asyncio.wait_for(stop.wait(), timeout=20)
        except asyncio.TimeoutError:
            pass
    X.STATE.update({"updated": int(time.time()), "stopped": True})
    STATUS.write_text(json.dumps(X.STATE, indent=1), encoding="utf-8")


async def main(until):
    stop = asyncio.Event()
    X.STATE["started"] = int(time.time())
    await asyncio.gather(supervisor(stop, until), manager(stop, until))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", type=float, required=True)
    asyncio.run(main(ap.parse_args().until))
