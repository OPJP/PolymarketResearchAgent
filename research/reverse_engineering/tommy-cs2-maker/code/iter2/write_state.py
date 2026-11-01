"""Update state.json for iteration 2 (catalog with panel X items, components with tags, target_metrics, ledger)."""
from __future__ import annotations

import json
from pathlib import Path

RES = Path(__file__).resolve().parents[2]
S = json.load(open(RES / "state.json", encoding="utf-8"))

S["primary_metric"] = "presence_auc"
S["status"] = "continue"
S["wall_reason"] = None
S["sealed_from"] = {"H": "2026-10-23T00:00:00Z", "released_lots": [], "future_examined_until": "2026-10-31T00:00:00Z"}
S["live_lab"] = [
    {"what": "own recorder v1, feed tommy_cs2_books (code/iter2/cs2_recorder.py, first version): unthrottled CLOB market-channel messages of every CS2 match/map-winner market in play, via live.Writer; stopped after 13 min (21 MB/h, too much disk)",
     "start": 1793457470, "end": 1793458210},
    {"what": "own recorder v2, feed tommy_cs2_near (code/iter2/cs2_recorder.py): same markets; price changes within 5c of the best bid/ask, near-touch snapshots every 30 s or when the best moves >= 2c, all last trades; filed dev/sealed by block via live.Writer; detached process, hard stop 2026-11-03 00:00 UTC, 280 MB cap",
     "start": 1793458232, "end": 1793664000},
]
S["live_split"] = {"note": "pre-registered 2026-10-31 for rules that need live books (none exist before 10-31)",
                   "BUILD": "development blocks before 2026-11-01 12:00 UTC (10-31 12-18, 11-01 06-12)",
                   "VALIDATE": "development blocks from 2026-11-01 18:00 UTC on"}
S["strategy_statement"] = (
    "CS2 in-play bot (maker regime from 10-16; before that a round-trip taker in GRID tier-1/2 events). "
    "[VALIDATE-only] Selection: whole events (match + all maps) of non-GRID tier-3 leagues (1win, Stake, PGL, Circuit X, DraculaN, NODWIN, ...; since 10-31 also CyberClash and FiReSPORTS), never an event with a GRID official-data series id (0/122), favouring events with high pre-game popularity; event-level rule AUC 0.954 vs activity baseline 0.892 (gain +0.062, p 0.002), recall 0.72 at lift 3.3. "
    "[VALIDATE-only] Maker: from game start it keeps 100-share BUY orders on whole cents on BOTH outcome tokens, joining the best bid (43% of filled orders exactly at the bid in live books; 24% at a touch rebuilt from all makers' filled orders), never sells, merges complete pairs (97% of shares paired, pair cost 0.978) and holds the residual; it does not pull its bids when other makers do, so the pack fills them. "
    "[VALIDATE-only live, small sample; hypothesis as a frozen rule] Taker trigger: about 0.3-1.0 s after other makers cancel the near-touch asks of one team without any trade (depth collapse; precedes 87% of its taker orders, random times 3%), it sends a FAK BUY of that team at the best ask + 0-2c (median fill 12%), acting on 5-8% of such collapses (the deeper ones that leave a stale best ask); the informed pack (0x4ebc2722 and a 3-wallet operator) does the same 0.3-0.5 s later; the bought team then gains +2.6-2.9c in 10 s and +4-5c in 60 s, with adverse >= 4c moves in 20-23% (in-round information, not known round results). "
    "[hypothesis] The cancelling makers have a faster game feed than the stream-priced makers; the wallet either reads their cancels from the public book or shares a similar feed slightly later. "
    "[VALIDATE-only] Economics: locked pair margins plus the informed taker legs; a generic public-data ladder in the same markets loses 5-10% and its per-market PnL correlates negatively with the wallet's.")
