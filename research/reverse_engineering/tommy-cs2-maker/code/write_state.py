"""Write state.json for the current iteration from the result files (iteration 1)."""
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
fr = json.load(open(R / "results/final_rule_validate.json"))
tm = {"presence_auc": fr["presence_auc"], "selection_auc": fr["selection_auc"], "selection_recall": fr["selection_recall"],
      "selection_lift": fr["selection_lift"], "presence_baseline": fr["presence_baseline"], "selection_baseline": fr["selection_baseline"],
      "side_accuracy": None, "side_baseline": None, "price_within_tick": fr["price_within_tick"], "pnl_corr_pearson": None,
      "pnl_corr_spearman": None, "coverage_fills": 0.9273, "coverage_abs_pnl": 0.9898}


def it(status, ev):
    return {"status": status, "evidence": ev}


catalog = {
    "A1": it("not_applicable", "CS2 match/map markets resolve on the match result (Gamma resolutionSource https://hltv.org); no price-feed settlement."),
    "A2": it("not_applicable", "No crypto underlying: all 229 maker-regime markets are CS2 (220) or Dota 2 (9) match/map winners."),
    "A3": it("not_applicable", "No crypto underlying (see A2)."),
    "A4": it("tried", "Sibling markets (match vs maps) before its taker orders: share with a >= 2c sibling move in the prior 5 s 3.2% vs 2.3% at random times; prior 10 s 5.6% vs 3.7%: no cross-market lead (results/taker_trigger.json)."),
    "A4b": it("open", "Other venues pricing the same CS2 matches (sportsbooks need keys per the brief; Kalshi CS2 coverage unchecked)."),
    "A5": it("open", "A5a sports websocket verified (per-round CS2 scores; gameId = PandaScore id = Gamma eventMetadata.pandascoreMatchId); latency vs its signing pending: no development-unit match of its leagues recorded yet. bo3.gg in-round data and stream delay untested. League feeds (MLB/NHL/NBA) not applicable."),
    "A6": it("not_applicable", "No event/news markets traded."),
    "A6b": it("not_applicable", "No FOMC markets traded."),
    "A7": it("open", "Tape prints used (lead tests, next-jump test); Gamma fee params checked; recorded books (clob_wallets) not yet usable for its leagues; prices-history unused."),
    "A8": it("open", "Operational events (restarts, pauses) not yet matched to its activity."),
    "B1": it("tried", "29,936 wallet txs decoded (25,878 orders: signing ms, full size, limit price) + 79,234 public taker txs of its markets (results/describe_orders.json, timing_xcorr.json)."),
    "B2": it("open", "Resting lifetimes of filled orders measured (median 15.8 s); ladders 1c apart; cancellations need the books (live lab)."),
    "B3": it("open", "Quote-vs-last-print lead is mechanical (same for 30 other makers); fair-value inverse fit vs the touch not done."),
    "B4": it("tried", "BUY-only; 2,129 MERGE rows; 97.4% of bought shares paired; pair cost 0.9785 (results/inventory.json)."),
    "B5": it("tried", "67% of its maker fills on the short-inventory side; taker side independent of inventory (49/50); residual unpaired median 29% of max |net| (results/size_taker.json, inventory.json)."),
    "B6": it("tried", "Maker rebates $2.05k (17-22 Oct) and taker rebates $2.2k vs settlement PnL $13.1k on 16-22 Oct: material but not the main source."),
    "B7": it("ruled_out", "REWARD rows total $1 on 15-22 Oct although 85% of its orders are 100 shares within 4.5c: rewards are not a driver."),
    "B8": it("ruled_out", "holdingRewardsEnabled = False on its markets (Gamma)."),
    "B9": it("open", "Rebate pool share by market not computed."),
    "C1": it("open", "Co-maker 0xe8e1b119 appears in 8,040 of its transactions but has signatureType 2 (wallet: 3) and 20/5/40-share orders (wallet: 100): different client set-up, not a sibling by fingerprint; funding / owner checks pending for it and for the informed-taker pack (0x93078b5d sigType 1, 0x4ebc2722 sigType 3)."),
    "C2": it("open", "Cross-correlogram vs every taker done (all makers react about +1 s after takers sign). Same-team takers after its taker orders (0x93078b5d, 0x4ebc2722, 0xfe8a28be, 0x2529c68d, 0x72aaaaf9, 0x2005d16a) print in the same or next block (lag 0-3 s), not with a copy delay: common trigger, not copying (results/copy_leadlag.json). Whether IT follows anyone (signing-time lead-lag vs these wallets) still open."),
    "C3": it("tried", "3,111 distinct counterparties, top-10 share 19%: no single predictable victim (results/describe_orders.json)."),
    "C4": it("open", "Inside the maker regime (results/versions_by_day.json): 10-share maker orders appear only on 10-22 (20% of that day, 0 before); taker orders of exactly 1000/2000 shares fall from 52-64% (10-17/18) to 31-33% (10-19/20) and 12-17% (10-21/22); 100-share share 67% on 10-16 (start-up). Versions not yet decoded separately."),
    "C4b": it("open", "Gamma market parameters of CS2 match markets identical 10-01..10-22 (fee schedule, secondsDelay, rewards): no listing-level change; program-level announcements not found by one web search (a CFTC filing mentions a 2026 market-maker program on Polymarket US)."),
    "C5": it("tried", "Selection is by league, not hour: inside 09-19 UTC CCT Europe 0/52 and ESEA 0/37 while 1win Private Club 10/10 (results/selection.json); all activity 08-23 UTC following its league schedules; taker submissions automated (sign-to-block 2.4-4.5 s, uniform ms)."),
    "C6": it("tried", "All 29,936 wallet transactions are V2 matchOrders (no RFQ/combo calls); rfqEnabled False on its markets."),
    "C7": it("open", "Self-matching / related wallets not checked."),
    "C8": it("open", "Fingerprint: signatureType 3, builder = metadata = 0, salt median 9.0e11, uniform like Math.random()*Date.now() (TypeScript client; shared by the other bots, not distinctive), 100-share whole-cent ladders; GitHub search not done."),
    "D1": it("tried", "Unit = the order (B1): orders.parquet with signing times."),
    "D2": it("open", "Hazard / HMM / sequence models not tried."),
    "D3": it("open", "Order-by-order replay against books not possible without books for its leagues (live lab pending)."),
    "D4": it("tried", "Settlement PnL $13.1k = maker fills about +$4.0k (+0.47%) + taker fills about +$9.1k (+5.98%); locked pairs $21.6k, unpaired residual -$8.4k (results/inventory.json)."),
    "X1": it("open", "Reviewer (2026-10-31): Polymarket policy / rewards / fee change at the 10-16/17 switch (C4b). Market-level parameters ruled out; program-level change open."),
    "X2": it("open", "Reviewer (2026-10-31): quotes move only at map/round boundaries from a round-score Markov model. Boundary-only requoting rejected (14.1% of maker signings within 15 s after a round-end proxy vs 8.1% at random; 59% more than 60 s after); Markov valuation untested."),
    "X3": it("open", "Reviewer (2026-10-31): sports websocket CS2 map scores. Feed verified (per-round scores, PandaScore ids); its latency vs the wallet's signing awaits a development-unit match of its leagues."),
}
hyp = [
    {"id": "H1", "family": "presence", "description": "LightGBM fill presence per 30-s bin, activity + league rate (M1)", "validate_metrics": {"presence_auc": 0.952, "baseline_B0": 0.9417}, "verdict": "co-occurrence: gain 0.010"},
    {"id": "H2", "family": "selection", "description": "League score s_meta (BUILD target encoding) on CS2 match/map markets", "validate_metrics": {"selection_auc": 0.8765, "recall": 0.636, "lift": 2.646, "baseline": 0.8816, "combined_with_activity": 0.9198}, "verdict": "describes selection; no gain over the pre-game activity baseline"},
    {"id": "H3", "family": "quote-lead", "description": "Its burst-top bid minus the last print predicts the next public move", "validate_metrics": {"corr10": 0.608, "b120": 0.85}, "verdict": "mechanical: same for 30 other makers (maker_compare.json)"},
    {"id": "H4", "family": "timing", "description": "Maker signings follow public taker signings within about 1 s", "validate_metrics": {"peak_ratio": 2.97, "controls": "2.2-2.9"}, "verdict": "true but shared with every maker"},
    {"id": "H5", "family": "taker-information", "description": "Taker orders predict the next round-end price jump", "validate_metrics": {"next_jump_in_favour": 0.642, "control": 0.538, "settlement_edge_pct": 5.25}, "verdict": "supported: informed component; input unknown (in-round state)"},
    {"id": "H6", "family": "taker-public-rule", "description": "Public contrarian taker: buy a team after a >= D drop within W s", "validate_metrics": {"edge_pct": -7.52, "overlap_with_wallet": 0.035}, "verdict": "rejected"},
    {"id": "H7", "family": "cross-market", "description": "Taker orders triggered by sibling-market moves", "validate_metrics": {"sib5_up2c": 0.032, "control": 0.023}, "verdict": "rejected"},
    {"id": "H8", "family": "round-boundary", "description": "Maker requotes only at round boundaries (X2 strong form)", "validate_metrics": {"share_within_15s": 0.141, "control": 0.081}, "verdict": "rejected"},
    {"id": "H9", "family": "exit", "description": "Merge pairs, hold residual, never sell", "validate_metrics": {"paired_share": 0.974, "pair_cost": 0.9785}, "verdict": "supported (descriptive)"},
    {"id": "H10", "family": "size", "description": "Maker orders are 100 shares", "validate_metrics": {"size_100_accuracy": 0.883}, "verdict": "supported (descriptive)"},
]
state = {
    "primary_metric": "presence_auc",
    "primary_metric_definition": "VALIDATE AUC of a point-in-time score for 'wallet has >= 1 fill in (market, 30-s bin)' over every CS2 moneyline/child_moneyline market, bins gs..gs+4h, no own-state features (pre-registered in NOTES.md).",
    "split": {"BUILD": "gameStartTime in [2026-10-16, 2026-10-21)", "VALIDATE": "gameStartTime in [2026-10-21, 2026-10-23)"},
    "status": "continue", "wall_reason": None,
    "sealed_from": {"H": "2026-10-23T00:00:00Z", "released_lots": [], "future_examined_until": "2026-10-31T00:00:00Z"},
    "live_lab": [],
    "strategy_statement": (
        "CS2 in-play bot with two components. [VALIDATE-only] Selection: whole events (all map winners + the match winner) of a fixed set of leagues "
        "(1win / 1win Private Club, Stake Pulse / Ranked, PGL, Circuit X, DraculaN, NODWIN ...), never others (CCT, ESEA, ESL Challenger, United21, EPL); in-play only. "
        "[VALIDATE-only] Maker component: from game start it keeps re-signing ladders of 100-share BUY orders on whole cents, 1 cent apart, on BOTH outcome tokens "
        "(best bids sum about 0.97), re-signing within about 1 s of other traders' orders like every other maker; it never sells, merges complete pairs "
        "(97% of shares paired, pair cost 0.978) and holds the residual to resolution; its maker fills earn only +0.5% and are adversely selected. "
        "[VALIDATE-only] Taker component: limit orders (1000/2000 or odd sizes, limit about 1c above the touch, 12% filled) that buy the team which wins the round "
        "in progress about 30 s before the market reprices (next jump in favour 64-67% vs 51-54% at random times; event bootstrap gain +0.13 [0.095, 0.166] on VALIDATE), earning +5-7% and about 70% of settlement PnL. "
        "[VALIDATE-only] The two components are coupled: in the 30 s before a taker order 71-75% of its filled maker orders are on the same team (it keeps bidding the team "
        "while sellers hit it), and in the 0-120 s after it 58-64% are on the other team (re-pairing). "
        "[VALIDATE-only] Its taker orders lead a burst of other informed takers buying the same team (73% of same-team taker orders within +-10 s are signed after its own, 4x in the first 0.5 s), so the trigger is a sharply timed external game event that it sees among the fastest. "
        "[hypothesis] The taker input is live in-round game state (kills / man advantage / bomb) from a feed or stream; the maker quote placement vs the touch is not decoded."),
    "components": {
        "selection": {"confidence": 0.6, "tag": "VALIDATE-only", "description": "Whole events of a league whitelist (league score AUC 0.877 on VALIDATE; 0 of 5 dev-unit events of other leagues traded on 10-31); in-play only (99.1% of fills)."},
        "timing": {"confidence": 0.35, "tag": "hypothesis", "description": "Maker: continuous re-signing, peaks 0-1.5 s after public taker signings (shared with all makers). Taker: about 30 s before the next round-end jump; trigger input unknown."},
        "side": {"confidence": 0.4, "tag": "VALIDATE-only", "description": "Maker: both outcomes (BUY both tokens), fills skewed 67% to the short-inventory side. Taker: the team winning the round in progress (64-67% vs 53-54%)."},
        "price": {"confidence": 0.3, "tag": "VALIDATE-only", "description": "Maker: whole-cent ladders 1c apart, two-sided best bids sum about 0.97; last-print anchor exact only 11.5%. Taker: limit 0-2c above the best fill."},
        "size": {"confidence": 0.6, "tag": "VALIDATE-only", "description": "Maker 100 shares (88% on VALIDATE; 10 or 11-99 when inventory is small). Taker 1000/2000 (23%) or odd sizes (median 542)."},
        "exit": {"confidence": 0.75, "tag": "VALIDATE-only", "description": "Never sells; merges complete pairs (pair cost 0.978); holds the unpaired residual to resolution (ends on the loser 68%)."},
    },
    "catalog": catalog,
    "target_metrics": tm,
    "best": {"rule_id": "tommy-v1-league-ladder", "validate_metrics": fr},
    "hypotheses": hyp,
    "data_sources": ["data-api activity 15-22 Oct (activity_dev.parquet)", "Polygon OrderFilled V2 logs, topic2 = wallet, 16 Oct..H (publicnode)",
                     "V2 matchOrders calldata of 29,936 wallet txs and 79,234 public taker txs (publicnode eth_getTransactionByHash)",
                     "Gamma CS2 events/markets (series 10310) listing projection, 25 Sep..H and dev blocks after T0", "data-api taker tapes per market, [gs-1h, gs+4h10m]",
                     "live lab: sports websocket (per-round CS2 scores), clob_wallets books (dev blocks only)"],
    "iterations": [{"n": 1, "minutes": 75, "best_validate_score": fr["presence_auc"],
                    "families": ["B1 calldata orders", "maker comparison control", "ms timing xcorr", "taker information (next jump)", "public contrarian taker",
                                 "cross-market", "selection by league", "inventory/exit", "live lab sports feed"]}],
    "tool_bugs": ["tools/live.py iter_live does not catch zlib.error on the hour file being written (reader stops at the current hour)"],
}
json.dump(state, open(R / "state.json", "w"), indent=1)
print("ok", len(catalog), "open", sorted(k for k, v in catalog.items() if v["status"] == "open"))
