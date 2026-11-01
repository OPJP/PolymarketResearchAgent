"""iteration 18 (X218 = mechanics P4 / information I17-4 live part): full-depth record of the BTC 5m (current + next) and
BTC 15m (current) books plus the reference feeds (code5/rawrec.py, dm_* feeds through tools/live.py's Writer) around
the first post-DST US equity opens: 11-02 13:15-13:50 UTC (the old 13:30 UTC slot, the placebo) and 14:15-14:50 UTC
(09:30 New York after the 11-01 DST change). 11-02 12-18 UTC is a development block (d + j = 4). Sleeps without network
until each start; hard stop 14:50 UTC 11-02; its own disk is capped at 60 MB (rawrec's dm_* cap raised by 60 MB over
the dm_* total at launch); memory as rawrec (< 100 MB).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code18/open_rec.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code5"))
import rawrec  # noqa: E402

D = 1793577600  # 2026-11-02 00:00 UTC
WINDOWS = [(D + 13 * 3600 + 900, D + 13 * 3600 + 3000), (D + 14 * 3600 + 900, D + 14 * 3600 + 3000)]
STATUS = HERE.parents[3] / ".cache" / "re" / "directional-maker" / "openrec_status.json"


def main():
    rawrec.DISK_CAP_MB = rawrec.dm_disk_mb() + 60.0
    log = {"cap_mb": rawrec.DISK_CAP_MB, "windows": WINDOWS, "runs": []}
    STATUS.write_text(json.dumps(log), encoding="utf-8")
    for a, b in WINDOWS:
        while time.time() < a:
            time.sleep(min(30.0, max(a - time.time(), 0.1)))
        if time.time() >= b:
            continue
        t0 = time.time()
        try:
            asyncio.run(rawrec.main(b))
            log["runs"].append({"start": t0, "end": time.time(), "ok": True})
        except Exception as ex:  # noqa: BLE001
            log["runs"].append({"start": t0, "end": time.time(), "ok": False, "err": repr(ex)[:300]})
        STATUS.write_text(json.dumps(log), encoding="utf-8")


if __name__ == "__main__":
    main()