S["components"] = {
    "selection": {"confidence": 0.7, "tag": "VALIDATE-only",
                  "description": "Events (all markets) of non-GRID tier-3 leagues; GRID events never (0/122); event-level logistic (league rate with GRID zeroing + pre-game popularity) AUC 0.954 vs 0.892 baseline, recall 0.72 at lift 3.3 on VALIDATE."},
    "timing": {"confidence": 0.55, "tag": "hypothesis",
               "description": "Maker: continuous from game start (VALIDATE-only). Taker: 0.3-1.0 s (median 0.77) after a public depth collapse on one side of the book (other makers cancel, no trade); live-BUILD only (one dev block, 40 orders): S_col AUC 0.846 vs market-grouped CV prints baseline 0.512; live VALIDATE from 11-01 18:00 UTC."},
    "side": {"confidence": 0.6, "tag": "VALIDATE-only",
             "description": "Maker: both outcomes. Taker: the team whose asks collapsed (100% of matched orders on the collapse side); that team gains in 72-77% of cases within 60 s."},
    "price": {"confidence": 0.4, "tag": "VALIDATE-only",
              "description": "Maker: join the best bid on whole cents (43% exact in live books, 24% vs rebuilt touch, 11.5% vs last print); deeper ladder levels are censored. Taker: FAK at best ask (52%) or ask + 1-2c (29%)."},
    "size": {"confidence": 0.6, "tag": "VALIDATE-only",
             "description": "Maker 100 shares (88% VALIDATE, 78% live); taker sizes variable (1000/2000 caps early, odd later), not decoded."},
    "exit": {"confidence": 0.75, "tag": "VALIDATE-only",
             "description": "Never sells; merges complete pairs; holds the unpaired residual to resolution."},
}
cat = S["catalog"]
upd = {
    "A4b": ("tried", "Kalshi public API: 1,200 open events scanned, no CS2 or esports event; sportsbooks need keys (brief); bo3.gg bet_updates is a static Thunderpick pre-match line (info panel). No other venue prices these tier-3 CS2 maps in play."),
    "A5": ("tried", "Sports websocket has round scores only for GRID events (info panel); the wallet's events are non-GRID, so it cannot time their rounds. bo3.gg: no live coverage for the wallet's live matches today (live_coverage None); bo3 round durations do not align pack clusters better than permuted durations (round_align.json). HLTV blocked (403). Kick VOD stream clock = X4 (open)."),
    "A7": ("tried", "Recorded books (clob_wallets, dev block 10-31 12-18): a near-touch depth collapse by other makers' cancels precedes 87% of its taker orders (random 3%); live taker presence AUC 0.943 vs 0.529; maker orders join the best bid 43% (dev_books.json, collapse_*.json). prices-history unused."),
    "A8": ("tried", "No market-wide outage explains its activity dips: on 10-18 (375 trades) CS2 markets printed 2-4.6k taker trades per hour 11-19 UTC; minute gaps in the tapes follow the schedule. The dip matches the number of whitelisted events (6 on 10-18 vs 11-35 other days). The 10-29 pause is in a sealed lot."),
    "B2": ("tried", "Filled orders: lifetimes median 15.8 s; live books: filled maker orders at the bid 43%; cancellations of OTHER makers are the taker trigger (A7). Its own cancels: lost depth before its taker orders is not in 100-share units (11%), so it does not pull; own ladder depth not yet measured."),
    "B3": ("tried", "Touch rebuilt from every maker's filled orders: price = best known resting bid 24% (within 1c 40%); last print 11.5%; own last fill (match clock) 18.7%; live: join the bid 43% (price_touch.json, dev_books.json). Fair-value models not needed for the maker: it joins the touch."),
    "B9": ("tried", "MAKER_REBATE rows are daily without market ids (10-16..10-21: $50, $309, $27, $431, $423, $812), a stable 0.26-0.27% of its daily traded USD: no per-market rebate-pool selection is visible; the rebate scales with volume."),
    "C1": ("tried", "Owners via eth_call owner(): wallet 0x8af810f0..., P4e 0xbf6461fa..., P8a 0x875909d7... (different EOAs); co-maker 0xe8e1b119 has a different signature type. Funding graph not done."),
    "C2": ("tried", "Pack signs after the wallet (+0.48 s cluster; P4e -51 ms); following the pack's prints loses out of sample (iter 1). Today the pack also follows the book collapse, about 0.3 s after the wallet: a common trigger, not copying."),
    "C4": ("tried", "Whole history 06-16..10-22: regime switch on 10-16 from GRID tier-1/2 round-trip taking (99% of USD in GRID events, 46% sells) to non-GRID tier-3 buy-only making + FAK taking (0% GRID, 0 sells); within the maker regime size versions (iter 1). taker_regime.json."),
    "C4b": ("tried", "No market-parameter change (iter 1). The switch coincides with a change of universe to non-GRID events where the pack already operated since at least 09-26 (P4e in 48% of those events before 10-16). No Polymarket announcement found."),
    "C7": ("tried", "Self-matching: 0 of 1,698 taker transactions (16-22 Oct) include it as a maker; owners of the wallet and P4e differ. Referral income not checked."),
    "C8": ("tried", "Fingerprint: sigType 3 deposit wallet, builder = metadata = 0, salt ~ Math.random()*Date.now(), 100-share whole-cent maker orders, FAK takers at ask + 0-2c. One web search found only generic or sports two-sided makers (spfunctions/polymarket-sports-mm, LeapTech-Lab/poly-maker, warproxxx/poly-maker), none with CS2 logic or cancel-following."),
    "D2": ("tried", "Event-level logistic selection; live 0.5-s hazard-style taker presence on book state (collapse score)."),
    "D3": ("tried", "Generic two-sided ladder replay on the public tape (strict fills): loses 5-10%, per-market PnL corr with the wallet -0.06..-0.12 (pnl_replay.json)."),
    "X1": ("tried", "Reviewer (C4b): no fee / rewards / delay change on CS2 markets 10-01..10-22; the switch is a change of universe GRID -> non-GRID (taker_regime.json)."),
    "X2": ("open", "Reviewer: round-boundary Markov quoting. Boundary-only requoting rejected (iter 1); maker price = join the bid (live); Markov valuation of the taker filter untested."),
    "X3": ("ruled_out", "Reviewer: sports websocket CS2 map scores. For the wallet's (non-GRID) events the socket carries map scores only (info panel, 10-31 dev block); it cannot be the trigger source; where it has rounds (GRID) the market leads it by a median 23 s."),
}
for k, (st, ev) in upd.items():
    cat[k] = {"status": st, "evidence": ev}
