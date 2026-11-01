"""iteration 17, T9 = X199 part 1: crypto-price endpoint vs the dy_rtds stream at the same value stamps (BTC/ETH/SOL)."""
import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

BASE = "https://polymarket.com/api/crypto/crypto-price"
a, b = 1793520000, 1793527200
taus = list(range(a, b, 600))
stream = {}
for r in live.iter_live("dy_rtds", a - 5, b + 305):
    if r.get("tp") == "cl" and r.get("sy") in ("btc", "eth", "sol") and r.get("ts") is not None:
        _t = int(r["ts"]); _t = _t // 1000 if _t > 10**11 else _t
        stream.setdefault((r["sy"], _t), float(r["v"]))
cli = httpx.Client(timeout=20, headers={"User-Agent": "polyrea/0.1 (research)", "Accept": "application/json"})
rows = []
for sy in ("BTC", "ETH", "SOL"):
    for t in taus:
        try:
            r = cli.get(BASE, params={"symbol": sy, "variant": "fiveminute", "eventStartTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))})
            d = r.json() if r.status_code == 200 else {}
        except Exception as ex:  # noqa: BLE001
            d = {"err": repr(ex)[:80]}
        for stamp, key in ((t, "openPrice"), (t + 300, "closePrice")):
            e = d.get(key)
            s = stream.get((sy.lower(), stamp))
            rows.append({"sy": sy, "stamp": stamp, "endpoint": e, "stream": s,
                         "diff": (float(e) - s) if (e is not None and s is not None) else None})
        time.sleep(0.5)
out = {}
for sy in ("BTC", "ETH", "SOL"):
    x = [r for r in rows if r["sy"] == sy]
    d = [abs(r["diff"]) for r in x if r["diff"] is not None]
    rel = [abs(r["diff"]) / r["stream"] for r in x if r["diff"] is not None and r["stream"]]
    out[sy] = {"pairs": len(d), "requested": len(x), "max_abs_diff": max(d) if d else None,
               "max_rel_diff": max(rel) if rel else None, "missing_stream": sum(1 for r in x if r["stream"] is None),
               "missing_endpoint": sum(1 for r in x if r["endpoint"] is None)}
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "iter17_cl_parity.json").write_text(json.dumps({"summary": out, "rows": rows}, indent=1))
