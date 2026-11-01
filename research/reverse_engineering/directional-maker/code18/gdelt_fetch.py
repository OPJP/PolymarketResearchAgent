"""iteration 18, T9 = X222 data: GDELT DOC 2.0 timelinevolraw (article counts) for 'bitcoin' and '(crypto OR fed OR cpi)',
2026-08-02..10-23 in 7-day chunks (hourly resolution is returned for 7-day ranges; verified 13:00 UTC 11-01), one request
per 5.5 s. Output .cache/re/directional-maker/it18/gdelt_hourly.parquet (q, ts, n). Public news-volume data only."""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker/it18/gdelt_hourly.parquet"
URL = "https://api.gdeltproject.org/api/v2/doc/doc"
QS = {"bitcoin": "bitcoin", "macro": "(crypto OR fed OR cpi)"}


def main():
    import sys
    gap = float(sys.argv[1]) if len(sys.argv) > 1 else 5.5
    have = set()
    rows, log = [], []
    if OUT.exists():
        old = pd.read_parquet(OUT)
        rows = [tuple(r) for r in old[["q", "ts", "n", "norm", "res"]].itertuples(index=False, name=None)]
        have = {(q, int(t) // (7 * 86400)) for q, t in zip(old.q, old.ts)}
    d0 = datetime(2026, 8, 2, tzinfo=timezone.utc)
    d1 = datetime(2026, 10, 23, tzinfo=timezone.utc)
    with httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0"}) as cl:
        for name, q in QS.items():
            a = d0
            while a < d1:
                b = min(a + timedelta(days=7), d1)
                if (name, int(a.timestamp()) // (7 * 86400)) in have and (name, int(b.timestamp() - 3600) // (7 * 86400)) in have:
                    a = b
                    continue
                prm = {"query": q, "mode": "timelinevolraw", "startdatetime": a.strftime("%Y%m%d%H%M%S"),
                       "enddatetime": b.strftime("%Y%m%d%H%M%S"), "format": "json"}
                for attempt in range(3):
                    r = cl.get(URL, params=prm)
                    if r.status_code == 200:
                        break
                    time.sleep(2 * gap)
                log.append({"q": name, "a": a.isoformat(), "status": r.status_code})
                try:
                    js = r.json()
                    res = js.get("query_details", {}).get("date_resolution")
                    for p in js["timeline"][0]["data"]:
                        ts = int(datetime.strptime(p["date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp())
                        rows.append((name, ts, int(p["value"]), int(p.get("norm") or 0), res))
                except Exception as ex:  # noqa: BLE001
                    log[-1]["err"] = repr(ex)[:120]
                a = b
                time.sleep(gap)
    df = pd.DataFrame(rows, columns=["q", "ts", "n", "norm", "res"]).drop_duplicates(["q", "ts"])
    df.to_parquet(OUT)
    print(json.dumps({"rows": len(df), "by_q": df.groupby("q").size().to_dict(), "res": df.res.value_counts().to_dict(), "log": log[:3]}))


if __name__ == "__main__":
    main()