X = {
    "X4": ("open", "info panel P1 (iter 1): Kick VOD stream clock (PDT + ffmpeg HUD diffs). Not run: needs downloading VOD video segments (~70 MB per map); the panel itself asked to confirm with the user first. Playlist PDT metadata alone was not fetched yet."),
    "X5": ("tried", "info panel P2: GRID id boundary. 0/122 GRID events traded; event-level frozen rule AUC 0.954 vs 0.892, gain +0.062 [0.019, 0.115], p 0.002, recall 0.72 at lift 3.3 (final_rule.py, selection_event.json). PIT (grid_pit.py, 14:20-15:14 UTC): the gridSeriesId key is attached 1.0-1.3 h before the start (CCT Europe and Gamers Club Masters got GRID ids, FiReSPORTS a null), never later in the checks. Own-recorder data: deep trade-free collapses 23.7% of collapses in non-GRID vs 5.4% in GRID events (grid_collapse.json)."),
    "X6": ("tried", "info panel P3: coverage fingerprint. Stream-channel prior +0.005 VALIDATE AUC (0.962 vs 0.957), platform +0.004 (not adopted); hltv.org-only events (no stream) never traded (0/12); bo3 live_coverage None for its live matches. A provider-level coverage list not found."),
    "X7": ("tried", "info panel P4: own recorder for all CS2 markets started (tommy_cs2_books, then tommy_cs2_near); book-event trigger measured on the shared recorder: depth collapse precedes 87% of its taker orders vs 3% random (collapse_trigger.json)."),
    "X8": ("open", "info panel P5: bo3 per-round team stats as labels; needs a round clock (bo3 durations do not align, round_align.json)."),
    "X9": ("tried", "info panel P6: 10-16 switch vs GRID: it left GRID events entirely on 10-16; the pack was already in its new leagues (taker_regime.json, pre-switch tapes)."),
    "X10": ("tried", "mechanics panel P1: pack clusters 1.31 per bo3 round (P4e 0.66, wallet 0.26); timing-only DP alignment to bo3 rounds = permuted control (5.0 vs 4.7 tight links/map): not round ends at bo3 resolution. Live part (b): the socket has no round scores for its events; the pack's live trigger is the same book collapse (46.5% drop before vs 2.9%)."),
    "X11": ("tried", "mechanics panel P2: child orders on the match clock. Own-fill anchor (match clock) 18.7% exact; rebuilt touch 24%; live join-bid 43%. Re-sign split (resign_split.py): filled maker signings in [+0.5, +2) s after public taker signings 3.7-4.1x control when the taker matched the wallet, 2.8-3.2x when it matched only others: both user and market channels."),
    "X12": ("tried", "mechanics panel P3: pair unit = taker order + complement maker orders signed 0.5-5 s later (477 of 1,631 parents; pair cost median 0.95): unit PnL BUILD +$3.3k (p 0.27), VALIDATE +$5.1k (p 0.14) vs parent leg +$5.2k (p 0.15) / +$3.9k (p 0.22): not significant per split (pair_unit.json)."),
    "X13": ("tried", "mechanics panel P4: live books (40 orders): taker size / depth up to its limit at signing median 1.22 (IQR 0.91-4.29), never equal; fill / that depth median 0.95: size is a cap above the stale depth left, which it takes almost fully (taker_size_depth.json). Stale-depth league score not built."),
    "X14": ("tried", "mechanics panel P5: owner recovery via owner(): wallet 0x8af810f0, P4e 0xbf6461fa, P8a 0x875909d7 (different); 3-wallet POLY_PROXY cluster owners not readable; funding graph and complementary sizing not done."),
    "X15": ("tried", "assumptions panel P1: P4e present in 39-48% of whitelisted non-GRID events, 0% of other non-GRID and of GRID events (before and after the switch); the sports socket has no round scores for its events; listing-level coverage proxies (stream channel, platform) add at most +0.005 AUC; hltv.org-only events never traded (0/12). The feed behind the cancels is not identified."),
    "X16": ("tried", "assumptions panel P2: taker regime fetched (72,639 activity rows 06-16..10-16) and 11,692 transactions of 10-01..10-15 decoded: all taker FAK orders, 58% BUY / 42% SELL, 99.5% in-play, fill fraction median 100% (vs 12% after the switch), GRID tier-1/2 universe (taker_regime.json, taker_regime_orders.json). Sign-to-block (real block times, 40 sampled txs) median 34 s, p95 291 s, min 2.1 s although secondsDelay = 1: pre-signed orders fired later, so the taker-regime signing time is not the decision time (maker regime: 2.4-4.5 s)."),
    "X17": ("tried", "assumptions panel P3: executable tape replays vs the wallet per market (BUILD / VALIDATE Pearson): strict-fill ladder -0.06 / -0.12, follow-pack -0.14 / -0.11, both -0.14 / -0.17, at-touch ladder -0.40 / +0.11 (pnl_replay.json, pnl_follow_pack.json): no positive rule; the per-market PnL is driven by the residual from its stale bids being hit by the pack."),
    "X18": ("tried", "assumptions panel P4: h1/h2 have no books or game feed (recordings start 10-31): the taker trigger can only be examined on future blocks (own recorder running); h1/h2 claims limited to selection, size, price vs last print, exit. Sports-api REST history probe not done."),
}
for k, (st, ev) in X.items():
    cat[k] = {"status": st, "evidence": ev}
