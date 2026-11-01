"""iteration 18 (X223 = information I17-4, historical part): 1-minute bars of IBIT, QQQ, SPY, COIN, MSTR (regular session)
for 2026-10-01..10-31 from the keyless Yahoo chart API (1-minute history is kept ~30 days, so it must be fetched now).
Public equity data only. Output .cache/re/directional-maker/it18/yahoo_1m.parquet (sym, ts, o, h, l, c, v)."""
import json
import sys
import time
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker/it18" / (sys.argv[3] if len(sys.argv) > 3 else "yahoo_1m.parquet")
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval=1m&period1={a}&period2={b}&includePrePost=false"
SYMS = ["IBIT", "QQQ", "SPY", "COIN", "MSTR"]
import sys
T0 = int(sys.argv[1]) if len(sys.argv) > 1 else 1790812800  # default 2026-10-01 00:00 UTC
T1 = int(sys.argv[2]) if len(sys.argv) > 2 else 1793404800  # default 2026-10-31 00:00 UTC


def main():
    rows = []
    log = []
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=30) as cl:
        for s in SYMS:
            a = T0
            while a < T1:
                b = min(a + 7 * 86400, T1)
                r = cl.get(URL.format(s=s, a=a, b=b))
                log.append({"sym": s, "a": a, "b": b, "status": r.status_code})
                if r.status_code == 200:
                    res = r.json()["chart"]["result"]
                    if res and res[0].get("timestamp"):
                        q = res[0]["indicators"]["quote"][0]
                        for i, t in enumerate(res[0]["timestamp"]):
                            rows.append((s, int(t), q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]))
                a = b
                time.sleep(1.0)
    df = pd.DataFrame(rows, columns=["sym", "ts", "o", "h", "l", "c", "v"]).drop_duplicates(["sym", "ts"])
    df.to_parquet(OUT)
    print(json.dumps({"rows": len(df), "by_sym": df.groupby("sym").size().to_dict(),
                      "first": str(pd.to_datetime(df.ts.min(), unit="s")) if len(df) else None, "log": log}))


if __name__ == "__main__":
    main()
