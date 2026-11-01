"""iteration 17 (X214, information panel I16-4 step 2): record the Polymarket Perps index and mark for BTC / ETH / SOL
(instruments 6 / 7 / 8) from the keyless REST tickers endpoint (api.perpetuals.polymarket.com/v1/info/tickers; the index is
"computed from Pyth, Chainlink Data Streams, Hyperliquid", published every 200 ms; polled here about once a second).
Records {"t": receive ms, "i": instrument, "x": index_price, "m": mark_price, "l": last_price, "ts": server ms} through
tools/live.py's Writer (feed dp_perps, filed into dev / sealed by receive time's block). Hard stop --until (default
2026-11-03 00:00 UTC), disk cap 60 MB for the feed, status in .cache/re/directional-maker/perpsrec_status.json.
    python perpsrec.py [--until 1793750400] [--period 1.0]"""
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

URL = "https://api.perpetuals.polymarket.com/v1/info/tickers"
FEED = "dp_perps"
KEEP = {6, 7, 8}
STATUS = ROOT / ".cache/re/directional-maker/perpsrec_status.json"
CAP = 60 * 1024 * 1024


def feed_bytes():
    tot = 0
    for part in ("dev", "sealed"):
        d = live.LIVE / part / FEED
        if d.exists():
            tot += sum(f.stat().st_size for f in d.glob("*.jsonl.gz"))
    return tot


def main():
    until = 1793750400
    period = 1.0
    a = sys.argv[1:]
    if "--until" in a:
        until = int(a[a.index("--until") + 1])
    if "--period" in a:
        period = float(a[a.index("--period") + 1])
    w = live.Writer(FEED)
    cli = httpx.Client(timeout=10, headers={"User-Agent": "polyrea/0.1 (research)", "Accept": "application/json"})
    n = err = 0
    last_status = 0.0
    last_ts = {}
    while time.time() < until:
        t0 = time.time()
        try:
            r = cli.get(URL)
            if r.status_code == 200:
                for x in r.json():
                    i = int(x.get("instrument_id", -1))
                    if i in KEEP and x.get("timestamp") != last_ts.get(i):
                        last_ts[i] = x.get("timestamp")
                        w.write({"t": int(time.time() * 1000), "i": i, "x": x.get("index_price"), "m": x.get("mark_price"),
                                 "l": x.get("last_price"), "ts": x.get("timestamp")})
                        n += 1
            else:
                err += 1
                if r.status_code == 429:
                    time.sleep(5)
        except Exception:  # noqa: BLE001
            err += 1
            time.sleep(2)
        if time.time() - last_status > 60:
            w.flush()
            b = feed_bytes()
            STATUS.write_text(json.dumps({"t": int(time.time()), "written": n, "errors": err, "bytes": b, "until": until}))
            last_status = time.time()
            if b > CAP:
                break
        dt = period - (time.time() - t0)
        if dt > 0:
            time.sleep(dt)
    w.close()
    STATUS.write_text(json.dumps({"t": int(time.time()), "written": n, "errors": err, "bytes": feed_bytes(), "until": until, "stopped": True}))


if __name__ == "__main__":
    main()
