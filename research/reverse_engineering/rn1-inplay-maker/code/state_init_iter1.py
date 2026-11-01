"""Iteration 1: writes the initial state.json (catalog, dimensions, legacy indicators, pre-registration)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_lib import CATALOG_IDS, TARGET_KEYS, save, set_catalog, set_dim  # noqa: E402

s = {
    "strategy": "rn1-inplay-maker",
    "wallets": ["0x2005d16a84ceefa912d4e380cd32e7ff827875ea"],
    "primary_metric": ("presence_auc (pre-registered in iteration 1): VALIDATE 2026-10-16..22 ROC AUC of the rule's score for "
                       "'RN1 has >= 1 maker fill in this (market, 60-s bin)' over cells of the sampled events' markets "
                       "(all sibling markets) in [gameStart-2h, gameStart+5h] that have >= 1 public taker print in the bin; "
                       "point in time, no own-state features"),
    "split": {"BUILD": [1790899200, 1792108800], "VALIDATE": [1792108800, 1792713600],
              "live_only": "development 6-h blocks after T0: day d BUILD iff floor(d/2) even (10-31, 11-01 BUILD; 11-02, 11-03 VALIDATE)"},
    "status": "continue",
    "wall_reason": None,
    "sealed_from": {"H": 1792713600, "T0": 1793404800, "released_lots": [], "future_examined_until": 1793404800},
    "live_lab": [],
    "strategy_statement": "",
    "components": {},
    "catalog": {},
    "target_metrics": {k: None for k in TARGET_KEYS},
    "best": {"rule_id": None, "validate_metrics": {}},
    "hypotheses": [],
    "data_sources": [],
    "dimensions": {},
    "indicators": [],
    "iterations": [],
}
for c in CATALOG_IDS:
    set_catalog(s, c, "open", "")

# E1 dimension inventory (iteration 1). Fields: family, status, source, resolution, publication_latency,
# best_indicator, min_detectable_share, verdict.
D = [
    ("clob_book_levels", "polymarket_internal", "proxy", "live lab clob_wallets (post-T0 dev blocks); pre-H only the tape", "200 ms top-10, 30 s full", "ws push", None),
    ("public_tape", "polymarket_internal", "have", "data-api /trades (taker and maker rows) per market", "1 s", "block time", None),
    ("other_wallets", "polymarket_internal", "have", "tape wallets; V2 calldata of every order in the tx", "1 s / ms signing", "block time", None),
    ("listings_metadata", "polymarket_internal", "have", "Gamma markets/events (listing fields only)", "per market", "at listing", None),
    ("market_comments", "polymarket_internal", "missing", "Gamma /comments (parent_entity_type, parent_entity_id)", "per post", "post time", None),
    ("fees_rebates_rewards", "polymarket_internal", "have", "activity MAKER_REBATE/TAKER_REBATE/REWARD rows; Gamma feeSchedule, rewards params", "daily", "daily", None),
    ("taker_delay", "polymarket_internal", "have", "Gamma secondsDelay (1 s on 98.7% of its markets)", "per market", "at listing", None),
    ("operational_events", "polymarket_internal", "missing", "Polymarket status page / engine restarts", "event", "unknown", None),
    ("sibling_markets", "related_markets", "have", "tapes of all markets of the same event", "1 s", "block time", None),
    ("sportsbook_odds", "related_markets", "blocked", "Pinnacle / bet365 / odds APIs need keys", "sub-second", "unknown", None),
    ("betfair_exchange", "related_markets", "blocked", "Betfair stream API needs a key", "50 ms", "unknown", None),
    ("kalshi_sports", "related_markets", "missing", "Kalshi public market data (sports)", "trade", "unknown", None),
    ("espn_pbp", "event_state", "have", "polyrea.adapters.espn play-by-play wall clocks, win probability", "1 s", "~3.5 s after the public price jump (soccer goals)", None),
    ("polymarket_sports_ws", "event_state", "have", "live lab feed 'sports' (live-only, from 2026-10-31)", "push", "unknown (to measure, X2)", None),
    ("official_data_feed", "event_state", "blocked", "Sportradar / Genius / IMG Arena official feeds (commercial)", "sub-second", "fastest", None),
    ("tennis_courtside", "event_state", "infeasible", "in-venue scouts; no public trace", "point", "fastest", None),
    ("esports_feeds", "event_state", "missing", "GRID (signup, blocked), HLTV (Cloudflare), bo3.gg / liquipedia (to try)", "round", "unknown", None),
    ("video_streams", "event_state", "missing", "broadcast / Twitch stream with delay", "frame", "stream delay", None),
    ("settlement_oracle", "event_state", "missing", "UMA proposals and disputes for sports markets", "event", "minutes-hours", None),
    ("news_wires", "information", "missing", "GDELT, Google News RSS (team news, injuries, lineups)", "15 min", "minutes", None),
    ("social_media", "information", "blocked", "X blocked; proxies Telegram previews, Reddit RSS, Bluesky", "post", "seconds-minutes", None),
    ("official_calendars", "information", "have", "Gamma gameStartTime, ESPN schedules", "per game", "days ahead", None),
    ("own_inventory", "own_state", "have", "its fills (activity / OrderFilled)", "fill", "own", None),
    ("own_pnl_drawdown", "own_state", "have", "fills + settlement (outcome only for PnL)", "fill", "own", None),
    ("own_capital", "own_state", "proxy", "on-chain collateral balance (pUSD/USDC) at blocks", "block", "own", None),
    ("time_of_day", "operator", "have", "clock", "s", "0", None),
    ("human_reaction", "operator", "have", "B1 signing times (ms)", "ms", "0", None),
    ("restarts_maintenance", "operator", "proxy", "gaps in its signing-time stream", "s", "0", None),
    ("bot_loop_cadence", "operator", "have", "B1 signing ms fractions and inter-order gaps", "ms", "0", None),
    ("latency_colocation", "infrastructure", "have", "B1 signing -> block time; taker order ages", "ms", "0", None),
    ("api_outages", "infrastructure", "missing", "Polymarket status history, engine restart notices", "event", "unknown", None),
]
for name, fam, st, src, res, lat, best in D:
    set_dim(s, name, family=fam, status=st, source=src, resolution=res, publication_latency=lat, best_indicator=best,
            min_detectable_share=None, verdict="untested")

# legacy indicators (earlier studies, entered as they were)
legacy = [
    ("own_tape_calm_logit", "public_tape", "reviewer logistic on own-tape calm (range 30/120 s, prints)", "level",
     {"test_auc": 0.531, "perm_p": 0.589, "n_test": 20881, "test_markets": 80}, "no_effect_legacy"),
    ("sibling_market_jumps", "sibling_markets", "jumps of 3/5/10 c in sibling markets", "jump",
     {"test_auc": 0.563, "perm_p": 0.115, "test_markets": 72}, "no_effect_legacy"),
    ("espn_time_since_goal", "espn_pbp", "time since ESPN soccer goal", "event features",
     {"test_auc": 0.547, "perm_p": 0.18}, "no_effect_legacy"),
    ("absence_after_soccer_goal", "espn_pbp", "share of touch fills in the window after an ESPN goal, RN1 vs other makers", "ESPN goal",
     {"rn1_share": 0.060, "others_share": 0.129, "p": 0.0005, "held_out_games_in_direction": "23 of 32"}, "drives_absence_legacy"),
    ("espn_scoring_play_first5s", "espn_pbp", "share of passive fills in the first 5 s after ESPN scoring plays", "ESPN scoring play",
     {"rn1_share": 0.014, "all_makers_share": 0.049}, "drives_absence_legacy"),
    ("tape_jump_5c_30s", "public_tape", "seconds since a 5-cent tape jump within 30 s", "jump",
     {"rn1_share_fills_0_5s": 0.078, "others_share_fills_0_5s": 0.146}, "drives_absence_legacy"),
]
for name, dim, definition, ev, res, verdict in legacy:
    s["indicators"].append({"name": name, "dimension": dim, "definition": definition, "event": ev, "period": "legacy",
                            "result": res, "verdict": verdict})

s["catalog"]["X1"] = {"status": "open", "evidence": "", "source": "reviewer lead 2026-10-31: Combos/RFQ flow (Gamma rfqEnabled) as a hedge or a source of its two-sided quoting"}
s["catalog"]["X2"] = {"status": "open", "evidence": "", "source": "reviewer lead 2026-10-31: Polymarket sports websocket latency against ESPN and against its V2 order signing times"}
save(s)
print("state.json written", len(s["catalog"]), "catalog items", len(s["dimensions"]), "dimensions")