S["catalog"] = cat
S["target_metrics"] = {
    "presence_auc": 0.8721, "selection_auc": 0.9538, "selection_recall": 0.722, "selection_lift": 3.302,
    "presence_baseline": 0.899, "selection_baseline": 0.8916, "side_accuracy": None, "side_baseline": None,
    "price_within_tick": 0.115, "pnl_corr_pearson": -0.121, "pnl_corr_spearman": -0.061,
    "coverage_fills": 0.9273, "coverage_abs_pnl": 0.9898}
S["target_metrics_notes"] = {
    "selection": "event level, frozen v2 rule with BUILD constants on VALIDATE (gain +0.062 [0.019, 0.115], p 0.002)",
    "presence": "fill per (market, 30-s bin), event score x in-play: still below the activity baseline (co-occurrence by construction)",
    "live_taker_presence": "dev block 10-31 12:00-15:00 only: collapse score AUC 0.847 vs prints-only 0.532 (40 orders, wallet markets); frozen rule over all CS2 markets with books 0.900 vs 0.437 (34 orders); not VALIDATE",
    "price": "last-print anchor; rebuilt touch 0.24; live join-the-bid 0.43",
    "pnl": "generic tape ladder (executable, strict fills); negative"}
S["best"] = {"rule_id": "tommy-v2-grid-league-collapse", "validate_metrics": {
    "events": 128, "events_traded": 36, "selection_auc": 0.9538, "selection_baseline": 0.8916, "selection_gain": 0.0622,
    "selection_gain_ci95": [0.0188, 0.1148], "selection_gain_p_le0": 0.002, "selection_recall": 0.722, "selection_lift": 3.302,
    "presence_auc": 0.8721, "presence_baseline": 0.899, "price_within_tick": 0.115, "price_within_cent": 0.305,
    "size_100_accuracy": 0.883, "pnl_corr_pearson": -0.121, "pnl_corr_spearman": -0.061}}
