"""I11-1 (X114): whole-history data-api activity of the three cluster wallets, first trade .. 2026-10-08 00:00 UTC
(the files activity_<name>.parquet already cover 10-08..22 and exam/activity_* the lot). Development data only
(everything here is before H). Fetched in 7-day chunks (memory), kept columns only, one parquet per wallet and chunk:
.cache/re/directional-maker/it12/hist/act_<name>_<chunkstart>.parquet. Status json for monitoring."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

H = 1792713600
END = 1791417600  # 2026-10-08 00:00 UTC
WALLETS = {
    "almach": ("0x3725d52f3c252e8374999cc8617292ea2608ad88", 1779408000),   # first row 2026-05-22
    "bosona": ("0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", 1780358400),   # 2026-06-02
    "momoney": ("0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", 1770163200),  # 2026-02-04 (sports first)
}
OUT = ROOT / ".cache/re/directional-maker/it12/hist"
KEEP = ["timestamp", "type", "conditionId", "asset", "side", "outcomeIndex", "price", "size", "usdcSize", "transactionHash", "slug"]
CH = 7 * 86400


def main() -> None:
    assert END < H
    OUT.mkdir(parents=True, exist_ok=True)
    pm = PolymarketData()
    status = {"done": [], "started": time.time()}
    # newest chunks first (the most useful months), wallets interleaved
    chunks = []
    for name, (w, first) in WALLETS.items():
        t = END - CH
        while t + CH > first:
            chunks.append((t, name, w, max(t, first)))
            t -= CH
    chunks.sort(key=lambda c: -c[0])
    for t, name, w, a in chunks:
        f = OUT / f"act_{name}_{t}.parquet"
        if f.exists():
            continue
        t0 = time.time()
        rows, srcs, cov = pm.activity(w, start=a, end=min(t + CH, END) - 1)
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df[(df["timestamp"] >= a) & (df["timestamp"] < min(t + CH, END))]
            df = df[[c for c in KEEP if c in df.columns]]
            for c in ("price", "size", "usdcSize"):
                if c in df:
                    df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")
        df.to_parquet(f, index=False)
        status["done"].append([name, t, len(df), cov.status, round(time.time() - t0, 1)])
        (OUT / "status.json").write_text(json.dumps(status))
        print(name, pd.to_datetime(t, unit="s").date(), len(df), cov.status, f"{time.time()-t0:.0f}s", flush=True)
        del rows, df
    status["finished"] = time.time()
    (OUT / "status.json").write_text(json.dumps(status))


if __name__ == "__main__":
    main()
