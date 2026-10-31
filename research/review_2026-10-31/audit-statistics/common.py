"""Shared helpers: read cached user-pnl bodies straight from a scratch copy of the HTTP cache
(no network, no writes to the repo)."""
import json
import sqlite3
import sys
import zlib

REPO = "/home/user/PolymarketResearchAgent"
sys.path.insert(0, REPO)
SCR = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/audit-statistics"
DB = f"{SCR}/cache/http.sqlite"
AS_OF = 1793318400  # stage_a1.json evidence.subject.as_of (2026-10-30 00:00 UTC)

_db = None


def points(wallet: str):
    global _db
    if _db is None:
        _db = sqlite3.connect(DB)
    url = f"https://data-api.polymarket.com/v2/user-pnl?user={wallet.lower()}&interval=all&fidelity=1d"
    row = _db.execute("SELECT body FROM responses WHERE url=? ORDER BY fetched_at DESC", (url,)).fetchone()
    if row is None:
        return None
    d = json.loads(zlib.decompress(row[0]))
    return ((d or {}).get("data") or {}).get("points") or []


def stage_a1():
    return json.load(open(f"{REPO}/research/stage_a/stage_a1.json"))


def board():
    return json.load(open(f"{REPO}/research/stage_a/leaderboard_snapshot.json"))["rows"]
