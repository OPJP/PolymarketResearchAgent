"""Tolerant reader of the shared recorder's development files (same dev folder and record filter as tools/live.py
iter_live). Two artefacts make iter_live stop early: (1) a file still being written ends in an unflushed deflate block
(zlib.error, which iter_live does not catch); (2) when the recorder was restarted inside an hour (e.g. 2026-10-31
12:18 UTC) the hourly file holds a truncated gzip member followed by a new one, and everything after the truncation is
lost. Here every gzip member is decompressed separately (resync on the gzip magic), so both are handled.
Development blocks only unless ALLOW_SEALED is set by an examiner's driver."""
import calendar, json, sys, time, zlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa
ALLOW_SEALED = False
MAGIC = b"\x1f\x8b\x08"


def _members(raw: bytes):
    pos = 0
    while True:
        i = raw.find(MAGIC, pos)
        if i < 0:
            return
        d = zlib.decompressobj(31)
        try:
            out = d.decompress(raw[i:])
        except zlib.error:
            # truncated / corrupt member: keep what decompresses up to the error by feeding in chunks
            d = zlib.decompressobj(31)
            out, step, j = b"", 1 << 16, i
            while j < len(raw):
                try:
                    out += d.decompress(raw[j:j + step])
                except zlib.error:
                    break
                if d.eof:
                    break
                j += step
            yield out
            pos = i + 3
            continue
        yield out
        used = len(raw) - i - len(d.unused_data)
        pos = i + max(used, 3)
        if not d.eof:
            return


def iter_live(feed, start, end, allow_sealed=None):
    allow = ALLOW_SEALED if allow_sealed is None else allow_sealed
    parts = ["dev", "sealed"] if allow else ["dev"]
    files = [p for part in parts for p in (live.LIVE / part / feed).glob("*.jsonl.gz")]
    for p in sorted(files, key=lambda p: p.name):
        hour = calendar.timegm(time.strptime(p.name[:11], "%Y%m%dT%H"))
        if hour + 3600 <= start or hour >= end:
            continue
        raw = p.read_bytes()
        seen = set()  # per file
        for chunk in _members(raw):
            for line in chunk.decode("utf-8", errors="ignore").splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not (start * 1000 <= r.get("t", -1) < end * 1000):
                    continue
                key = (r.get("t"), r.get("a"), r.get("k"), r.get("s"))
                if key in seen:  # a member found twice by the resync
                    continue
                seen.add(key)
                yield r
