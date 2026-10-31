"""Clock check (iteration 3): this laptop's clock vs the CLOB server and HTTP Date headers.
Method: poll https://clob.polymarket.com/time (integer seconds) and HTTP Date headers of www.google.com /
clob.polymarket.com in a tight loop; the local time at which the server's second flips bounds the offset
(server - local) to the request round trip. Output: results/clock_probe.json"""
import json, time, sys
from pathlib import Path
import httpx
RES = Path(__file__).resolve().parents[2] / "results"
from email.utils import parsedate_to_datetime

def flips(url, kind, n=40):
    cli = httpx.Client(timeout=5, headers={"User-Agent": "polyrea-research"})
    out = []; prev = None
    for _ in range(n):
        t0 = time.time()
        try:
            r = cli.get(url) if kind == "time" else cli.head(url)
        except Exception as e:
            continue
        t1 = time.time()
        if kind == "time":
            sv = int(float(r.text.strip()))
        else:
            sv = int(parsedate_to_datetime(r.headers["date"]).timestamp())
        if prev is not None and sv == prev[0] + 1:
            # flip happened between prev request and this one: server second boundary sv at local time in [prev_t0, t1]
            out.append({"server_sec": sv, "local_lo": prev[1], "local_hi": t1, "rtt": t1 - t0})
        prev = (sv, t0)
        time.sleep(0.05)
    return out

res = {}
for name, url, kind in [("clob_time", "https://clob.polymarket.com/time", "time"),
                        ("google_date", "https://www.google.com", "date"),
                        ("clob_date", "https://clob.polymarket.com/time", "date")]:
    f = flips(url, kind)
    # offset = server - local at the boundary; local boundary in [lo, hi] -> offset in [sv - hi, sv - lo]
    offs = [(x["server_sec"] - x["local_hi"], x["server_sec"] - x["local_lo"]) for x in f]
    res[name] = {"n_flips": len(f), "offset_bounds_s": [[round(a, 3), round(b, 3)] for a, b in offs]}
print(json.dumps(res, indent=1))
json.dump({"ts": time.time(), **res}, open(RES / "clock_probe.json", "w"), indent=1)
