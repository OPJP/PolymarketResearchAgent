"""directional-maker iteration 8: start code5/rawrec.py (full-depth unaggregated CLOB events of the current and next
BTC 5m and the current BTC 15m window, plus the reference feeds) at a gate time, so the next development block
(11-01 06:00-12:00 UTC) has a full-depth book for the generator tests (panel iter7 mechanics critique 5, M1, A3).
Sleeps (no network, no memory) until --start, then runs rawrec.main(--until). Disk cap and feeds as in rawrec.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code8/delayed_rawrec.py --start 1793512500 --until 1793534400
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code5"))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--until", type=float, required=True)
    a = ap.parse_args()
    while time.time() < a.start:
        time.sleep(min(30.0, max(a.start - time.time(), 0.1)))
    import rawrec  # noqa: E402
    asyncio.run(rawrec.main(a.until))
