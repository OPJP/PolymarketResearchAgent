"""Sealed-data calendar for the deep reverse engineering (pre-registered on 2026-10-31).

Every strategy uses the same calendar. What differs between strategies is which exam lots have been
released to them, listed in ``research/reverse_engineering/<key>/results/sealed_state.json`` as
``{"released": ["h1", ...], "future_examined_until": <unix ts>}``.

* Before ``H`` (2026-10-23 00:00 UTC): development data for everyone.
* Historical sealed period ``[H, T0)`` (T0 = 2026-10-31 00:00 UTC): two exam lots by alternating UTC day,
  ``h1`` = 10-23, 10-25, 10-27, 10-29 and ``h2`` = 10-24, 10-26, 10-28, 10-30. Both reach the forward
  days after as_of.
* From ``T0`` on: 6-hour blocks starting 00, 06, 12 and 18 UTC. Block ``j`` of day ``d`` (days since T0)
  is sealed iff ``d + j`` is odd. Over any two days each time of day is once development and once sealed.
  Future exams take every sealed block that ended after the previous future exam and before this one
  (lots ``f1``, ``f2``, ...).
* A unit (crypto window, game, match) belongs to the day or block in which it starts; an event (an FOMC
  meeting, a deadline) to the one in which it resolves. All records of a sealed unit are sealed, whatever
  their timestamps.
* Live recordings (``tools/live.py``) are filed by receive time into ``.cache/live/dev`` and
  ``.cache/live/sealed``.

Command line (from the repository root)::

    .venv/Scripts/python.exe research/reverse_engineering/tools/sealed.py <key>
    .venv/Scripts/python.exe research/reverse_engineering/tools/sealed.py <key> --check 1792800000 1793500000
    .venv/Scripts/python.exe research/reverse_engineering/tools/sealed.py <key> --next-lot
    .venv/Scripts/python.exe research/reverse_engineering/tools/sealed.py <key> --release h1   (examiners only)
    .venv/Scripts/python.exe research/reverse_engineering/tools/sealed.py <key> --release f --until 1793500000
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

H = 1792713600  # 2026-10-23 00:00 UTC, the original holdout start
T0 = 1793404800  # 2026-10-31 00:00 UTC, start of the block calendar
DAY = 86400
BLOCK = 6 * 3600
LOTS = {"h1": (0, 2, 4, 6), "h2": (1, 3, 5, 7)}  # day offsets from H
BASE = Path(__file__).resolve().parent.parent


def lot_of(ts: float) -> str:
    """'dev', 'h1', 'h2', 'fdev' (a future development block) or 'f' (a future sealed block)."""
    if ts < H:
        return "dev"
    if ts < T0:
        day = int((ts - H) // DAY)
        return "h1" if day in LOTS["h1"] else "h2"
    return "f" if future_block_sealed(ts) else "fdev"


def future_block_sealed(ts: float) -> bool:
    k = int((ts - T0) // BLOCK)
    return (k // 4 + k % 4) % 2 == 1


def block_bounds(ts: float) -> tuple[int, int]:
    """The day (before T0) or 6-hour block (from T0) that contains ts."""
    if ts < T0:
        a = H + int((ts - H) // DAY) * DAY if ts >= H else int(ts // DAY) * DAY
        return a, a + DAY
    a = T0 + int((ts - T0) // BLOCK) * BLOCK
    return a, a + BLOCK


def load_state(key: str) -> dict:
    p = BASE / key / "results" / "sealed_state.json"
    if p.exists():
        st = json.loads(p.read_text(encoding="utf-8"))
        return {"released": list(st.get("released") or []), "future_examined_until": int(st.get("future_examined_until") or T0)}
    return {"released": [], "future_examined_until": T0}


def is_sealed(ts: float, key: str, state: dict | None = None) -> bool:
    """True if a record (or a unit starting / resolving) at ts is sealed for this strategy now."""
    st = state or load_state(key)
    lot = lot_of(ts)
    if lot in ("dev", "fdev"):
        return False
    if lot in LOTS:
        return lot not in st["released"]
    return block_bounds(ts)[0] >= st["future_examined_until"]


def intervals(key: str, start: float, end: float, sealed: bool, state: dict | None = None) -> list[tuple[int, int]]:
    """Merged [a, b) intervals within [start, end) that are sealed (or development) for this strategy."""
    st = state or load_state(key)
    out: list[list[int]] = []
    start, end = int(start), int(end)
    t = start
    while t < end:
        a, b = block_bounds(t)
        if t < H:
            a, b = t, min(H, end)
        lo, hi = max(a, start), min(b, end)
        if is_sealed(lo, key, st) == sealed:
            if out and out[-1][1] == lo:
                out[-1][1] = hi
            else:
                out.append([lo, hi])
        t = hi
    return [(a, b) for a, b in out]


def next_lot(key: str, now: float, state: dict | None = None) -> dict:
    """The data the next exam would use: the next unreleased historical lot, else the sealed future blocks
    that ended after the last future exam and before now."""
    st = state or load_state(key)
    for lot, days in LOTS.items():
        if lot not in st["released"]:
            iv = [(H + d * DAY, H + (d + 1) * DAY) for d in days]
            return {"lot": lot, "intervals": iv, "sealed_hours": len(iv) * 24}
    iv = []
    t = max(st["future_examined_until"], T0)
    while t + BLOCK <= now:
        a, b = block_bounds(t)
        if future_block_sealed(a) and b <= now:
            iv.append((a, b))
        t = b
    return {"lot": "f", "intervals": iv, "sealed_hours": len(iv) * BLOCK // 3600, "until": iv[-1][1] if iv else None}


def release(key: str, lot: str, until: float | None = None) -> dict:
    st = load_state(key)
    if lot in LOTS:
        if lot not in st["released"]:
            st["released"].append(lot)
    elif lot == "f":
        if until is None:
            raise SystemExit("--until is required for a future lot")
        st["future_examined_until"] = max(st["future_examined_until"], int(until))
    else:
        raise SystemExit(f"unknown lot {lot!r}")
    p = BASE / key / "results" / "sealed_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=1) + "\n", encoding="utf-8")
    return st


def _fmt(iv: list[tuple[int, int]]) -> str:
    g = lambda t: time.strftime("%Y-%m-%d %H:%M", time.gmtime(t))
    return ", ".join(f"[{g(a)}, {g(b)})" for a, b in iv) or "none"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("key")
    ap.add_argument("--check", nargs="*", type=float, help="timestamps to classify")
    ap.add_argument("--next-lot", action="store_true")
    ap.add_argument("--release", help="h1, h2 or f (examiners only)")
    ap.add_argument("--until", type=float)
    a = ap.parse_args()
    now = time.time()
    if a.release:
        print(json.dumps(release(a.key, a.release, a.until)))
        return
    st = load_state(a.key)
    if a.check:
        for ts in a.check:
            print(int(ts), "sealed" if is_sealed(ts, a.key, st) else "development", lot_of(ts))
        return
    if a.next_lot:
        print(json.dumps(next_lot(a.key, now, st)))
        return
    print(f"{a.key}: released {st['released'] or 'none'}; future examined until {time.strftime('%Y-%m-%d %H:%M', time.gmtime(st['future_examined_until']))} UTC")
    print("development from H to now:", _fmt(intervals(a.key, H, now, False, st)))
    print("sealed from H to now:     ", _fmt(intervals(a.key, H, now, True, st)))
    b = block_bounds(now)
    print(f"current block [{time.strftime('%H:%M', time.gmtime(b[0]))}, {time.strftime('%H:%M', time.gmtime(b[1]))}) UTC is", "sealed" if is_sealed(now, a.key, st) else "development")


if __name__ == "__main__":
    main()
