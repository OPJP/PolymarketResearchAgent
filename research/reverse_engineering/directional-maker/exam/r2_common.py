"""Examiner round 2 (lot f1), shared constants. Every sealed fetch goes through POLYREA_CACHE_DIR = .cache/exam/directional-maker."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parent
ROOT = HERE.parents[3]
EXC = ROOT / ".cache" / "exam" / "directional-maker"
EXC.mkdir(parents=True, exist_ok=True)
os.environ["POLYREA_CACHE_DIR"] = str(EXC)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WS / "code"))
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))

LOT = [(1793426400, 1793448000), (1793469600, 1793512800)]  # f1: 10-31 06-12, 10-31 18 - 11-01 06 (merged)
LOT_START, LOT_END = 1793426400, 1793512800
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
RES = WS / "results"


def in_lot(ts) -> bool:
    return any(a <= int(ts) < b for a, b in LOT)


def iter_feed(feed: str, start: float, end: float, need: bytes | None = None):
    """Examiner's tolerant reader of .cache/live/{dev,sealed}/<feed>/<hour>.jsonl.gz (receive time in [start, end)):
    every gzip member is decoded on its own and a corrupt member is skipped (tools/live.iter_live stops on zlib.error)."""
    import calendar
    import json
    import time as _t
    import zlib
    base = ROOT / ".cache" / "live"
    files = sorted((p for part in ("dev", "sealed") for p in (base / part / feed).glob("*.jsonl.gz")), key=lambda p: p.name)
    for p in files:
        hour = calendar.timegm(_t.strptime(p.name[:11], "%Y%m%dT%H"))
        if hour + 3600 <= start or hour >= end:
            continue
        raw = p.read_bytes()
        pos = 0
        while pos < len(raw):
            d = zlib.decompressobj(31)
            try:
                data = d.decompress(raw[pos:])
                nxt = len(raw) - len(d.unused_data)
                ok = True
            except zlib.error:
                data, ok = b"", False
                nxt = raw.find(b"\x1f\x8b\x08", pos + 1)
                nxt = len(raw) if nxt < 0 else nxt
            if ok and nxt <= pos:
                break
            for line in data.split(b"\n"):
                if not line or (need is not None and need not in line):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if start * 1000 <= r.get("t", 0) < end * 1000:
                    yield r
            pos = nxt
