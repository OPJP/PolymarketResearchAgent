"""Shared constants and loaders (development data only; nothing at or after H is ever read)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache/re/rn1-inplay-maker"
R = ROOT / "research/reverse_engineering/rn1-inplay-maker"
W = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
H = 1792713600
BUILD = (1790899200, 1792108800)
VALID = (1792108800, 1792713600)


def parse_ts(s):
    if s is None or (isinstance(s, float) and np.isnan(s)) or str(s) in ("None", "nan", ""):
        return None
    s = str(s).replace("Z", "+00:00").replace(" ", "T")
    if s.endswith("+00"):
        s = s + ":00"
    try:
        return int(datetime.fromisoformat(s).astimezone(timezone.utc).timestamp())
    except ValueError:
        return None


def load_activity(p0, p1, types=("TRADE",)):
    p1 = min(p1, H)
    parts = []
    for d in range(p0 - p0 % 86400, p1, 86400):
        f = C / "activity" / f"act_{d}.parquet"
        if f.exists():
            parts.append(pd.read_parquet(f))
    a = pd.concat(parts, ignore_index=True)
    a = a[(a["timestamp"] >= p0) & (a["timestamp"] < p1)]
    if types:
        a = a[a["type"].isin(types)]
    return a.reset_index(drop=True)


def load_chain(p0, p1):
    p1 = min(p1, H)
    parts = []
    for d in range(p0 - p0 % 86400, p1, 86400):
        f = C / "chain" / f"chain_{d}.parquet"
        if f.exists():
            parts.append(pd.read_parquet(f))
    c = pd.concat(parts, ignore_index=True)
    return c[(c["ts"] >= p0) & (c["ts"] < p1)].reset_index(drop=True)


def load_markets():
    f = C / "markets_1790899200_1792713600.parquet"
    m = pd.read_parquet(f)
    m["gst"] = [parse_ts(x) for x in m["gameStartTime"]]
    return m


SPORT_PREFIX = {
    "atp": "tennis", "wta": "tennis", "cs2": "esports", "lol": "esports", "dota2": "esports", "val": "esports",
    "nfl": "usfb", "cfb": "usfb", "nba": "usbb", "cbb": "usbb", "mlb": "baseball", "nhl": "hockey",
}


def family_of(slug: str) -> str:
    s = str(slug or "")
    p = s.split("-")[0]
    if p in SPORT_PREFIX:
        return SPORT_PREFIX[p]
    return "soccer_or_other"


def mtype_of(slug: str, smt: str | None) -> str:
    s = str(slug or "")
    if smt and smt not in ("None", "nan"):
        return str(smt)
    for k in ("exact-score", "total", "spread", "btts", "halftime", "map", "set", "games"):
        if k in s:
            return k
    return "other"
