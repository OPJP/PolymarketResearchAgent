"""Iteration-15 state.json update (catalog X204-X218 and existing items, dimensions, indicators, hypotheses, components,
target metrics, best rule v6, strategy statement, iteration entry). Run once at the end of iteration 15."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SP = ROOT / "research/reverse_engineering/tommy-cs2-maker/state.json"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def main(now_ts: int, minutes: float):
    s = json.load(open(SP, encoding="utf-8"))
    c = s["catalog"]
    P14 = "panel iteration 14 "
    new = {
        "X204": ("tried", P14 + "information P1: GRID-map natural experiment, the operator's quotes against the sports socket's public round-END clock",
                 "code/iter15/grid_socket_data.py, grid_socket_clock.py, grid_socket_clock2.py; results/grid_socket_clock*.json (development units 10-31 12-18, 11-01 06-12). The socket carries round scores for GRID events only (48 / 37 / 22 / 35 round ticks), on a 20.2-s polling grid, the print's winner-direction jump in the 20 s before the tick (L 2 / 10 s). 0xd2bb9459's filled bursts (659 orders): mid-round round-winner AUC 0.703 vs the print's 0.622 (183 rounds, two 10-31 events), map books 0.766 vs 0.736, match books 0.614 vs 0.489 (stale match print); share of its move in the end window 0.38; neither pre-registered R nor K verdict holds. 0xd2bb9459 is not the operator's process (X205 step 5: no cross-market co-signing, different design), so the arm is not the wallet's machine; it shows a GRID maker's value carries no in-round information beyond the liquid map print."),
        "X205": ("tried", P14 + "information P2: label the operator, not the address; routing of events to accounts",
                 "code/iter15/operator_selection.py, sibling_identity.py; results/operator_selection.json, sibling_identity.json. Step 5 first: cross-market 0-5 ms co-signing with the wallet's 25,878 orders (16-22 Oct, 700 sampled txs each): 0xd2bb9459 0 vs 6 pairs at 5-50 ms, 0x10d79cc7 1 vs 6 (1.4x), the known sibling 0x7d67f01d 13 vs 24 (4.4x); designs differ (single 50-600-share orders; 20-share ladders). So 0xd2bb9459 / 0x10d79cc7 are not attributed (X203's 9-12.6x was same-market co-signing, which co-subscribers of one feed produce). Operator relabel with the panel's lists: v5 VALIDATE wallet label 0.973 / recall 0.75 / lift 3.2; six-account label 0.904 / 0.596 / 2.54; non-GRID only 0.961 / 0.737. Routing among non-GRID operator events: 77 of 97 to the wallet, v5 separates wallet vs sibling-only at AUC 0.777 (gp72 0.71, hour 0.61); share 4/10 on 10-16 rising to 36/38 on 10-21/22; 20 sibling-only events, too few for an out-of-fold allocation model. Whether the exam's wallet list should be the operator's attributed accounts is the user's call (asked in the return)."),
        "X206": ("open", P14 + "information P3: name the vendor (PandaScore Low Latency Feed); key-free fingerprints and a user-gated token test",
                 "Not run beyond what the notebook holds: the fixed-lag cross-operator fan-out exists in CS2, LoL and Dota and not in Valorant (subscribers_other_titles.json), which matches the LLF's title list. Iteration-15 support for an in-round event stream (X209: no decided-early drop; K favored) fits the LLF's kill / bomb / alive data points. The decisive test needs a PandaScore token (account creation is the user's), asked in the return; the key-free veto-timing test is not run."),
        "X207": ("ruled_out", P14 + "information P4: LoL as the public-state twin on 0xd2bb9459's LoL trades",
                 "Its premise fails by measurement: 0xd2bb9459 is not the operator's process (X205 step 5: 0 cross-market co-signed pairs at 0-5 ms vs 6 at 5-50 ms with the wallet's orders in 16-22 Oct, 0 within 50 ms on 10-31; single-order design of 50-600 shares), so its LoL quoting is not a twin of the wallet's machine. The operator's attributed accounts' LoL (0x7d67f01d 730 LoL trades in 10-15..22) remains a candidate under X191."),
        "X208": ("open", P14 + "information P5: is the Dota half read from Valve's public spectator state?",
                 "Not run: the development-block Dota units were traded by 0x7d67f01d, which fails the same-process gate on those units (X215: single orders of 50-60 shares, no 1c ladder, no co-signing with the wallet on 10-31); the wallet's own Dota units of the development blocks remain the test units."),
        "X209": ("tried", P14 + "mechanics P1: decided-early rounds, the sign of V's lead over the print separates R from K",
                 "code/iter15/decided_early.py, decided_early_stats.py; results/decided_early_print.json, decided_early_takes.json, decided_early_clock_*.json. Print-anchored clock (412 rounds): share of its value's winner-signed move before the anchor 0.680 in elimination rounds (262) vs 0.682 in decided-early rounds (115; defuse after T wipe, bomb with CTs alive); difference +0.002, map-cluster bootstrap CI [-0.203, +0.176]; print control -0.014 [-0.35, +0.26]. R predicted about -0.28 (excluded); K's no-difference signature holds. Single-take clock (141 rounds): +0.221 [-0.31, +0.73] (no fall). In save rounds its value moves +2.18c mid and +1.57c late vs the print's +1.45 / -0.57c. Hypothesis-level (weak clock, 1.30x placebo)."),
        "X210": ("tried", P14 + "mechanics P2: the operator's GRID ladders on BUILD-live with the socket's round scores as a true clock",
                 "Run with X204 (same data): socket clock characterized (20.2-s polling, GRID only); 0xd2bb9459 fails identity (no cross-market co-signing) and the process signatures (single orders, no five-slot bursts: 649 of 654 bursts single; sizes 60-440 in steps of 20); its mid-round AUC equals the map print's. The other accounts in the four GRID books of 10-31 (0xca0b532d, 0x2b55d2ee, 0xd3bd48ab, 0x68915897, 0x5d40576b) were not decoded; 0x68915897 and 0x5d40576b (both among the 100-share whole-cent BUY makers of those GRID books, iteration 6 timer_owner) show 16x / 8x per-ms 0-5 ms co-signing with the wallet's 10-31 orders inside the wallet's own txs (same_process_gate.json control list, 6 / 1 pairs); that is same-market co-signing; the cross-market test (code/iter15/grid_candidates.py, results/grid_candidates.json; their 10-31 12-18 activity filtered to development-unit events, 729 / 324 orders decoded) finds 0 pairs within 50 ms for both, single-order designs (707 of 718; 324 of 324), so neither is the operator's process: no attributed account quotes GRID events on the development blocks."),
        "X211": ("open", P14 + "mechanics P3: are the dark re-pricings messages? censoring-free and follower-free informativeness, count per round",
                 "Step 3 simplified only (code/iter15/kill_margin.py, results/kill_margin.json): its mid-round winner-signed move rises 0.65c per kill of margin (CI [-0.01, 1.31]) like the print's 0.47c; lead slope 0.21c per kill (CI [-0.27, 0.75]); in close rounds (margin <= 1) +2.84c toward the winner before the print anchor vs the print's -0.87c. Steps 1-2 (censoring-free label with the union top, joiner-free markout) not run."),
        "X212": ("open", P14 + "mechanics P4: uncensored BUILD-live path against the bo3 rounds of the same maps; freeze-time refractory test",
                 "First pass (code/iter15/refractory_live.py, results/refractory_live.json): bo3 has parsed the wallet's 10-31 maps (shin-isg, gls1-pcy, bhe-bar2; development units); the uncensored X163 rows cover only shin-isg map 1 (457 value moments) and gls1-pcy map 2 (75); the print-anchored tracker snaps 11 of 23 rounds on shin-isg map 1 against 9 with the winner sequence reversed (chance level) and 1 of 21 on gls1-pcy map 2, leaving 6 rounds with both ends: no usable clock, so the refractory hazard (0.25 vs 0.48 moments per 5 s early vs action phase) is not interpretable. The wallet's non-GRID events have no socket round clock (map scores only). Open."),
        "X213": ("tried", P14 + "mechanics P5: exact series identity and rounding rule as the feed-class fingerprint",
                 "code/iter15/series_identity.py, series_identity_live.py; results/series_identity*.json. Filled co-repricings (15 units, 70 pairs within 50 ms): residual SD 1.34c around one line per (event, map, token) vs 5.64c for random pairings; 56% within 1c (null 12%); slopes 0.46 (map 1) / 0.56 (map 2) as the Bo3 formula predicts. Uncensored BUILD-live add bursts (3 units, 71 pairs; one unit trivial): SD 1.17-2.01c over 26-31c of map range, slopes 0.24-0.29, 41-43% within 1c (null SD 8-10c). The exact single-identity signature (>= 90% of pairs) fails on both records: the match quote is a strong but not exact linear function of the map quote at the same ms (consistent with an in-map update of q or a separate match input); rounding rule not identifiable at this n."),
        "X214": ("tried", P14 + "assumptions P1: decode the operator, not the wallet: account allocation as a decision component, pooled selection",
                 "Same measurements as X205 (operator_selection.json, sibling_identity.json): allocation among the attributed accounts is not fittable out of fold (20 sibling-only events in 16-22 Oct, mostly 0x7d67f01d in DraculaN / Stake / CIS LAN / PGL); v5 separates them at AUC 0.777; the two big GRID accounts are not attributed (no cross-market co-signing), so the operator's selection boundary stays non-GRID. Random-thinning bound: lift and recall unchanged, AUC about 0.88 at 42% thinning. USDC balances at listing not fetched."),
        "X215": ("ruled_out", P14 + "assumptions P2: run the frozen VALIDATE-live tests on the operator's units (declared amendment)",
                 "The pre-registered same-process gate fails (code/iter15/same_process_gate.py, results/same_process_gate.json): 0x7d67f01d on cs2-1win-5s, dota2-xe-hn (10-31) and dota2-synaps-hn (11-01): 318 orders, BUY 1.00, whole cents 0.975, band 1.00, sizes 50-60 / 100, 277 of 296 bursts single, multi-order bursts at one price (no 1c ladder), 0 co-signed pairs with the wallet within 50 ms on 10-31 (189 orders); 0xd2bb9459: single orders, no co-signing. The panel's if-false branch: the live tests wait for the wallet's own units."),
        "X216": ("ruled_out", P14 + "assumptions P3: the GRID arm via 0x10d79cc7 / 0xd2bb9459 calldata (same machine, different information set)",
                 "Premise refuted by measurement (sibling_identity.json): neither account co-signs across markets with the wallet (0 / 1 pairs at 0-5 ms vs 6 / 6 at 5-50 ms, the known sibling 13 vs 24), and their designs differ from the five-slot 100-share machine (0xd2bb9459 single 50-600-share orders, whole cents 0.88; 0x10d79cc7 20-share ladders). The on-chain GRID quoting is not the wallet's process; the GRID socket test of their values is in X204."),
        "X217": ("tried", P14 + "assumptions P5: measure the two yardsticks correctly (price against the maker population at fill time; latency against the message)",
                 "Step 2 (code/iter15/message_latency.py, results/message_latency.json): lag of its message-locked V-change decisions behind the first visible informed take: median 1.10 s (quantiles 0.10 / 0.60-0.65 / 1.10 / 1.55-1.65 / 2.2 s), co-signing mode in the first 100 ms plus a broad mode near 1 s; a source with latency L after the message precedes 85% (0.25 s), 77-79% (0.5 s), 67% (1 s). Step 1: evaluate() v6 reports price_within_tick_at_fill_m1c (the fill unit, last wallet-free print before the fill block minus 1c) beside the order unit; the population baseline at the fill (0.605, other makers' whole-cent BUY fills) is the panel's measurement (it needs public calldata, not in evaluate())."),
        "X218": ("tried", P14 + "assumptions P4: outcome replay with the wallet's own exit policy (net cap about 600, taper, re-pair)",
                 "code/iter15/exit_policy_ladder.py (X57 engine), tape_exit_policy.py (tape engine); results/exit_policy_ladder.json, tape_exit_policy.json. X57 engine: BUILD C0 0.067 / 0.275, C400 -0.325 / -0.023, C600 -0.250 / 0.061, T26 -0.258 / 0.058, T26S -0.271 / 0.040; BUILD chooses C0 -> VALIDATE 0.315 / 0.238 (the capped forms reach 0.41-0.48 Pearson but 0.11-0.21 Spearman on VALIDATE). Tape engine: caps -0.20..-0.29 Pearson on VALIDATE; its BUILD choice L1_C0 (bid-side anchor, pair cap, no cap on inventory) scores 0.197 / 0.027 on VALIDATE and replaces the v5 replay in evaluate() (v6) under the pre-registered rule. Hypothesis M rejected: with the wallet's exit policy the outcome item stays gated by its value. The re-pair variant was not run."),
    }
    for k, (st, src, ev) in new.items():
        c[k] = {"status": st, "source": src, "evidence": ev}
    c["E5"]["evidence"] += (" | Iteration 15: GDELT DOC 2.0 timeline queries for CS2 and the wallet's leagues (16-22 Oct) returned HTTP 429 "
                            "('Please limit requests to one every 5 seconds') twice with >= 6 s spacing on the shared connection "
                            "(results/e5_gdelt_check.json); Gamma comments are empty for its events (iteration 14). The selection residual is "
                            "allocation to the sibling 0x7d67f01d (operator_selection.json), not an information input; timing is sub-second "
                            "and feed-locked. Still open for a successful news query.")
    c["X188"]["evidence"] += (" | Iteration 15: the two large GRID accounts (0xd2bb9459, 0x10d79cc7) are not attributed to the operator "
                              "(no cross-market co-signing, X205 step 5); the GRID books of 10-31 have a socket round clock (X204) and "
                              "two other co-signing candidates (0x68915897, 0x5d40576b) to decode next.")
    c["X195"]["evidence"] += (" | Iteration 15: the sports socket gives a true round clock only for GRID events (20.2-s polling grid, "
                              "X204); none for the wallet's non-GRID events (map scores only). Decided-early contrast on the print clock "
                              "favours K (X209).")
    c["X189"]["evidence"] += " | Iteration 15: decided-early contrast (X209) and kill-margin slope (X211 step 3) favour in-round events (K) over round results only (R), at hypothesis level."
    # dimensions
    D = s["dimensions"]
    D["kill_level_inround_state"]["verdict"] = "inferred"
    D["kill_level_inround_state"]["note"] += (" | iteration 15: decided-early rounds show the same share of its move before the print's jump as "
                                              "elimination rounds (0.682 vs 0.680, CI of the difference [-0.20, +0.18]; R predicted -0.28), and in "
                                              "save rounds it moves before any round-end message could exist: its input carries in-round state "
                                              "(kills / plant / alive), hypothesis-level")
    D["feed_vendor_identity"]["note"] += (" | iteration 15: candidate PandaScore Low Latency Feed (titles CS2 / Dota / LoL match the fan-out; "
                                          "kill / bomb / alive data match the K reading); a token is needed (user); latency needed to carry the "
                                          "price item: about 0.25 s after the first co-receiver (85% of message-locked decisions)")
    D["feed_vendor_identity"]["best_indicator"] = "message-locked decision lag (results/message_latency.json)"
    D["operator_multi_account"]["note"] += (" | iteration 15: cross-market 0-5 ms co-signing confirms 0x7d67f01d (4.4x) and refutes "
                                            "0xd2bb9459 / 0x10d79cc7 (0 / 1 pairs vs 6 / 6); on 10-31 / 11-01 0x7d67f01d runs single "
                                            "50-60-share orders, not the five-slot ladder")
    D["pm_sports_websocket_scores"]["verdict"] = "untested"
    D["pm_sports_websocket_scores"]["note"] += (" | iteration 15: round scores for GRID events only, on a 20.2-s polling grid that "
                                                "trails the print's jump; the wallet trades no GRID event, and a 20-s clock cannot carry "
                                                "a price item that tolerates < 0.25 s (X201 / X217). No screen run: its events carry no "
                                                "round ticks, so the dimension has no content in the wallet's units")
    D["pm_sports_websocket_scores"]["status"] = "have"
    D["operator_account_routing"] = {"family": "operator", "status": "have", "source": "data-api activity of the attributed accounts (development)",
                                     "resolution": "per event", "publication_latency": "on chain", "best_indicator": "v5 score (wallet vs sibling AUC 0.777)",
                                     "min_detectable_share": None, "verdict": "inferred",
                                     "note": "iteration 15: 20 of 97 non-GRID operator events of 16-22 Oct went to siblings only (0x7d67f01d mostly); share rising 0.4 -> 0.95 over 16-22 Oct; too few for an out-of-fold model"}
    # indicators ledger rows
    I = s["indicators"]
    dl = json.load(open(RES / "decided_early_print.json"))
    I.append({"name": "X209_decided_early_before_share", "dimension": "kill_level_inround_state", "definition": "share of V's winner-signed move before the print-anchored round end, decided-early minus elimination rounds",
              "event": "bo3 end class on the print-anchored clock", "period": "BUILD+VALIDATE (descriptive, historical)",
              "result": {"point": dl["diff_before_share_decided_minus_elim_V"]["point"], "ci95": dl["diff_before_share_decided_minus_elim_V"]["ci95"],
                         "print_control": dl["diff_before_share_decided_minus_elim_P"], "rounds": dl["rounds"]}, "verdict": "K favored (R's predicted drop excluded)"})
    km = json.load(open(RES / "kill_margin.json"))
    I.append({"name": "X211_kill_margin_slope", "dimension": "kill_level_inround_state", "definition": "slope of V's mid-round winner-signed move on the round's kill margin", "event": "bo3 round margin",
              "period": "BUILD+VALIDATE (descriptive)", "result": {k: km[k] for k in km if k.startswith("slope")}, "verdict": "shared with the print (lead slope CI covers 0)"})
    ml = json.load(open(RES / "message_latency.json"))
    I.append({"name": "X217_message_lag_cdf", "dimension": "push_feed_inround_events", "definition": "lag of message-locked V-change decisions behind the first visible informed take (excess over shifted null)",
              "event": "I1 / I2 of E3-1", "period": "BUILD and VALIDATE", "result": {k: {"q": v["excess_lag_quantiles_s"], "after_L": v["share_after_L"]} for k, v in ml.items()},
              "verdict": "median 1.1 s; a source must be < ~0.25 s after the message to precede 85%"})
    gs = json.load(open(RES / "grid_socket_clock2.json"))
    I.append({"name": "X204_grid_socket_mid_round_auc", "dimension": "pm_sports_websocket_scores", "definition": "round-winner AUC of the mid-round change of a GRID maker's value (0xd2bb9459) vs the print, on the socket's round ticks",
              "event": "socket round-score change (20.2-s polling)", "period": "development live blocks (10-31 12-18)",
              "result": {k: {kk: gs[k][kk] for kk in ("rounds", "auc_V", "auc_P", "auc_V_resid_given_P")} for k in ("all", "map_books", "match_books")},
              "verdict": "no in-round lead beyond the map print; not the wallet's process"})
    # hypotheses
    H = s["hypotheses"]
    H += [
        {"id": "H152", "family": "price", "description": "R: its value steps only at the feed's round-result messages (iteration-15 explanation 1).", "validate_metrics": {"decided_early_diff": dl["diff_before_share_decided_minus_elim_V"]}, "verdict": "disfavored (X209; weak clock)"},
        {"id": "H153", "family": "price", "description": "K: its value prices in-round events (kills, plant, alive state) delivered by the feed (explanation 2).", "validate_metrics": {"decided_early_diff": dl["diff_before_share_decided_minus_elim_V"], "kill_margin_lead_slope_c": km["slope_lead_mid_per_kill_c"]}, "verdict": "favored, hypothesis-level"},
        {"id": "H154", "family": "selection", "description": "A: allocation of events among the operator's accounts (explanation 3).", "validate_metrics": {"v5_wallet_vs_sibling_auc": 0.777, "sibling_only_events": 20}, "verdict": "real but small in 16-22 Oct; not fittable; the two GRID accounts are not the operator's"},
        {"id": "H155", "family": "exit", "description": "M: the outcome is margin harvesting under the wallet's inventory cap; a capped public ladder reproduces it (explanation 4).", "validate_metrics": {"build_choice": "C0", "validate": [0.315, 0.238], "capped_validate": [0.479, 0.21]}, "verdict": "rejected (X218)"},
        {"id": "H156", "family": "price", "description": "G2: on GRID events the operator runs the machine on a public value (explanation 5).", "validate_metrics": {"attribution": "0xd2bb9459 0 vs 6 cross-market co-signed pairs"}, "verdict": "untestable as stated: the GRID accounts are not the operator's"},
        {"id": "H157", "family": "selection", "description": "O2: calendar rotation of accounts (explanation 6).", "validate_metrics": {"wallet_share_by_day": "0.4 (10-16) -> 0.95 (10-21/22)"}, "verdict": "a trend, not a rotation; untested beyond 16-22 Oct"},
        {"id": "H158", "family": "price", "description": "V: the feed is an odds product; map and match quotes come separately (explanation 7).", "validate_metrics": {"series_identity_within1c": 0.56, "live_sd_c": [1.17, 2.01]}, "verdict": "open: the exact single identity fails, but censoring and in-map q updates can produce that"},
    ]
    # target metrics and best rule
    v6 = json.load(open(RES / "final_rule_v6_validate.json"))
    tm = s["target_metrics"]
    tm["pnl_corr_pearson"] = v6["pnl_corr_pearson"]
    tm["pnl_corr_spearman"] = v6["pnl_corr_spearman"]
    s["best"] = {"rule_id": v6["rule_id"], "validate_metrics": {k: v for k, v in v6.items() if k not in ("per_wallet", "pooled", "rule_id", "constants")}}
    s["target_metrics_notes"]["pnl_iter15"] = ("v6 outcome (bid-side anchored single level with pair cap, tape engine) 0.197 / 0.027 on VALIDATE "
                                               "(v5 replay -0.131 / -0.081; prints baseline 0.329 / 0.289; partial given prints 0.176); the X57-engine "
                                               "five-slot ladder 0.315 / 0.238 needs the lot's public calldata; capped forms rejected on BUILD (X218)")
    s["target_metrics_notes"]["price_iter15"] = ("order unit at signing unchanged (0.322); the fill unit (last wallet-free print before the fill "
                                                 "block minus 1c) is reported by evaluate() as price_within_tick_at_fill_m1c; population of other "
                                                 "whole-cent makers at the fill 0.605 (assumptions panel); neither reaches 0.80 without V")
    s["progress_gauges"]["iter15_note"] = ("g3 unchanged (outcome bound 0.43 / 0.40 for an oracle copy at 2 s). The frozen executable outcome moved from "
                                           "-0.131 / -0.081 to 0.197 / 0.027 (v6); the exit policy does not lift it (X218).")
    # components
    C = s["components"]
    C["price"]["description"] += (" | Iteration 15 [hypothesis]: the private input carries in-round state, not only round results: on the "
                                  "print-anchored clock its share of the move before the print's jump is the same in decided-early rounds "
                                  "(defuse after a wipe, bomb with CTs saving) as in elimination rounds (0.682 vs 0.680; R predicted <= 0.40), and "
                                  "in save rounds it moves before any round-end message; message-locked re-pricings lag the first co-receiver by a "
                                  "median 1.1 s, so a source <= 0.25 s after the message would precede 85% of them.")
    C["price"]["confidence"] = 0.6
    C["exit"]["description"] += (" | Iteration 15: the measured exit policy (net cap about 600 CS2 shares, long-side taper from 200) does not "
                                 "carry the outcome item in a public ladder (X218: BUILD chooses no cap; capped VALIDATE Spearman <= 0.21).")
    C["selection"]["description"] += (" | Iteration 15: of the operator's attributed accounts only 0x7d67f01d takes non-GRID events the wallet "
                                      "skips (20 of 97 in 16-22 Oct, share rising to 36/38 on 10-21/22); the large GRID accounts 0xd2bb9459 / "
                                      "0x10d79cc7 are not the operator's (no cross-market co-signing), so never-GRID stays the operator's boundary.")
    C["timing"]["description"] += (" | Iteration 15: message-locked re-pricings lag the first visible informed take by a median 1.1 s (two modes: "
                                   "0-100 ms co-signing and ~1 s after its own take).")
    s["strategy_statement"] = STATEMENT
    s["status"] = "continue"
    s["wall_reason"] = None
    s["next_steps"] = NEXT
    s["iterations"].append({"n": 15, "minutes": minutes, "best_validate_score": tm["presence_auc"], "status": "continue",
                            "paradigm": "operator-level unit and the GRID socket clock as a natural experiment, plus the wallet's exit policy in the outcome replay; the same-process gate and cross-market co-signing re-decide which accounts are the operator",
                            "families": ["exit-policy outcome replay in the X57 and tape engines (X218)", "v6 bid-side anchored outcome component", "cross-market co-signing identity of the sibling accounts (X205 step 5)",
                                         "operator-level selection relabel and allocation (X214 / X205)", "GRID socket round clock: 20.2-s polling, L fit, GRID maker value vs print (X204 / X210)",
                                         "same-process gate on development-block units (X215)", "decided-early rounds R vs K (X209)", "kill-margin slope (X211 step 3)",
                                         "message-locked decision latency CDF (X217 step 2)", "series identity on filled and uncensored co-repricings (X213)", "fill-unit price metric in evaluate() (X217 step 1)",
                                         "E5 GDELT attempt (429)"],
                            "now_ts": now_ts})
    s["updated"] = now_ts
    s["data_sources"].append("iteration 15: Polymarket sports socket (shared recorder, development blocks, iter_live in 15-min slices) for GRID round ticks; data-api trades of the development-block GRID / sibling units; publicnode calldata of 0xd2bb9459 / 0x10d79cc7 / 0x7d67f01d samples (16-22 Oct and the development blocks)")
    json.dump(s, open(SP, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("catalog open:", [k for k, v in s["catalog"].items() if v.get("status") == "open"])


STATEMENT = (
    "[VALIDATE-only] A CS2 and Dota 2 in-play bot of one operator who signs for several accounts with one process (the wallet "
    "'TommyLeePeeca'; 0x52661b8e 'TommyLeePeeecan'; 0x67119033; 0x7d67f01d 'BACKTESTEOCARAIO1', confirmed again in iteration 15 by "
    "cross-market 0-5 ms co-signing at 4.4x). Two large GRID-event accounts proposed by the panel (0xd2bb9459, 0x10d79cc7) do not "
    "co-sign across markets with it and run other designs, so they are not attributed. [VALIDATE-only] Selection: whole events of "
    "non-GRID CS2 / Dota 2 leagues covered by its push-feed product, minus a small share routed to 0x7d67f01d; frozen v5 AUC 0.970 vs "
    "activity 0.886, recall 0.74 at lift 3.16, coverage 1.0. [VALIDATE-only] Maker: whole-cent BUY ladders on both outcome tokens "
    "(100 shares in CS2, 10 in Dota 2, an event-wide 54-100 ramp in some events), never sells, merges pairs in a 300-s loop (pair "
    "cost 0.978), band [0.05, 0.95], net position capped near 600 CS2 shares with a long-side taper from 200; a burst of n adds takes "
    "the n highest free slots V .. V - 4c (oracle 0.875 live). [hypothesis] V is its own in-round win-probability value fed by a "
    "private esports push feed whose messages carry in-round events (kills, plant, alive state), not only round results: it steps at "
    "the feed's messages, leads the public print by 2-5 s on them (10-45 s on average), moves before the print's jump as much in "
    "decided-early rounds as in elimination rounds, and is written to the map and match books along the Bo3 series slope (not an "
    "exact single identity). Candidate vendor: PandaScore's Low Latency Feed (titles and data points match; needs a token to test). "
    "[hypothesis] Taker: FAK buys of the team that gained on the feed's messages (>= 19 co-subscribers at fixed lags, it at +30-65 ms "
    "behind the fastest), with maker re-pricings a median 1.1 s after the first visible co-receiver take. Not decoded to the exam bar: "
    "the price item needs V to the cent at the message (a source must arrive <= ~0.25 s after it), and the outcome item needs its "
    "informed takes; the frozen v6 rule replaces V with public anchors (price 0.322 within one tick; outcome 0.197 / 0.027)."
)

NEXT = [
    "Ask the user (unchanged and new): a PandaScore token for the Low Latency Feed test (X206); demos (X37 / X122); whether the exam's wallet list should include the attributed accounts 0x7d67f01d / 0x52661b8e / 0x67119033 (X205 / X214).",
    "Close the live-only catalog items that cannot get a development unit of the wallet within the budget (the next development block, 11-01 18-24, starts after the projected end), with that reason; keep their frozen tests for the examiner's blocks.",
    "X211 steps 1-2 (censoring-free dark re-pricings with the union top; joiner-free markouts) and X212 (bo3 rounds of the 10-31 maps against the uncensored BUILD-live path).",
    "X206 key-free part: pre-game Map-N re-pricing clusters at the veto's end (LLF lists map picks; a relay reader cannot see vetoes).",
    "E5: retry GDELT when the connection is quiet; X191 LoL on the attributed accounts; X208 Dota on the wallet's own development units.",
    "Before the exam: re-fit the taker size and merge timing drift (X156) if the forward build changed; keep v6 frozen otherwise.",
]


if __name__ == "__main__":
    main(int(sys.argv[1]), float(sys.argv[2]))
