"""Iteration 6: bring state.json up to date (catalog X26-X42, components, statement, live lab, iteration entry)."""
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "state.json"
s = json.loads(P.read_text(encoding="utf-8"))
cat = s["catalog"]


def put(k, status, ev):
    cat[k] = {"status": status, "evidence": ev}


put("X26", "tried", "source: panel iter5 information I1 (price and R3 features on the match clock from the shared recorder). Shared "
    "clob_crypto trade stream, 1,519 cluster BTC 5m maker fills 10-31 12:18-16:13 UTC (98.3% found by tx hash): last clean print "
    "before the match - 0.01 within a tick 0.795 (live BUILD 12-15 UTC, n 550) and 0.858 (live VALIDATE 15:00-16:13, n 969; "
    "bosona 0.870, almach 0.854, mo-money 0.852); trivial anchors on the same fills: last print 0.847, touch 200 ms before 0.863, "
    "touch - 0.01 0.864; anchor >= 2 s old 0.59 (block clock). Frozen as R4 price (final_rule.price_match_clock). Presence on the "
    "match clock: see X31 (results/iter6_i1_price_1793448000_1793463203.json, iter6_r4_price_*.json).")
put("X27", "tried", "source: panel iter5 information I2 (the ladder center F* and a race of inputs on it). 3,045 s of 24 live BTC 5m "
    "windows: skew F* - mid regressed on fair_X - mid, fit < 15:00 UTC, held out after (1,861 s): Chainlink (RTDS, value stamp, "
    "true strike) at 2 s lag held-out R^2 0.206 (in-sample 0.198), 3 s 0.128, 0-1 s <= 0.00; Binance futures, spot, Coinbase, OKX, "
    "Bybit at 0-4 s <= -0.01. The peak equals the measured Chainlink publication delay (newest RTDS value stamped 1.2-1.8 s before "
    "arrival). Deribit, Bitstamp (recorded from 15:57 UTC in dx_drb / dx_bst), composite and Kalshi not raced yet: X41 "
    "(results/iter6_m1_center_*.json, iter6_m1_race_*.json).")
put("X28", "open", "source: panel iter5 information I3 (counterparties' signing lag vs RTDS, PM jumps, futures). Not done; partly "
    "addressed by X38 (non-HFT first prints carry the profit, HFT ~0).")
put("X29", "tried", "source: panel iter5 information I4 (slim exam recorder through the sealed blocks). code6/examrec.py started "
    "2026-10-31 15:57 UTC (pid 20820), hard stop 2026-11-02 00:00 UTC, dx_* feeds (trades with tx hash and server ms, touch, touch "
    "queue every 200 ms, schedule-size deltas within 3 ticks, books within 3 ticks every 5 s; futures bookTicker + aggTrade; RTDS "
    "Chainlink + TWAP staggered; Deribit; Bitstamp); measured ~7.5 MB/h, cap 280 MB. Completeness vs the cluster's calldata to be "
    "checked in the next development block.")
put("X30", "tried", "source: panel iter5 mechanics M1 (complement-pair decomposition). Top 500-rung pair sum median 0.88, h* 0.06 "
    "(p10-p90 0.025-0.105; 0.083 in the last minute), skew median -0.005 (IQR -0.03..+0.03), autocorr 0.44 at 1 s; the skew is "
    "explained by Chainlink at its publication delay (held-out R^2 0.21), not by futures (<= 0.0) (see X27).")
put("X31", "tried", "source: panel iter5 mechanics M2 (selection branch; presence ceiling). Live print level (34,109 BTC 5m prints, "
    "1,188 cluster; test 15:00-16:13): activity 0.636, + futures 0.632, + Chainlink fair (stamp <= t-2 s) 0.703, + both 0.747 "
    "(recall 39% at lift 2.8); 10-s bins (840 test bins): activity 0.604, + Chainlink 0.638, all 0.641; side in one-sided bins "
    "(n 127) Chainlink edge 0.63, activity 0.55, always-Up 0.60. Historical (examinable on the lot) version impossible without a "
    "historical Chainlink 1-s series (X42). results/iter6_sel_live_*.json, iter6_pres_live_*.json.")
put("X32", "tried", "source: panel iter5 mechanics M3 (not quoting vs quoted but unfilled). Live: 24/24 BTC 5m windows quoted (median "
    "437 near-touch 500/100 adds), one zero-fill window: P(0 | quoted) 0.04. VALIDATE: 94.5% of windows active, R3 0.708 inside "
    "them vs 0.716 overall, so the on/off is not the presence gap on VALIDATE; the 0.862 oracle used the label.")
