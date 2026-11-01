"""Reader for the dm_* feeds of code5/rawrec.py: development folder only, gzip members decoded one by one (a member
cut off by a restart is read up to its last complete line). Same calendar rule as tools/live.py iter_live."""
from __future__ import annotations

import calendar
import json
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import sealed  # noqa: E402

LIVE = ROOT / ".cache" / "live"
ALLOW_SEALED = False
GZ_MAGIC = bytes([0x1F, 0x8B, 0x08])
NL = bytes([10])


def _is_member_start(raw: bytes, c: int) -> bool:
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        d.decompress(raw[c:c + 4096])
        return True
    except zlib.error:
        return False


def _members(raw: bytes):
    """Split a file of concatenated gzip members (some cut off by a killed writer) at the real member starts and
    decode each segment on its own; a cut-off member yields its complete lines up to the last flush."""
    cands, k = [], raw.find(GZ_MAGIC)
    while k >= 0:
        cands.append(k)
        k = raw.find(GZ_MAGIC, k + 1)
    starts = [c for c in cands if c == 0 or _is_member_start(raw, c)]
    for a, b in zip(starts, starts[1:] + [len(raw)]):
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        outs = []
        seg = raw[a:b]
        for x in range(0, len(seg), 4096):
            try:
                outs.append(d.decompress(seg[x:x + 4096]))
            except zlib.error:
                break
            if d.eof:
                break
        out = b"".join(outs)
        yield out[: out.rfind(NL) + 1]


def iter_dm(feed: str, start: float, end: float):
    parts = ["dev", "sealed"] if ALLOW_SEALED else ["dev"]
    files = [p for part in parts for p in (LIVE / part / feed).glob("*.jsonl.gz")]
    for p in sorted(files, key=lambda p: p.name):
        hour = calendar.timegm(time.strptime(p.name[:11], "%Y%m%dT%H"))
        if hour + 3600 <= start or hour >= end:
            continue
        raw = p.read_bytes()
        for chunk in _members(raw):
            for line in chunk.split(NL):
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                t = r.get("t", 0)
                if start * 1000 <= t < end * 1000 and (ALLOW_SEALED or not sealed.future_block_sealed(t / 1000)):
                    yield r
