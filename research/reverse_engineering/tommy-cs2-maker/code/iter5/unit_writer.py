"""Writer that files a record by its UNIT as well as by its receive time (iteration 5, information panel iter4 critique 1).

tools/live.py Writer files a record into .cache/live/sealed/ when its receive time lies in a sealed 6-h block. This
class adds the unit rule of the brief: a record of a unit (game / event) that STARTED in a sealed block is filed into
the sealed folder whatever its receive time, so a development-block file never holds a sealed unit's records and the
agent's dev reads cannot see them. Examiners read both folders with iter_live(..., allow_sealed=True); within one hour
the dev and the sealed file are both read (consumers sort by time).
The status counters of the recorders that use it count only records filed into the dev folder.
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402

KEY = "tommy-cs2-maker"


def unit_sealed(game_start: float) -> bool:
    """True if a unit starting at game_start is sealed for this strategy (calendar + released lots)."""
    try:
        return bool(sealed.is_sealed(float(game_start), KEY))
    except Exception:  # noqa: BLE001  (fail closed)
        return True


class UnitWriter:
    def __init__(self, feed: str):
        self.feed = feed
        self.fh: dict[str, tuple[Path, object]] = {}
        self.n_dev = 0

    def write(self, obj: dict, is_unit_sealed: bool) -> None:
        now = time.time()
        part = "sealed" if (is_unit_sealed or sealed.future_block_sealed(now)) else "dev"
        path = live.LIVE / part / self.feed / (time.strftime("%Y%m%dT%H", time.gmtime(now)) + ".jsonl.gz")
        cur = self.fh.get(part)
        if cur is None or cur[0] != path:
            if cur is not None:
                cur[1].close()
            path.parent.mkdir(parents=True, exist_ok=True)
            self.fh[part] = (path, gzip.open(path, "at", encoding="utf-8", compresslevel=6))
        self.fh[part][1].write(json.dumps(obj, separators=(",", ":")) + "\n")
        if part == "dev":
            self.n_dev += 1

    def flush(self) -> None:
        for _, h in self.fh.values():
            h.flush()

    def close(self) -> None:
        for _, h in self.fh.values():
            h.close()
        self.fh = {}