put("X33", "tried", "source: panel iter5 mechanics M4 (improve or join; age null). 1,316 confirmed orders: 78% at the touch, 9.5% "
    "improved it, 68% joined (median 500 ahead), 67% fresh; age at match median 0.68 s vs 11.2 s for at-touch 500/100 orders alive "
    "at random moments (length-biased null): fills come from recent posts.")
put("X34", "open", "source: panel iter5 mechanics M5 (size controller hazard on futures vol). Not done this iteration.")
put("X35", "tried", "source: panel iter5 assumptions Q1 (fresh post at the touch after a print). Confirmed posts follow a trade by a "
    "median 95 ms (P<=150 ms 0.59 vs 0.41-0.46 other at-touch adds, 0.18 random); the trade sold the post's token in 61% (others "
    "42-44%); post price = that trade's price 37% (others 46-47%); futures moved toward the token before 23% of posts (others 82%). "
    "Partly supported: fresh joins after the token is sold; side 61% and price 37% far from the 80% signatures.")
put("X36", "tried", "source: panel iter5 assumptions Q2 (whose 500/100 stream). Signatures 41.6/s (3 wallets); exact 500/100 adds in "
    "the recorded BTC books 21.2/s; adds > signatures in 0/124 60-s bins; OLS slope 0.39, intercept 4.8/s, R^2 0.53: mostly the "
    "cluster's, not proven (all-match calldata identity check not done).")
put("X37", "tried", "source: panel iter5 assumptions Q3 (queue-ahead fill law). At-touch confirmed joins: median 500 ahead; prints at "
    "the level between post and match (excluding the fill tx) cover it in 19%: the fill's own match sweeps the queue ahead (or "
    "orders ahead cancel). Strict back-of-queue needs each match's maker list (calldata); partial.")
put("X38", "tried", "source: panel iter5 assumptions Q4 (PnL from continuing taker sequences). Rejected: cluster fills are first "
    "prints of the taker's sequence in 67% (STUDY) / 73% (VALIDATE agg.) vs 64% base; non-HFT first prints carry the profit (STUDY "
    "+3.7%, VALIDATE +5.7% = +$19.4k), HFT ~0, positions 3-5 lose in both halves (results/iter6_q4_sequences.json).")
put("X39", "open", "source: panel iter5 assumptions Q5 (on/off as competitor avoidance). Not done; on VALIDATE only 5.5% of windows "
    "are inactive (X32), so its weight in the metrics is small.")
put("X40", "open", "source: panel iter5 assumptions Q6 (BTC 15m late window priced off the 5m book). Not done.")
put("X41", "open", "source: iteration 6 (own). Replicate the Chainlink-center and print-selection result on the 11-01 06-12 "
    "development block (dx_rtds) and race Deribit (dx_drb) and Bitstamp (dx_bst) on F*.")
put("X42", "infeasible", "source: iteration 6 (own): a historical Chainlink BTC/USD 1-s series for the released lot, to test the "
    "Chainlink input on VALIDATE. data.chain.link/streams/btc-usd-cexprice-streams and /api/live-data-engine-streams-data?feedId=... "
    "answered HTTP 429 (text/html, 36,991 bytes) on 2026-10-31 16:20 UTC. Used instead: the live RTDS recordings (dm_rtds, dx_rtds). "
    "Retry another day or find another archive.")
cat["X11"] = {"status": "tried", "evidence": "source: panel iter4 information I2 (match clock). Done in iteration 6 on the live block "
              "(X26: price within a tick 0.858 on the match clock vs 0.59 with a 2-s-old anchor; X31: presence and selection on server "
              "ms). Historical all-match calldata clock not built (not needed for the exam route through the shared recorder)."}

s["status"] = "continue"
s["live_lab"] = [
    {"what": "code5/rawrec.py: dm_clob_raw (unaggregated CLOB events, BTC 5m current+next, 15m current), dm_bnf/dm_bnfa, dm_bns, dm_cb, "
             "dm_okx, dm_byb, dm_hl, dm_rtds; hard stop 18:00 UTC; disk cap 280 MB", "start": 1793455457, "end": 1793469600},
    {"what": "code6/examrec.py (slim exam recorder): dx_clob (trades with tx hash and server ms, touch, touch queue every 200 ms, "
             "schedule-size deltas within 3 ticks, books within 3 ticks every 5 s; BTC 5m current+next, 15m current), dx_bnf/dx_bnfa "
             "(Binance futures bookTicker on best-price change, aggTrade), dx_rtds (Chainlink + TWAP-60, staggered), dx_drb (Deribit index "
             "+ perp ticker 100 ms), dx_bst (Bitstamp trades); ~7.5 MB/h, cap 280 MB, < 100 MB memory", "start": 1793461050, "end": 1793577600},
]
s["live_lab_note"] = ("Shared recorder (pid 27184) running. Own rawrec (pid 14360) to 18:00 UTC; slim exam recorder examrec (pid 20820, "
                      "launcher 9952) to 2026-11-02 00:00 UTC, status .cache/re/directional-maker/examrec_status.json. Read dm_/dx_ feeds with "
                      "code5/rawread.iter_dm (gzip members one by one; development blocks only).")
