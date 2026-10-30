import numpy as np
import pandas as pd

from polyrea.adapters.espn import Game, Play, team_matches
from polyrea.workflows.sports_study import _outcome_side, _stale_quote_pnl, annotate, favoured, reaction_stats, scoring_events

GAME = Game(
    "nba",
    "1",
    "Atlanta Hawks",
    "Miami Heat",
    1000,
    (
        Play(1000, 0, 0, False, 0.5, "tip"),
        Play(1100, 2, 0, True, 0.55, "Hawks score"),
        Play(1300, 2, 3, True, 0.48, "Heat three"),
    ),
)


def _prints(ts_list, side="home", wallet_mask=None):
    rows = []
    for i, ts in enumerate(ts_list):
        rows.append({"event_slug": "g", "ts": ts, "is_wallet": bool(wallet_mask[i]) if wallet_mask else False, "side_kind": side, "price": 0.5, "size": 10.0, "payout": 1.0, "fee_rate": 0.05})
    return pd.DataFrame(rows)


def test_team_matching_and_sides():
    assert team_matches("Atlanta Hawks", {"team": {"displayName": "Atlanta Hawks"}})
    assert _outcome_side("Atlanta Hawks", GAME) == "home"
    assert _outcome_side("Miami Heat", GAME) == "away"
    assert _outcome_side("Over", GAME) == "over"
    assert _outcome_side("Boston Celtics", GAME) is None


def test_scoring_events_and_favoured():
    ev = scoring_events(GAME)
    assert list(ev["ts"]) == [1100, 1300]
    hp, ap = ev["home_pts"].to_numpy(), ev["away_pts"].to_numpy()
    assert list(favoured("home", hp, ap)) == [1, -1]
    assert list(favoured("over", hp, ap)) == [1, 1]
    assert list(favoured("under", hp, ap)) == [-1, -1]


def test_annotate_respects_information_delay():
    ev = scoring_events(GAME)
    p = _prints([1103, 1108, 1305])
    a0 = annotate(p, ev, delay=0)
    assert list(a0["since"]) == [3, 8, 5]
    assert list(a0["fav"]) == [1, 1, -1]
    a5 = annotate(p, ev, delay=5)  # the Hawks basket is not known until 1105
    assert np.isnan(a5["since"].iloc[0]) and a5["since"].iloc[1] == 3
    # boundary: the Heat three (1300) becomes known at exactly 1305
    assert a5["since"].iloc[2] == 0 and a5["fav"].iloc[2] == -1
    a5b = annotate(_prints([1304]), ev, delay=5)  # one second earlier it still sees the Hawks basket
    assert a5b["since"].iloc[0] == 1304 - 1105 and a5b["fav"].iloc[0] == 1


def test_reaction_stats_and_shift_breaks_alignment():
    ev = scoring_events(GAME)
    p = _prints([1102, 1104, 1302, 1200, 1250], wallet_mask=[1, 1, 0, 0, 0])
    p.loc[2, "side_kind"] = "away"
    r = reaction_stats(annotate(p, ev, 0), window=10)
    assert r["wallet_share_reactive"] == 1.0 and r["wallet_direction_agree"] == 1.0
    shifted = reaction_stats(annotate(p, ev, 0, shift=500), window=10)
    assert not (shifted["wallet_share_reactive"] == 1.0)


def test_stale_quote_pnl_bins():
    ev = scoring_events(GAME)
    p = _prints([1102, 1150], wallet_mask=[1, 0])
    p.loc[0, "payout"] = 0.0  # stale quote picked off right after the play
    out = _stale_quote_pnl(annotate(p, ev, 0))
    assert out["wallet"]["0-5s"]["return"] == -1.0
    assert out["all_makers"]["30-60s"]["return"] == 1.0
