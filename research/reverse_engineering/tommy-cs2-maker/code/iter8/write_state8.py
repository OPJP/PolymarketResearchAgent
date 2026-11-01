"""Iteration 8 state.json update (catalog X101-X116, components, hypotheses, target metrics, best, iteration entry)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
P = ROOT / "research/reverse_engineering/tommy-cs2-maker/state.json"
s = json.loads(P.read_text(encoding="utf-8"))
cat = s["catalog"]

X = {
 "X101": ("open", "information panel P1 (iter 7): push channels behind public live pages (trackers, organisers, broadcasts)",
          "Not run: the whole iteration ran in the sealed block 11-01 00-06, and the test needs live pages of development-start units in play (no sealed unit may be opened). Runbook and scoring pre-registered in NOTES iteration 8 for 11-01 06-12 and later development blocks."),
 "X102": ("tried", "information panel P2 (iter 7): name the vendor from the feed's own coverage (P4e's event set as the label)",
          "vendor_boundary.json: P4e in-event presence on 384 CS2 events (16-22 Oct): GRID 0/122; non-GRID tier 3 22/22, tier 4 36/96, tier 5 0/144; in-sample AUC GRID 0.687, tier 0.907, GRID x tier 0.943, league 0.967; the wallet traded 87.9% of P4e's events vs 8.0% of the others. A tiered product with the GRID-exclusive events removed, no single rights holder. Dota 2: the slower subscribers are in 88% of events incl. GRID-flagged EPL Masters (91%). Step 4 (PandaScore's own tier) needs PandaScore docs / the X55 token."),
 "X103": ("tried", "information panel P3 (iter 7): Polymarket's own data provider as a latency yardstick, GRID as the positive control",
          "provider_latency.json (10-31 12-18 development units): sports-socket map-score update minus the market's terminal repricing: non-GRID (Dota incl.) n 20 min 16 s, p10 26 s [16, 65], median 169 s; GRID n 17 min 20 s, p10 47 s [20, 165], median 196 s. The provider is tens of seconds to minutes behind the market for both classes: it cannot be the feed and does not separate GRID from non-GRID. Gamma score polling (step 5) is redundant with this result."),
 "X104": ("tried", "information panel P4 (iter 7): the book as the carrier of its private events (prints-based markout, followers)",
          "print_markout.json: untriggered pulls on non-wallet taker prints (+5, +15] s -2.06c (30 of 213 with a print; null +0.10c, p 0.086), multi-level -3.84c (13), triggered +0.18c (161), GT other makers +2.35c (18): same sign as the mid markout, too few prints for significance. The follower stratification is the panel's (no followers -0.49c, n 87); reported next to test (c) on VALIDATE-live (pre-registered)."),
 "X105": ("tried", "information panel P5 (iter 7): value or raw events (cross-subscriber limits against the stale ask)",
          "cosigner_premium.json: wallet / P4e co-signed pairs 191 (86 markets): premium correlation 0.21 (0.20 given the 60-s move), limit difference SD 3.3c, within 1c 36%; P93 / P4e 193 pairs: 0.61 (0.59), SD 3.4c. No shared value at the cent level for the wallet: raw events, each subscriber prices its own take (P93 anchors on P4e's book)."),
 "X106": ("open", "information panel P6 (iter 7): outages as natural experiments (one source or two)",
          "Step 1 run (outage_gaps.json): the wallet's two idle-but-up gaps (10-17 16:43-17:22, 10-22 10:01-11:00): P4e 10.6 / 2.0 prints per hour vs 52.8 / 56.1 in the rest of the run, other subscribers 30 / 12 vs 88 / 179: game-phase lulls, not a wallet-side outage. Steps 2 (feed-wide outages with the socket's live fields) and 3 (common-mode lag shocks across titles) not run."),
 "X107": ("tried", "mechanics panel P1 (iter 7): validate the pull label with ground-truth cancels, then re-score Z4",
          "cancel_truth.json / gt_markouts.json (BUILD-live): 132 ground-truth remainder cancels (54 wallet); co-burst precision of the frozen pull label 0.955 (21/22; multi 15/16, single odd 6/6); other makers' GT cancels inside labelled bursts 1.3%; untriggered class not attributable by construction. GT wallet untriggered cancels (17): 10-s others'-mid -0.94c (null -0.06c, p 0.034); GT other makers untriggered (17) +0.74c (p 0.89). Z4 holds on the wallet's own ground-truth cancels; (c') / (c'') pre-registered for VALIDATE-live."),
 "X108": ("tried", "mechanics panel P2 (iter 7): the ladder manager as an explicit own-state machine (price item)",
          "ladder_machine.json (2,739 validated own adds, BUILD-live): touch - k 0.472 within one tick (first level 0.511); own-state machine (refill the slot vacated in 3 s, else touch / extend) 0.291 (halves 0.407 / 0.176); refill 0.255; own top 0.246; extend 0.089; oracle union of the four 0.726. No own-state rule of this family reaches 0.8; the touch stays frozen."),
 "X109": ("tried", "mechanics panel P3 (iter 7): handler identity, then the take filter conditional on a receipt",
          "handler_filter.json (BUILD-live): take-time pulls (37) 3.8 levels, re-post median 1,033 ms (59.5% at 1.00-1.15 s); untriggered multi-level pulls (74) 2.85 levels, next add median 261 ms (4.2% at 1.00-1.15 s); untriggered single pulls (139) replaced in 6 ms. Take vs strip-only logit on public execution state: CV AUC 0.515. Untriggered pulls are ladder re-pricing, not handler receipts; the take is not a public execution filter."),
 "X110": ("tried", "mechanics panel P4 (iter 7): recover the signing key of every order from its ERC-7739 nested signature",
          "sig_signers.json: pure-Python keccak / secp256k1; contents self-test 1,062 of 1,064 sigType-3 orders; eip712Domain = DepositWallet v1, chainId 137. All 273 sampled wallet orders (114 taker, 159 maker, 10-01..10-22, both regimes) recover to 0x8af810f0e236cae55588ea6a084013c24122fd4f = owner(); P4e, 0x8a80528d, 0xf1f2b3c6, 0x52661b8e recovered to distinct keys; no key shared by two of 316 makers in 333 transactions. C1 closed at the key level."),
 "X111": ("tried", "mechanics panel P5 (iter 7): one stream or two (lag by event class, residual coupling to P4e)",
          "lag_by_class.json (203 co-signed pairs, 44 events): isolated 53, reversal 50.5, follow-on 40 ms; MixedLM follow-on -10.9 ms (p 0.07), reversal -0.9 (p 0.84), event SD 8.0, residual 25.1 ms; reversal - follow-on +10 ms [-4, +22]; control 0x2005d16a - P4e similar (-12.5 / -10.9 ms, n.s.). No class-dependent offset >= 20 ms: one fan-out with the kind filter at the wallet. Step 2 (pull share at P4e-alone events live) waits for P4e takes on a recorded book (with X115); step 3 (geography) not run."),
 "X112": ("tried", "assumptions panel P1 (iter 7): scope: decode the Dota 2 module and report coverage on the lot in evaluate()",
          "coverage_iter8.json: CS2-only coverage of fills 0.846 on 10-22, 0.927 on VALIDATE, 0.425-0.457 on the 10-31 12-18 block (abs PnL 0.78-0.93); CS2 + Dota 1.000 everywhere. final_rule v4 adds the Dota universe (series 10309) with the v3 recipe and _coverage(); VALIDATE pooled selection 0.9528 vs 0.8863, recall 0.744, lift 3.25, coverage 1.0 / 1.0; forward block AUC 0.851, recall 0.5, lift 3.13. Dota module (dota_module.json): 10-share whole-cent ladders, 67 takes, merges in the CS2 300-s loop, GRID-flagged EPL Masters 0/33 traded."),
 "X113": ("tried", "assumptions panel P2 (iter 7): selection = the feed's coverage today from the subscribers' earlier takes",
          "selection_feedcov.json (pre-registered): cov24 VALIDATE AUC 0.850 vs all-takers control 0.798 (+0.052), unseen-league 0.763 vs 0.720; within non-GRID 0.820 < control 0.853 (the slower subscribers trade GRID events); p4e24 0.806 (recall 0.667, lift 2.94); BUILD-fitted activity + GRID + p4e24 0.944, + cov24 + all24 0.942 (unseen 0.980) vs v3 0.957 (unseen 0.928). v3 stays frozen; the variants join the forward pool."),
 "X114": ("tried", "assumptions panel P3 (iter 7): is the shared feed multi-sport (cross-sport fan-out, ESPN clock)?",
          "multisport_fanout.json (30,113 txs of 1,106 non-esports markets, 16-22 Oct): 0x2005d16a's 1,064 taker BUYs have 13 same-token co-signs by the 0x8a80528d / 0xddb6e624 process within 500 ms (30-s shift null 4.25; median +148 ms, IQR 122) and 1 with 0xf1ee4842 (null 0). The CS2 fan-out does not repeat in football / NBA / tennis: an esports product; the ESPN step is moot."),
 "X115": ("open", "assumptions panel P4 (iter 7): uncensor the fan-out (P(follower co-signs | depth left at its arrival)) on live books",
          "Not run: P4e and 0x2005d16a have no taker order in the recorded BUILD-live markets (10-31 12-18), so no leader take with a follower window exists on a recorded book yet; needs a development block where they trade."),
 "X116": ("tried", "assumptions panel P5 (iter 7): discrete message kinds vs a continuous private fair value (accumulation test)",
          "accumulation.json (BUILD-live, 22,011 1-s steps, 56 takes): take hazard by untriggered pulls in 10 s: 0.83% / 1.05% / 2.02% / 3.53% (0 / 1 / 2 / 3+); logit with public controls +0.48 per log1p count (p 0.051; 60 s +0.26, p 0.03); direction 64-71% aligned (n 7-11, p 0.13). Weak dose-response: weak support for a continuous private value; premium and add-top steps not run (n too small)."),
}
for k, (st, src, ev) in X.items():
    cat[k] = {"status": st, "source": src, "evidence": ev}
cat["X48"]["evidence"] = cat["X48"]["evidence"] + " | Iteration 8 (X105): the wallet's limit shares no value with P4e's at the cent level (premium corr 0.21, limit diff SD 3.3c): the shared-odds-feed reading of (a) is closed; (b) the probes of odds sources remain untested (terms)."
cat["X98"]["evidence"] = cat["X98"]["evidence"] + " | Iteration 8: v4 (v3 + Dota table) on the 10-31 12-18 block: pooled AUC 0.851 vs 0.640, recall 0.5, lift 3.13 (Dota 2 of 2 traded selected); variants activity + GRID + p4e24 and + cov24 + all24 added to the forward pool (scored without refit)."
cat["C1"]["evidence"] = cat["C1"].get("evidence", "") + " | Iteration 8 (X110): ERC-7739 signer recovery: every sampled wallet order (both legs, both regimes) signed by owner() 0x8af810f0; no key shared with any of 316 makers sampled."

comp = s["components"]
comp["selection"] = {"confidence": 0.72, "tag": "VALIDATE-only",
    "description": ("Whole events of non-GRID CS2 and Dota 2 leagues (never a GRID event: CS2 0/122, Dota EPL Masters 0/33); event logistic (league rate with GRID zeroing + pre-game popularity; v4 adds the Dota 2 league table) VALIDATE pooled AUC 0.953 vs activity 0.886 (gain +0.067 [0.022, 0.118]), recall 0.744 at lift 3.25; coverage of fills / abs PnL 1.0 / 1.0 (CS2-only 0.927; 0.43-0.46 on the 10-31 block). "
                    "The boundary is the feed's coverage: P4e's in-event presence is GRID 0%, non-GRID tier 3 100%, tier 4 38%, tier 5 0%, and the wallet trades 88% of P4e's events vs 8% of the others. Forward 10-31 12-18: AUC 0.851, recall 0.5 (CS2 1 of 4 in an unseen league, Dota 2 of 2).")}
comp["timing"] = {"confidence": 0.6, "tag": "hypothesis",
    "description": ("Taker: messages of a shared esports push feed (>= 6 subscribers at fixed lags; P4e 0, 0x2005d16a +25, the wallet +50, three at ~+200, P93 ~+400 ms; lag invariant across event classes within ~10 ms; not shared in football / NBA / tennis), of the plant / turn kind; raw events priced by each subscriber (premium corr with P4e 0.21). Its Dota takes use another input. "
                    "Maker: at its own takes it pulls the complement at +11-19 ms and re-posts after the FAK returns (~1.03 s); between takes it re-prices the ladder without any public trigger (single-order moves in 6 ms, multi-level pulls re-added in ~0.26 s), and these re-pricings precede adverse moves (validated label -0.60c, ground-truth wallet cancels -0.94c in 10 s, other makers' +0.74c); the take hazard rises with them (weak). Not a public execution filter (take vs strip-only AUC 0.52).")}
comp["side"]["description"] = ("Maker: both outcomes in every market, CS2 and Dota (VALIDATE-only). Taker: the team that gained in-round on plant / turn events (first informed move against the previous burst). Side is not scored (two-sided at market level).")
comp["price"] = {"confidence": 0.4, "tag": "VALIDATE-only",
    "description": ("Maker: whole-cent BUY ladders near the touch (adds at touch 28%, +1 14%, -1 10%, down to -5 13%); historical last-print anchor 0.322 (VALIDATE, v4 rule metric). Live (BUILD-live): touch 0.472 per add (first level 0.511), 0.471 on filled orders; own-state machines (refill the vacated slot, own top, extend, hole-filling) 0.09-0.50, oracle union 0.73: the ladder re-anchors on its private value. Taker: limit = stale ask + its own premium (not a shared value).")}
comp["size"] = {"confidence": 0.62, "tag": "VALIDATE-only",
    "description": ("Maker: 100 shares in CS2 (88-92% of orders; event-wide ramps from ~50 in 36% of events), exactly 10 shares in Dota 2 (1,292 of 1,292 orders); size rule accuracy 0.894 (VALIDATE, v4). Taker: odd sizes ~0.3x of the pre-event depth; Dota takes median 100 shares.")}
comp["exit"] = {"confidence": 0.75, "tag": "VALIDATE-only",
    "description": ("Never sells. Pulls the complement at its takes and re-posts ~1.03 s later; re-prices bids away from private adverse events between takes; merges complete pairs in one 300-s loop for CS2 and Dota (300.22 s + 7.28 s per merge; Dota merges within 30 s of a CS2 pass 68-88%) and holds the residual. Pair cost 0.978 (CS2), ~0.98 (Dota).")}

s["hypotheses"] += [
 {"id": "H83", "family": "scope", "description": "Q7: a CS2-only universe misses the Dota 2 module (exam scope item 1).",
  "validate_metrics": {"cs2_only_fills_validate": 0.9273, "cs2_only_fills_10_22": 0.8457, "cs2_only_fills_devblock_10_31": [0.4252, 0.4568], "cs2_dota_coverage": 1.0},
  "verdict": "supported; v4 universe adds Dota 2 and evaluate() reports coverage on the lot"},
 {"id": "H84", "family": "selection", "description": "The GRID boundary holds in Dota 2 too.", "validate_metrics": {"epl_masters_grid_traded": "0 of 33", "pari_universe_traded": "3 of 4 (10-22), 2 of 3 (10-31)"}, "verdict": "supported"},
 {"id": "H85", "family": "selection", "description": "Q6: selection = the feed's coverage; P4e's presence follows the same tier x GRID boundary.",
  "validate_metrics": {"p4e_presence": {"GRID": "0/122", "N3": "22/22", "N4": "36/96", "N5": "0/144"}, "wallet_traded_given_p4e": 0.879, "given_no_p4e": 0.08, "cov24_validate_auc": 0.8502, "all24_control": 0.7976, "act_grid_p4e24_validate": 0.9444, "v3_validate": 0.9574},
  "verdict": "supported as a mechanism; the point-in-time coverage features do not beat the league table on VALIDATE (kept as forward variants)"},
 {"id": "H86", "family": "label validity", "description": "X107: the pull label holds on ground-truth cancels; Z4 holds on the wallet's GT cancels.",
  "validate_metrics": {"cocancel_precision": 0.955, "gt_wallet_untrig_mk10_c": -0.941, "p": 0.034, "gt_other_untrig_mk10_c": 0.735},
  "verdict": "supported (small n, descriptive)"},
 {"id": "H87", "family": "maker information", "description": "X109: untriggered pulls are take-handler receipts without a FAK.",
  "validate_metrics": {"take_time_repost_median_ms": 1033, "untrig_multi_next_add_median_ms": 261, "untrig_single_next_add_median_ms": 6, "take_vs_strip_cv_auc": 0.5152},
  "verdict": "rejected: they are ladder re-pricing; the take is not a public execution filter"},
 {"id": "H88", "family": "information source structure", "description": "Q3: one operator behind several wallets of the fan-out (shared signing key).",
  "validate_metrics": {"wallet_orders": 273, "wallet_keys": 1, "owner_match": True, "shared_keys": 0, "makers_sampled": 316},
  "verdict": "rejected at the key level"},
 {"id": "H89", "family": "information source structure", "description": "Q2: two detectors (class-dependent lag to P4e).",
  "validate_metrics": {"follow_on_ms": -10.9, "reversal_ms": -0.9, "reversal_minus_follow_on_ci95": [-4.0, 10.0, 22.0]},
  "verdict": "not supported on the co-signed quarter (one fan-out)"},
 {"id": "H90", "family": "information source structure", "description": "The shared feed is a multi-sport B2B product.",
  "validate_metrics": {"r2_takes": 1064, "pair_cosigns": 13, "null": 4.25, "iqr_ms": 122.0},
  "verdict": "rejected (esports only)"},
 {"id": "H91", "family": "information source structure", "description": "The feed carries a value (odds), not raw events.",
  "validate_metrics": {"wallet_p4e_premium_corr": 0.21, "limit_diff_sd_c": 3.3, "p93_p4e_premium_corr": 0.607},
  "verdict": "rejected for the wallet (raw events)"},
 {"id": "H92", "family": "information source", "description": "Polymarket's own score provider is server-fast for non-GRID events.",
  "validate_metrics": {"non_grid_p10_s": 25.8, "grid_p10_s": 46.8, "non_grid_median_s": 168.7},
  "verdict": "rejected (tens of seconds to minutes behind the market for both classes)"},
 {"id": "H93", "family": "price", "description": "X108: an own-state ladder machine (refill vacated slots) predicts each add within one tick.",
  "validate_metrics": {"touch": 0.472, "machine": 0.291, "oracle_union": 0.726},
  "verdict": "rejected"},
 {"id": "H94", "family": "timing", "description": "Q4: the take hazard rises with accumulated untriggered re-pricings (continuous private value).",
  "validate_metrics": {"hazard_by_n10": [0.0083, 0.0105, 0.0202, 0.0353], "logit_coef_n10": [0.476, 0.051]},
  "verdict": "weakly supported (BUILD-live, n 56 takes)"},
 {"id": "H95", "family": "outcome", "description": "A balanced pair-ladder replay (short side, pair cap 0.98) tracks the wallet's per-market PnL.",
  "validate_metrics": {"pnl_corr_pearson": 0.034, "pnl_corr_spearman": -0.085},
  "verdict": "rejected"},
]

s["target_metrics"] = {"presence_auc": 0.8739, "selection_auc": 0.9528, "selection_recall": 0.744, "selection_lift": 3.253,
                       "presence_baseline": 0.8907, "selection_baseline": 0.8863, "side_accuracy": None, "side_baseline": None,
                       "price_within_tick": 0.322, "pnl_corr_pearson": -0.126, "pnl_corr_spearman": -0.065,
                       "coverage_fills": 1.0, "coverage_abs_pnl": 1.0}
s["best"] = {"rule_id": "tommy-v4-grid-league-dota", "validate_metrics": {
    "events": 140, "events_traded": 39, "selection_auc": 0.9528, "selection_baseline": 0.8863, "selection_gain": 0.0665,
    "selection_gain_ci95": [0.0219, 0.1177], "selection_gain_p_le0": 0.0, "selection_recall": 0.744, "selection_lift": 3.253,
    "selection_cs2": {"events": 128, "traded": 36, "auc": 0.9538, "baseline": 0.8916, "recall": 0.722, "lift": 3.302},
    "selection_dota2": {"events": 12, "traded": 3, "auc": 0.963, "baseline": 0.963, "recall": 1.0, "lift": 3.0},
    "presence_auc": 0.8739, "presence_baseline": 0.8907, "price_within_tick": 0.322, "price_exact_last_print": 0.123,
    "size_rule_accuracy": 0.894, "pnl_corr_pearson": -0.126, "pnl_corr_spearman": -0.065,
    "pnl_baseline_prints_pearson": 0.325, "pnl_baseline_prints_spearman": 0.283, "coverage_fills": 1.0, "coverage_abs_pnl": 1.0,
    "coverage_fills_cs2_only": 0.9273}}
tmn = s.get("target_metrics_notes", {})
tmn["scope"] = "Iteration 8: v4 universe (CS2 + Dota 2 match / map winners) covers 1.0 of fills and abs PnL on VALIDATE and on the 10-31 12-18 block; CS2-only would cover 0.927 (VALIDATE) and 0.43-0.46 of fills (10-31 block). evaluate() now computes coverage on the lot."
tmn["selection_forward"] = tmn.get("selection_forward", "") + " | Iteration 8: v4 on the same block (25 events incl. 5 Dota): AUC 0.851 vs 0.640, recall 0.5, lift 3.13."
tmn["primary_metric_change"] = "Iteration 8: presence_auc moves 0.8721 -> 0.8739 only because the universe now includes Dota 2 (same CS2 rule)."
s["target_metrics_notes"] = tmn
s["iterations"].append({"n": 8, "minutes": 95, "best_validate_score": 0.8739,
    "paradigm": "exam scope made explicit (Dota 2 universe, coverage on the lot) plus new decisive data fields: ERC-7739 signing keys, ground-truth cancels of partially filled orders, the feed's coverage read from P4e's presence, a provider latency yardstick, and a cross-sport fan-out test",
    "families": ["coverage by day / block and the Dota universe (X112)", "Dota module components (size, merges, takes)", "ground-truth remainder cancels and co-burst label attribution (X107)", "GT-cancel markouts with placebo (Z4 on ground truth)", "print-based markout (X104)", "handler identity and take-vs-strip filter (X109)", "accumulation dose-response (X116)", "ERC-7739 signer recovery with pure-Python keccak / secp256k1 (X110)", "lag by event class MixedLM (X111)", "feed-coverage selection features (X113, pre-registered)", "vendor boundary from P4e presence (X102)", "provider latency yardstick (X103)", "multi-sport fan-out (X114)", "co-signer premiums vs stale ask (X105)", "idle-gap outages (X106 step 1)", "own-state ladder machine (X108)", "balanced pair-ladder replay (outcome)"]})
s["status"] = "continue"
s["wall_reason"] = None
s["strategy_statement"] = (
    "CS2 and Dota 2 in-play bot; from 10-16 a buy-only two-sided maker plus an informed taker (one signing key, owner 0x8af810f0, for both legs and both regimes), before that a round-trip taker in GRID tier-1/2 events. "
    "[VALIDATE-only] Selection: whole events (match + all maps) of non-GRID leagues, tier 3 all, tier 4 by league, tier 5 rarely, never a GRID event (CS2 0/122, Dota 0/33); from 10-22 also PARI Universe Dota 2 events; this is the coverage of the push feed (P4e's presence has the same boundary); v4 event rule pooled AUC 0.953 vs activity 0.886, recall 0.74 at lift 3.25, coverage 1.0. "
    "[VALIDATE-only] Maker: whole-cent BUY ladders near the touch on both outcome tokens (100 shares in CS2, 10 in Dota 2), never sells, merges pairs in one 300-s loop (97% paired, pair cost 0.978). "
    "[hypothesis, BUILD-live] Protection: at its own takes it pulls the complement at +11-19 ms and re-posts after the FAK returns (~1.03 s); between takes it re-prices its ladder on the private input without any public trigger, and those re-pricings precede adverse moves (ground-truth wallet cancels -0.94c in 10 s). "
    "[hypothesis] Taker: FAK BUYs on raw in-round messages of a shared esports push feed (>= 6 subscribers at fixed lags, P4e 50 ms earlier, lag invariant across event classes, not shared outside esports) of the plant / turn kind, at the stale ask plus its own premium; ~16-20% of the informed bursts; its Dota takes use another input. "
    "[VALIDATE-only] Economics: per-market PnL is the locked margin of pairs formed across the two legs; public maker replays (generic or balanced) do not track it (-0.13 / 0.03), so the outcome item needs the private taker leg.")
s["next_steps"] = [
    "11-01 06-12 (VALIDATE-live): score every pre-registered live test unchanged (touch price, H69 odd sizes, X94 (c) plus (c') GT-cancel markout and (c'') co-burst precision, own-take pull, X116 dose-response), X87 chat clock, X91 / X101 live pages (browser, dev units only), X97 step 2 / X115 if P4e trades on a recorded book; the schedule test (first MERGE pass).",
    "X98 forward selection pooled over the development blocks from 11-01 06:00: v4, v3-tier, the tier rule, activity + GRID + p4e24, activity + GRID + cov24 + all24 (no refit; switching rule unchanged).",
    "X106 steps 2-3 (feed-wide outages with the socket's live fields; common-mode lag shocks across titles), X111 step 3 (geography), X96 (salt PRNG, z3 in a separate folder) if the user consents.",
    "Ask the user: live HLS playlist / chat route (X53), demos (X37), PandaScore token (X55, also X102 step 4), HLTV page checks (X64), odds probes (X48 b), Kick VOD segments (X4 / X22)."]
s.setdefault("data_sources", [])
s["data_sources"] += [
    "Gamma series 10309 (Dota 2) listing projection 10-01..now, resolution for development units only (.cache/re/tommy-cs2-maker/universe_dota.parquet); CS2 + Dota units from T0 (universe_t0.parquet)",
    "ERC-7739 nested signatures of 1,617 orders in 333 transactions (signers only: sig_signers.parquet); eip712Domain() of DepositWallet accounts via eth_call (publicnode)",
    "Public activity of 0x2005d16a, 0x8a80528d, 0xddb6e624, 0xf1ee4842 (16-22 Oct) and the calldata of their 30,113 non-esports transactions (.cache/re/tommy-cs2-maker/multisport/, decoded fields only)"]
s.setdefault("tool_bugs", [])
s["tool_bugs"].append("tools/live.py iter_live('sports', ...) also raises zlib.error on the 10-31 12:00 hour file (the clob hour-12 bug extends to the sports feed); read hour by hour with try/except")
P.write_text(json.dumps(s, indent=1), encoding="utf-8")
op = [k for k, v in s["catalog"].items() if v.get("status") == "open"]
print("open", len(op), op)