s["live_split"] = {"live_BUILD": [1793448000, 1793458800], "live_VALIDATE": [1793458800, 1793469600],
                   "note": "pre-registered in iteration 6 before any look: live-input rules fit on 10-31 12:00-15:00 UTC and are chosen on "
                           "15:00-18:00 UTC (aggregate); later development blocks extend live VALIDATE."}
s["target_metrics_live"] = {
    "period": "live VALIDATE 2026-10-31 15:00-16:13 UTC (development block)",
    "price_within_tick": 0.858, "price_within_tick_per_wallet": {"bosona": 0.870, "almach": 0.854, "momoney": 0.852},
    "price_trivial_anchors": {"last_print": 0.847, "touch_200ms": 0.863, "touch_minus_tick": 0.864},
    "selection_auc_print_level": 0.747, "selection_recall": 0.393, "selection_lift": 2.76, "selection_baseline_activity": 0.636,
    "presence_auc_10s_bins": 0.641, "presence_baseline_activity": 0.604, "side_accuracy": 0.63, "side_baseline_always_up": 0.598,
    "note": "R4 price is examinable now (shared recorder); the Chainlink selection/presence models are exploratory (fitted on 600 bins / "
            "12.6k prints of one Saturday afternoon) and not frozen."}
s["strategy_statement"] = (
    "One engine signs every order of three wallets (per-wallet sequential salt, timestamp 0; ~13.5 orders/s per wallet) "
    "[VALIDATE-only]. It keeps 500/100-share BUY quotes (other days 62/12 or 250/50, set for all wallets at once) on both outcomes "
    "of BTC 5m/15m (and other crypto) windows, re-posted about once a second; the top rungs of the two outcomes sum to 0.88 "
    "(half-spread ~6 c, wider in the last minute) around a center whose skew follows the Chainlink BTC/USD stream (the settlement "
    "source) at its ~2-s publication delay, not Binance [hypothesis, live block: held-out R^2 0.21 vs <= 0 for every exchange]. "
    "The orders that fill are fresh joins at the touch posted ~0.1 s after a trade sold that token (61%) and matched ~0.7 s later "
    "[hypothesis, live]. Its fill price is the last clean print minus a tick on the match clock (0.858 within a tick live; 0.709 on "
    "the block clock VALIDATE, 0.688 exam) [exam-verified on the block clock; VALIDATE-only (live) on the match clock]. Which windows "
    "it trades: nearly all on VALIDATE (94.5%) and live (24/24 quoted); BTC 5m on/off runs are rare operator switches [hypothesis]. "
    "Side: filled where its quote reaches the touch: 0.663 VALIDATE (exam 0.655) [exam-verified, partial]. It holds to resolution, "
    "with a small complement flatten and merge [VALIDATE-only]. Profit comes from first prints of non-HFT takers (+5.7% VALIDATE), "
    "about zero against high-frequency takers [VALIDATE-only].")
comp = s["components"]
comp["selection"] = {"confidence": 0.35, "tag": "hypothesis", "description": "one engine over crypto Up/Down; BTC 5m 78% of VALIDATE "
                     "fills / 69% of abs PnL (BTC 5m+15m 87% / 89%); nearly every window quoted (VALIDATE 94.5% active; live 24/24 quoted, "
                     "P(0 fills | quoted) 0.04); rare operator off-runs with no public correlate yet."}
comp["timing"] = {"confidence": 0.7, "tag": "VALIDATE-only", "description": "continuous re-signing (~13.5 orders/s per wallet); the "
                  "orders that fill are fresh joins at the touch posted a median 95 ms after a trade (P<=150 ms 0.59 vs 0.41-0.46 for other "
                  "makers) that sold that token (61%), matched a median 0.68 s later (vs 11 s age of resting at-touch orders) [live block: "
                  "hypothesis]; exposure to moves of the last ~0.25-1.5 s (STUDY ms clocks); stops ~30 s before the end."}
comp["side"] = {"confidence": 0.5, "tag": "exam-verified", "description": "Up and Down quoted together around one center; filled on "
                "the side whose quote reaches the touch: R3 0.663 VALIDATE (exam 0.655) vs 0.613 activity; live: the Chainlink edge picks the "
                "side in 0.63 of one-sided bins (n 127, hypothesis)."}
