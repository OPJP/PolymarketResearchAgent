"""Examiner r1: write results/exam_r1.json (verdict + metrics bundle) and copy to results/exam.json."""
import json, shutil, time
R = "research/reverse_engineering/btc5m-bot/results"
B = json.load(open(f"{R}/exam_r1_metrics_bundle.json"))
M = B["metrics"]
V = {
    "strategy": "btc5m-bot", "exam_round": 1, "lot": "h1", "now_ts": int(time.time()),
    "fresh_data_sufficient": True,
    "holdout_sample": ("h1 = BTC 5m Up/Down windows starting 2026-10-23, 10-25, 10-27, 10-29 UTC (1,152 windows listed, 1,131 traded by the "
                       "cluster; 160,664 cluster BUY fills; 92,963 unique cluster taker orders, 88,978 matched to the public capture). Halves by "
                       "listing start: earlier = 10-23 + 10-25 (576 windows), later = 10-27 + 10-29 (576). Left out: nothing in the rule's "
                       "universe; the public HF capture has no rows for 23:00-24:00 UTC of any day, so the decision-clock side / hazard routes "
                       "miss 4.3% of taker orders; no live recordings exist for h1 (live components return None)."),
    "target_met": False,
    "target_conditions": {
        "scope": "met: the rule's universe (every BTC 5m window) holds 100% of the wallets' lot fills (160,664 on chain, all on lot windows) and 100% of |PnL|",
        "presence_or_selection": ("NOT met: block-second presence AUC 0.8673 (>= 0.85) but the gain over the stronger market baseline (the RE's capture-aware MSB, "
                                  "refit as in pres14: 0.8564) is +0.0109 [0.0072, 0.0145] < 0.05; vs the RE's pure baseline +0.0483 [0.0450, 0.0515], vs the "
                                  "examiner's BUILD-fitted MKTX +0.0459 [0.0412, 0.0497] -- below 0.05 against every baseline. Selection AUC 0.8939, recall "
                                  "73.5% at lift 5.34 but gain +0.0177 [0.0151, 0.0204] over its baseline < 0.05. Slack-clean decision-aligned unit 0.9053 vs "
                                  "0.8765 (+0.029)."),
        "side": ("not applicable by the 20% rule (XM one-sided in 19.9% of its windows, order-count null 18.3%; GF 3.2%, DS 0.4%); reported: 0.8193 "
                 "per taker order (halves 0.821 / 0.818; DS 0.820, GF 0.826, XM 0.779) vs best market-only (underdog) 0.538 and own-inventory 0.506 -- "
                 "would be met within the 3-point tolerance"),
        "price": ("met under the proviso: limit within one tick of the touch of the same match for 95.3% of 14,130 sampled taker orders (halves 95.4 / 95.3; "
                  "DS 97.1, GF 94.2, XM 81.8). The rule IS the trivial touch anchor measured on the match (not a PIT forecast) and the touch+1-tick anchor "
                  "is better (97.5%); maker fills (26% of USDC) are not covered"),
        "outcome": ("NOT met: per-window PnL correlation of the executable tracker with the wallets 0.4245 / 0.4114 (Pearson / Spearman; 2-h block CI "
                    "[0.371, 0.478] / [0.357, 0.463]); slack-2 fills 0.418 / 0.404"),
        "significance": ("partly met: rotation null p = 0.00025 for the PnL correlation (4,000 draws), window-permutation null p = 0.0005 for presence and "
                         "within-window permutation p = 0.0005 for side (2,000 draws, floor), presence gain > 0 at p < 0.0005; but the pre-registered "
                         "gain >= 0.05 is rejected (bootstrap P(gain <= 0.05) = 1.0)"),
        "replication": ("NOT met: per wallet XM presence 0.841 (second half 0.811 < 0.82) with negative gain vs MSB in both halves; PnL corr per wallet "
                        "GF 0.279 / 0.269, XM 0.141 / 0.167, DS 0.416 / 0.375 (all < 0.47); second-half pooled PnL 0.402 / 0.367; side XM halves "
                        "0.789 / 0.772 (inside the tolerance)")},
    "components": {"selection": "pass", "timing": "partial", "side": "pass", "price": "partial", "size": "partial", "exit": "pass"},
    "criteria": {"match": "partial", "backtest": "fail", "replicable": "fail", "persists": "fail"},
    "criteria_details": {
        "match": ("partial: target_met is false. Strong pieces: side 0.819 per taker order vs 0.538 market-only; presence AUC 0.867 with permutation "
                  "p = 0.0005; PnL rotation p = 0.00025. But the presence / selection gain over a market-activity baseline is +0.011 / +0.018 "
                  "(< 0.05), the PnL correlation is 0.42 / 0.41 (< 0.5) and XM fails replication."),
        "backtest": ("fail: the executable rule (exposure tracker mix14, strict fills against other traders' taker prints, latency >= 2 s after the "
                     "information horizon) returns -0.98% before rebates on $154k bought (block-bootstrap P(return <= 0) = 0.77, 95% CI [-3.6%, +1.7%]); "
                     "with print stamps >= s+3 (block-time slack 2 s) -2.39% (P = 0.945); capture 0.5 -1.1% / -2.5%; the 30-share replica -2.33%. A "
                     "50% fee rebate (not available to a newcomer at the 0% tier) gives +0.56% (P(<= 0) = 0.33), still not significant."),
        "replicable": ("fail: the edge needs a host next to Polymarket's London engine reading Binance spot within ~100 ms, inside a 150-ms taker hold "
                       "(placebo anchors m +-3 s give 50% side accuracy); a normal connection at >= 2 s loses 1-2.4% before rebates; at the observed "
                       "liquidity the rule trades ~$1.2M a month for about -$11k a month, nowhere near $50k/month profit."),
        "persists": ("fail: the deploy-now statement is not supported. The deployable rule loses on the newest lot days (10-27 -3.2%, 10-29 +1.1%, "
                     "neither significant). The wallets themselves still earn (assess_persistence as of 11-01: GF and DS recent 30 days p < 1e-4, no "
                     "decline; XM late-15-day decline p = 0.0018), and the conditions they need (150-ms taker delay, 50% taker rebate paid daily, "
                     "BTC 5m listings) held on the lot, but that is the operator's colocated, rebate-tier edge, not a normal user's.")},
    "rule_summary": ("Frozen iteration-14 rule (code/final_rule.py sha256 0523a66c...): presence on Polygon block seconds = LightGBM model_it5_blk_full "
                     "(spot 1-s closes <= s-2, venue trades < s-1, others' prints <= s-1); side = dc_exam14 (Binance spot microprice / trade returns "
                     "over 100-2000 ms ending 260 ms before the capture match ms, model_it14_dcside_spot); price = the touch of the same match; PnL rule "
                     "= exposure tracker buying the deficit to a predicted cluster net-flow target (0.5 x (it4b + nf12b)/2 + 0.5 x 5.935 x hazard "
                     "imbalance) at last implied ask + 2 c, strict fills against other traders' taker BUY prints stamped [s+1, s+3]."),
    "leakage_check": {"passed": False, "details": (
        "No sealed access by development code: guards in every archive / capture loader (end_ts <= H, d0 + 86400 > H refused unless "
        "allow_sealed), a scan of .cache/re/btc5m-bot found no file with data in [H, T0) (79 files past H, all in the development blocks "
        "10-31 00-06 / 12-18), no reads of .cache/live/sealed/, http.sqlite or other workspaces, Gamma kept only for development windows "
        "(outcome column named SETTLEMENT_ONLY). Every rule parameter is a module constant; models are frozen files dated before the exam. "
        "Truncation / corruption tests at the code's stated horizons: 960 / 960 identical (blk_full, blk_pure, dp_full, netflow; 12 seeded "
        "windows x 20 decision seconds), side route 300 / 300 and hazard 200 / 200 identical. FAILED item: the pre-registered block-second "
        "presence unit uses data inside the 2-s block-time slack (prints stamped s-1, venue trades in [s-2, s-1) for a fill stamped s that "
        "matched up to 2 s earlier): corrupting that slice changes 480 / 480 sampled predictions (mean |dp| 0.178). The slack-clean "
        "decision-aligned unit is reported (0.905 vs 0.877). Also: W4 / W5 (the operator's own fan-out wallets) prints count as market "
        "activity in the tape features (8% of block cells, 19.9% of positives; excluding those cells leaves the gain over MSB at +0.012); the "
        "hazard's Polymarket inputs end 55-105 ms after the decision (in both model and baseline); nf12b's prev_up_spot reads the close of "
        "start-1 at rel 0-1 (<= 1 s early). None of these changes the verdict.")},
    "metrics": M,
    "per_wallet": {w: {"presence_auc": M["presence_block_seconds"]["by_wallet"][w], "side_accuracy": M["side_decision_clock"]["by_wallet"][w],
                       "price_within_tick": M["price"]["by_wallet"][w]["all"]["rule_touch_within_1tick"],
                       "pnl_corr": M["pnl_tracker_frozen_conv_a_capture1"]["by_wallet"][w],
                       "pnl_corr_halves": M["pnl_tracker_frozen_conv_a_capture1"]["by_wallet_halves"][w],
                       "own_return_before_rebates": M["wallet_own"]["by_wallet"][w]["before_rebates"]["return"],
                       "own_return_with_50pct_taker_rebate": M["wallet_own"]["by_wallet"][w]["with_50pct_taker_fee_rebate"]["return"],
                       "one_sided_window_share": M["side_decision_clock"]["side_applicability"][w]["share_one_sided"]} for w in ("GF", "XM", "DS")},
    "why_it_works": ("Latency arbitrage of stale Polymarket asks inside the 150-ms taker hold, paid for by slow makers and by the 50% taker-fee rebate. "
                     "The bot reads the Binance spot book ~100 ms after its stamp next to Polymarket's engine and lifts the outcome the spot "
                     "microprice is moving toward (82% of taker orders on the lot vs 54% for any market-only rule). It buys both outcomes of 98% of "
                     "windows: 88.6% of shares end paired at a pair cost of 0.9795, locking $26.5k gross on the lot; after $32.3k of taker fees its "
                     "trading PnL is +$13.1k (+0.92% of $1.42M); the next-day 50% taker rebate (+$16.2k) doubles that (+2.05%). Its taker fills earn "
                     "~0 after fees (+0.03 c / share); its maker fills (26% of USDC, mostly lost races resting at the old ask) earn +1.66 c / share. "
                     "Who loses: makers whose asks still stand when the hold ends (the slowest quote-pullers), and Polymarket's rebate pool."),
    "deploy_now": {"supported": False, "evidence": (
        "The executable rule loses before rebates on the lot (-0.98%, P(<= 0) = 0.77; -2.39% with block-time slack) and on the newest days "
        "(10-27 -3.2%, 10-29 +1.1%); a newcomer has a 0% rebate tier, and even a 50% rebate leaves it insignificant (+0.56%, P = 0.33). The "
        "wallets' own edge persists (GF / DS recent 30 days p < 1e-4; XM recent p = 0.0017 but late-15-day decline p = 0.0018) because of "
        "colocation, queue position and the Obsidian rebate tier, none of which a normal user has.")},
    "diagnosis": "see EXAM_r1.md section 'Diagnosis (first half only)' and diagnosis_first_half",
    "diagnosis_first_half": B["diagnosis_first_half"],
    "mechanical_fixes_made": ("None to code/: no file was copied or patched, so there is no results/exam_r1_patch.diff. The exam driver "
                              "(exam/run_eval.py) sets final_rule.ALLOW_SEALED = True and final_rule.EVAL_DIR = .cache/exam/btc5m-bot/eval at "
                              "runtime (so no sealed archive or tape lands in .cache/re/btc5m-bot), adds read-only wrappers that save intermediate "
                              "arrays, and memoizes public HF capture row groups with the exact rows the consumers use (polymarket rows filtered to "
                              "last_trade_price, the only event type any consumer keeps). Checks: the driver reproduces the RE's dev numbers on "
                              "10-22 22-24 (presence 0.8464 vs 0.7839); the examiner's independent side and tracker code reproduce evaluate() to 4 "
                              "decimals on every chunk. evaluate() was run on 16 six-hour chunks of the lot with intervals = the chunk (memory: "
                              "peak 2.0 GB per chunk; a 4-day call would not fit the laptop)."),
    "truncation": B["truncation"], "evaluate_run": B["evaluate_run"],
}
json.dump(V, open(f"{R}/exam_r1.json", "w"), indent=1, default=str)
shutil.copyfile(f"{R}/exam_r1.json", f"{R}/exam.json")
print("written", len(json.dumps(V, default=str)))
