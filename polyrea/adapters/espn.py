"""ESPN public site API: game play-by-play with wall-clock times and win probability.

Used as external public data for in-play sports hypotheses. Each play has a
``wallclock`` (UTC, second resolution) and, for NFL/NBA/college football,
ESPN's post-play home win probability. ESPN does not publish when a play
became visible through its API; the wall clock is the time of the play, so any
information delay ``D`` is a parameter of the hypothesis, never assumed zero.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd

from polyrea.adapters.http import HttpClient, shared_client

BASE = "https://site.api.espn.com/apis/site/v2/sports"
LEAGUES = {
    "nfl": ("football/nfl", {}),
    "cfb": ("football/college-football", {"groups": 80, "limit": 400}),
    "nba": ("basketball/nba", {}),
    "wnba": ("basketball/wnba", {}),
    "cbb": ("basketball/mens-college-basketball", {"groups": 50, "limit": 400}),
    "mlb": ("baseball/mlb", {}),
    "nhl": ("hockey/nhl", {}),
}


@dataclass(frozen=True)
class Play:
    ts: int
    home_score: int
    away_score: int
    scoring: bool
    home_wp: float | None
    text: str


@dataclass(frozen=True)
class Game:
    league: str
    event_id: str
    home: str
    away: str
    start_ts: int
    plays: tuple[Play, ...]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def _team_names(comp: dict[str, Any]) -> set[str]:
    t = comp.get("team", {})
    names = {t.get("displayName", ""), t.get("shortDisplayName", ""), t.get("name", ""), t.get("location", ""), t.get("abbreviation", "")}
    nick = t.get("nickname")
    if nick:
        names.add(nick)
    return {_norm(n) for n in names if n}


def team_matches(polymarket_name: str, comp: dict[str, Any]) -> bool:
    pn = _norm(polymarket_name)
    names = _team_names(comp)
    if pn in names:
        return True
    disp = _norm(comp.get("team", {}).get("displayName", ""))
    return bool(pn) and (pn in disp or disp in pn)


class ESPN:
    def __init__(self, http: HttpClient | None = None):
        self.http = http or shared_client()

    def scoreboard(self, league: str, day: str) -> list[dict[str, Any]]:
        path, extra = LEAGUES[league]
        data, _ = self.http.get_json(f"{BASE}/{path}/scoreboard", {"dates": day, **extra}, adapter="espn.scoreboard", max_age=None if _past(day) else 1800)
        return data.get("events") or []

    def find_event(self, league: str, start_ts: int, team_a: str, team_b: str) -> dict[str, Any] | None:
        """ESPN event whose two competitors match the Polymarket outcome names (UTC date +/- 1 day)."""
        for offset in (0, -1, 1):
            day = pd.Timestamp(start_ts + offset * 86400, unit="s", tz="UTC").strftime("%Y%m%d")
            for ev in self.scoreboard(league, day):
                comps = ev.get("competitions", [{}])[0].get("competitors", [])
                if len(comps) != 2:
                    continue
                a = any(team_matches(team_a, c) for c in comps)
                b = any(team_matches(team_b, c) for c in comps)
                if a and b and abs(pd.Timestamp(ev["date"]).timestamp() - start_ts) < 6 * 3600:
                    return ev
        return None

    def game(self, league: str, event: dict[str, Any]) -> Game | None:
        path, _ = LEAGUES[league]
        data, _ = self.http.get_json(f"{BASE}/{path}/summary", {"event": event["id"]}, adapter="espn.summary", max_age=None)
        comps = event.get("competitions", [{}])[0].get("competitors", [])
        home = next((c for c in comps if c.get("homeAway") == "home"), None)
        away = next((c for c in comps if c.get("homeAway") == "away"), None)
        if home is None or away is None:
            return None
        plays_raw = data.get("plays") or [p for d in ((data.get("drives") or {}).get("previous") or []) for p in d.get("plays", [])]
        wp = {str(w.get("playId")): w.get("homeWinPercentage") for w in data.get("winprobability") or []}
        plays = []
        prev = (0, 0)
        for p in plays_raw:
            wc = p.get("wallclock")
            if not wc:
                continue
            hs, as_ = int(p.get("homeScore") or 0), int(p.get("awayScore") or 0)
            scoring = bool(p.get("scoringPlay")) or (hs, as_) != prev
            prev = (hs, as_)
            plays.append(Play(int(pd.Timestamp(wc).timestamp()), hs, as_, scoring, wp.get(str(p.get("id"))), (p.get("text") or "")[:120]))
        plays.sort(key=lambda x: x.ts)
        return Game(league, str(event["id"]), home["team"]["displayName"], away["team"]["displayName"], int(pd.Timestamp(event["date"]).timestamp()), tuple(plays))


def _past(day: str) -> bool:
    return pd.Timestamp(day, tz="UTC") < pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=2)