S["hypotheses"] = S.get("hypotheses", []) + [
    {"id": "H11", "family": "selection-event", "description": "Event-level: GRID zeroing + league rate + pre-game popularity (logistic)",
     "validate_metrics": {"selection_auc": 0.9538, "baseline": 0.8916, "gain": 0.0622, "p": 0.002, "recall": 0.722, "lift": 3.302}, "verdict": "best selection rule; gain at the significance edge"},
    {"id": "H12", "family": "regime", "description": "10-16 switch = GRID tier-1/2 round-trip taker -> non-GRID tier-3 maker+FAK", "validate_metrics": {"grid_usd_share_taker_regime": 0.99, "grid_usd_share_maker_regime": 0.0}, "verdict": "supported (descriptive)"},
    {"id": "H13", "family": "trigger-round-end", "description": "Pack/wallet taker clusters are round ends (bo3 timing alignment)", "validate_metrics": {"tight_links_per_map": 5.0, "permuted_control": 4.7}, "verdict": "not supported"},
    {"id": "H14", "family": "trigger-book-collapse", "description": "Taker BUY of team X within 2 s after the near-touch ask depth of X collapses without trades", "validate_metrics": {"live_recall_cs2": 0.76, "live_recall_all": 0.70, "live_precision": 0.037, "presence_auc": 0.847, "prints_baseline": 0.532, "n_orders": 40, "frozen_rule_all_markets_auc": 0.900, "frozen_rule_baseline": 0.437, "cv_market_grouped_gbm_prints_baseline": 0.512, "cv_logistic_prints_baseline": 0.413, "s_col_no_fit": 0.846}, "verdict": "supported on one dev block (live BUILD); VALIDATE pending (dev blocks from 11-01 18:00)"},
    {"id": "H15", "family": "outcome-replay", "description": "Generic two-sided tape ladder per-market PnL vs the wallet", "validate_metrics": {"pearson": -0.121, "spearman": -0.061}, "verdict": "rejected as an outcome model"},
    {"id": "H16", "family": "maker-price", "description": "Maker order joins the best bid", "validate_metrics": {"live_exact": 0.427, "rebuilt_touch_exact": 0.244, "last_print_exact": 0.115}, "verdict": "partial (censored fills)"},
]
S["data_sources"] = S.get("data_sources", []) + [
    "taker-regime activity 06-16..10-16 (activity_taker.parquet, 72,639 rows) + Gamma metadata of 2,645 markets",
    "Gamma event listing projection with gridSeriesId (events_meta.parquet)",
    "pre-switch taker tapes of 506 markets (09-26..10-15)",
    "dev-block (10-31 12-18) wallet activity, 2,264 decoded transactions, clob_wallets books",
    "own recorder tommy_cs2_books (all CS2 match/map markets, unthrottled)",
    "deposit-wallet owner() via eth_call; bo3.gg live list (dev-block units only)"]
it = {"n": 2, "minutes": 76, "best_validate_score": 0.8721,
      "families": ["event-level selection with GRID boundary", "taker-regime data and regime switch", "pack event clock vs bo3 rounds (DP alignment)",
                   "price path / reversal test", "rebuilt touch from matched orders", "live books: quote placement", "live books: depth-collapse trigger",
                   "owner recovery", "generic ladder PnL replay", "own all-market book recorder"]}
S["iterations"] = [x for x in S.get("iterations", []) if x.get("n") != 2] + [it]
S.setdefault("tool_bugs", [])
if not any("zlib" in b and "12:18" in b for b in S["tool_bugs"]):
    S["tool_bugs"].append("tools/live.py iter_live: hour-12 files of 10-31 are unreadable after the 12:18 UTC recorder restart (zlib.error, a new gzip member after an unterminated one); readers stop there")
json.dump(S, open(RES / "state.json", "w", encoding="utf-8"), indent=1)
print("ok", len(S["catalog"]), "catalog items;", sum(1 for v in S["catalog"].values() if v["status"] == "open"), "open")