comp["price"] = {"confidence": 0.65, "tag": "exam-verified", "description": "fill price = last clean print - 0.01: block clock 0.709 "
                 "VALIDATE (exam 0.688); match clock (R4, shared recorder) 0.858 live VALIDATE, each wallet 0.85-0.87 [VALIDATE-only, live]; "
                 "it is the trivial anchor on a fresh clock. Ladder: pair sum 0.88, center skew tracks Chainlink at its publication delay "
                 "[hypothesis]."}
comp["size"] = {"confidence": 0.6, "tag": "VALIDATE-only", "description": "runtime size class 500 x 2^k with a one-fifth level "
                "(500/100 on 10-31; 62/12 or 250/50 on other days), switched for all wallets in the same second; partially filled orders "
                "re-posted with the remainder; size does not depend on the edge."}
comp["exit"] = {"confidence": 0.55, "tag": "VALIDATE-only", "description": "holds to resolution; taker-buys the under-held complement "
                "(72-83% of its taker buys) then merges in 17-51% of those windows; 2-4% of PnL; maker-maker pairs ~90% of paired shares."}
s["best"]["note_iter6"] = ("R4 = R3 + match-clock price (final_rule.price_match_clock); historical VALIDATE metrics unchanged (R4 = R3 there); "
                           "live VALIDATE price 0.858.")
s["best"]["rule_id"] = "R4-R3-presence+match-clock-price"
s.setdefault("hypotheses", []).extend([
    {"id": "H6-1", "family": "J1 reactive touch-poster (Q1)", "description": "fills come from fresh joins at the touch after a trade sold the token",
     "validate_metrics": {"confirmed": 1316, "at_touch": 0.78, "lag_le_150ms": 0.59, "null": "0.41-0.46", "token_just_sold": 0.61},
     "verdict": "partly supported"},
    {"id": "H6-2", "family": "J4 center skew input race (M1/I2)", "description": "ladder center skew follows Chainlink at its publication delay",
     "validate_metrics": {"heldout_r2_chainlink_2s": 0.206, "heldout_r2_best_exchange": -0.01}, "verdict": "supported (live, one block)"},
    {"id": "H6-3", "family": "Chainlink fair in selection/presence (M2)", "description": "print-level selection and 10-s presence with the Chainlink fair",
     "validate_metrics": {"print_auc": 0.747, "print_activity": 0.636, "bin_auc": 0.641, "bin_activity": 0.604}, "verdict": "promising (live, not frozen)"},
    {"id": "H6-4", "family": "J7 match-clock price (I1)", "description": "last clean print - 0.01 on the server match clock",
     "validate_metrics": {"within_tick_live_validate": 0.858, "block_clock_analog": 0.592}, "verdict": "supported; frozen as R4 price"},
    {"id": "H6-5", "family": "J5 taker sequences (Q4)", "description": "PnL from continuing taker sequences",
     "validate_metrics": {"first_print_share": 0.73, "base": 0.64, "nonHFT_first_ret": 0.057}, "verdict": "rejected"},
])
s.setdefault("data_sources", []).extend([
    "iteration 6: live activity + calldata of the cluster's live txs 10-31 12:00-16:13 UTC; own raw recording 14:06-16:13 UTC compacted to .cache/re/directional-maker/it6/",
    "iteration 6: shared recorder clob_crypto trade stream (x) 10-31 12:18-16:13 UTC for the match clock",
    "iteration 6: RTDS Chainlink 1-s + TWAP-60 (own dm_rtds, staggered) as an information input; publication delay measured 1.2-1.8 s",
    "iteration 6: slim exam recorder dx_* (code6/examrec.py) from 15:57 UTC to 2026-11-02 00:00 UTC",
    "iteration 6: data.chain.link history -> HTTP 429 (infeasible, X42)",
])
s["iterations"].append({"n": 6, "minutes": 92, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half); live VALIDATE 10-31 15:00-16:13 UTC for live-input rules",
                        "paradigm": "confirmed orders and an information race on the ladder center (live, match clock)",
                        "families": ["X26 match-clock price", "X27/X30 center race (Chainlink vs exchanges)", "X29 slim exam recorder",
                                     "X31 print-level selection and bin presence with Chainlink", "X32 quoted vs unfilled", "X33 age null / improve-join",
                                     "X35 reactive post hazard", "X36 salt counter vs adds", "X37 queue", "X38 taker sequences PnL", "side with Chainlink (live)"]})
P.write_text(json.dumps(s, indent=1), encoding="utf-8")
from collections import Counter
print(Counter(v["status"] for v in cat.values()))
print(sorted(k for k, v in cat.items() if v["status"] == "open"))
