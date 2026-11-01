"""Iteration-16 state.json update (catalog X219-X231 and revised items, dimensions, indicators, hypotheses, components,
strategy statement, next steps, iteration entry). Run once at the end of iteration 16:
    .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter16/write_state16.py NOW_TS MINUTES"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SP = ROOT / "research/reverse_engineering/tommy-cs2-maker/state.json"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def J(name):
    return json.load(open(RES / name, encoding="utf-8"))


def main(now_ts: int, minutes: float):
    s = json.load(open(SP, encoding="utf-8"))
    c = s["catalog"]
    I = s["indicators"]  # noqa: E741
    D = s["dimensions"]
    sfg, mc, pg = J("same_feed_gate.json"), J("map_counts.json"), J("pregame_clusters.json")
    dem, dek = J("decided_early_printmatch.json"), J("decided_early_clock_printmatch_15_30.json")
    sh, ga, fo = J("shadow_persistence.json"), J("grid_arm_anchor.json"), J("fanout_after_t0.json")
    inv, leak, tx = J("inventory_skew.json"), J("clob_wallets_leak.json"), J("telonex_availability.json")
    tc = J("tiny_cap_pairlock.json") if (RES / "tiny_cap_pairlock.json").exists() else None
    P = "panel iteration 15 "
    tc_ev = ("not run" if tc is None else
             f"code/iter16/tiny_cap_pairlock.py, results/tiny_cap_pairlock.json: BUILD scores {tc['build_scores']}; chosen {tc['chosen_on_BUILD']}; "
             f"VALIDATE {tc['VALIDATE_chosen']['corr'][:2]} (halves {tc['VALIDATE_chosen_halves']}); adopted {tc['adopt']}. "
             f"VALIDATE all variants: { {k: tc['VALIDATE'][k]['corr'][:2] for k in tc['build_scores']} }; prints baseline {tc['VALIDATE']['prints_baseline'][:2]}.")
    new = {
        "X219": ("open", P + "information P1: record the vendor's push socket live, stamped at receipt (strong form of X206)",
                 "User-gated: needs a PandaScore token (account creation is the user's; key-free requests return HTTP 403 'Token is missing', X206). "
                 "Its key-free step 0 is X221 (run: no pre-game vendor fingerprint). Ranked first of the user asks: only a receipt-stamped live "
                 "recording can carry the examined price item point in time."),
        "X220": ("tried", P + "information P2: historical tick-level Polymarket book for 16-22 Oct (Telonex; PMXT verified absent)",
                 "Step 1 run key-free (results/telonex_availability.json): https://api.telonex.io/v1/availability/polymarket?asset_id=<token> "
                 "answers 200 without a key; for cs2-priv-fnc-2026-10-21, cs2-faze-jjh-2026-10-21, cs2-fnc-prv-2026-10-20 it lists book_snapshot_full, "
                 "book_snapshot_25, book_snapshot_5, quotes and onchain_fills from 10-19 / 10-20 to 10-21 / 10-22. Downloads need an API key (the SDK's "
                 "download() requires api_key): steps 2-5 are user-gated (free trial: 5 file downloads; $99 a month). Development dates only were requested."),
        "X221": ("tried", P + "information P3: vendor fingerprint from pre-game (veto / draft) messages, at the vendor level",
                 f"code/iter16/pregame_clusters.py, results/pregame_clusters.json: {pg['events']} events, {pg['takes']} group-P / G takes in [-60, +30] min "
                 f"of the scheduled start; pre-start fan-out clusters {pg['pre_start']['clusters']} (null {pg['pre_start']['null']}) in only "
                 f"{pg['pre_start']['events_with_pre_clusters']} events, 15 of them in two events spread like in-play activity; share of events with half "
                 f"their clusters in one 3-min window 5-30 min before the start {pg['pre_start']['share_events_half_in_one_window_5_30min']}; "
                 f"in-play 0-5 min 47, 5-30 min 308. Pre-registered verdict: not LLF-like (no veto bursts). Map-pick direction (step 2) and the Dota "
                 "draft (step 3) not run: no pre-start clusters to type."),
        "X222": ("tried", P + "information P4: wallet-independent recording of what it sees; clob_wallets presence leak; recorders stop 11-03",
                 f"code/iter16/clob_wallets_leak.py, results/clob_wallets_leak.json (10-31 12-18, 9 traded markets): share first subscribed after its "
                 f"first trade {leak['share_first_sub_after_first_trade']} (190-1,139 s after; 2 never in the readable record; 1 subscribed 71 min "
                 "earlier); just under the 0.90 bar, conditioned on presence in substance. clob_wallets is forbidden as a presence / selection input "
                 "(FINAL_RULE.md; evaluate() uses it only as the live price fallback). The subs hour file 10-31 12:00-13:00 is unreadable (zlib). "
                 "No successor recorder started: the next exam lot (h1) has no live input; extending recorders past 11-03 is the user's call."),
        "X223": ("open", P + "mechanics P1: is V* a public-score table once the clamp and fill censoring are removed?",
                 "Historical form blocked by measurement: the diagnostic clock of step 2 (ms-synchronous map / match co-repricings in one team "
                 f"direction) does not exist on the filled record: {mc['means']['n_co_large']} large + {mc['means']['n_co_small']} small co-repricings "
                 f"per map against {mc['means']['rounds']} rounds (results/map_counts.json); the BUILD-live maps have no usable round clock (X212). "
                 "Needs the uncensored ladder of 16-22 Oct (X220 downloads, user-gated) or a real-time round score."),
        "X224": ("tried", P + "mechanics P2: clamp-aware price rule with an own-inventory skew for the forward blocks",
                 f"Historical part (code/iter16/inventory_skew.py, results/inventory_skew.json): order unit at signing, VALIDATE: wallet-free tape "
                 f"{inv['wallet_free']['validate_k0']} -> {inv['wallet_free']['validate_bucket_k_own_state']} with the BUILD-fitted skew "
                 f"(k by net bucket {inv['wallet_free']['bucket_k_build']}); evaluate()'s tape {inv['eval_tape']['validate_k0']} -> "
                 f"{inv['eval_tape']['validate_bucket_k_own_state']}; inside 200-600 shares +2.6..+4.4 points. Real but tiny; not adopted. The live "
                 "regime classifier and machine set unit need VALIDATE-live wallet units (none inside the budget)."),
        "X225": ("open", P + "mechanics P3: read the operator's valuation from the taker regime's pre-signed conditional order sets",
                 "Not run: the bracket fit needs the bo3 score at each sign moment, i.e. a round clock in the taker regime (GRID events before "
                 "10-16; the sports socket was not recorded then; the print clock snaps 1.3x). The panel's measurement stands (352 same-moment "
                 "pairs, BUY/BUY limits summing to 1.03-1.20, median width 6c). Clock-free form (sign moments per map vs rounds / kills, like X226) "
                 "is the next step."),
        "X226": ("tried", P + "mechanics P4: clock-free R versus K from per-map counts of round-sized co-repricings",
                 f"code/iter16/map_counts.py, results/map_counts.json: {mc['maps']} maps; negative binomial with log(rounds) offset: all V-changes kills per "
                 f"round {mc['n_all|offset_only']['kpr_c']['coef']} (p {mc['n_all|offset_only']['kpr_c']['p']}), with controls "
                 f"{mc['n_all|with_controls']['kpr_c']['coef']} (p {mc['n_all|with_controls']['kpr_c']['p']}); large (>= 4c) "
                 f"{mc['n_large|offset_only']['kpr_c']['coef']} / {mc['n_large|with_controls']['kpr_c']['coef']}, log(rounds) free "
                 f"{mc['n_large|rounds_free']['l_rounds']['coef']} (SE {mc['n_large|rounds_free']['l_rounds']['se']}); plants per round n.s. in every "
                 "class (co-repricings negative). R signature holds, K absent; one-move-per-kill excluded (CI upper +0.05 vs +0.15 predicted); a plant "
                 "form is not excluded by power."),
        "X227": ("tried", P + "assumptions P1: same-feed gate on the operator's development units, then the frozen live information tests",
                 f"code/iter16/same_feed_gate.py, results/same_feed_gate.json: 0x7d67f01d on the four units, {sfg['G1_pooled']['a7_takes']} takes, "
                 f"{sfg['G1_pooled']['cosigned']} co-signed with group P / G within 300 ms (null {sfg['G1_pooled']['null_share_mean']}); lag median "
                 "+54 ms but IQR 69.5 ms on the9-5s (bar 40 ms), 0 of 78 Dota takes co-signed; G2 new-high markout "
                 f"{sfg['G2_newhigh']['mean_m60_c']}c at 60 s (n {sfg['G2_newhigh']['n']}, bar 1.0). Gate FAILED. Thunderpick: no tommy_tp_odds2 record of "
                 "any operator unit (only GRID matches carried odds), so X168 has no unit. Exploratory Valve lock on dota2-synaps-hn "
                 "(results/valve_lock_a7.json): no excess at any lag window (0.56-0.85 of the null)."),
        "X228": ("tried", P + "assumptions P2: re-attribute the GRID accounts by the shadow fingerprint; GRID arm as the public-information control; LoL twin",
                 f"Step 1 (code/iter16/shadow_persistence.py, results/shadow_persistence.json; 16-22 Oct, 1,761 txs decoded): 0x67119033 vs 0x10d79cc7 "
                 f"{sh['result']['0x67119033']['0x10d79cc7']['pairs_0_5ms']} pairs at 0-5 ms vs {sh['result']['0x67119033']['0x10d79cc7']['pairs_5_50ms']} "
                 f"at 5-50 ms ({sh['result']['0x67119033']['0x10d79cc7']['per_ms_ratio']}x per ms); 0x52661b8e vs 0x10d79cc7 "
                 f"{sh['result']['0x52661b8e']['0x10d79cc7']['pairs_0_5ms']} vs {sh['result']['0x52661b8e']['0x10d79cc7']['pairs_5_50ms']}; vs 0xd2bb9459 0 / 0 "
                 "for both; controls 0 pairs at 0-5 ms. 0x10d79cc7 is attributed to the operator (separate loop), 0xd2bb9459 not. Step 2 "
                 f"(code/iter16/grid_arm_anchor.py, results/grid_arm_anchor.json): 0x10d79cc7's {ga['all_orders']['n']} orders in GRID events of 10-16 "
                 f"within one tick of the last clean print + k at most {max(ga['all_orders']['within_1c_of_print_plus_k'].values())} (bar 0.45): not a "
                 "public-print quoter, so the public-information control premise fails. Step 3 (LoL twin) not run (moved to X207)."),
        "X229": ("tried", P + "assumptions P3: re-time the public tape at the CLOB match and split the message-locked decision by its clock",
                 f"Step 1 (code/iter16/decided_early_match.py; results/decided_early_clock_printmatch_15_30.json, decided_early_printmatch.json, "
                 f"dark_round_winner_printmatch.json): snaps {dek['snapped']} vs {dek['snapped_placebo_reversed']} reversed (1.33x; block 1.30x; bar 1.6: "
                 f"no improvement); V share mid / late / end / after {dek['V_share_mid_late_end_after']}; decided-early minus elimination before-share "
                 f"{dem['diff_before_share_decided_minus_elim_V']['point']} CI {dem['diff_before_share_decided_minus_elim_V']['ci95']} (block clock +0.002 "
                 "[-0.20, +0.18]): R's predicted -0.28 is inside the CI, so X209's K reading does not survive; where the winner changes, dark agreement "
                 "with the current winner 0.50-0.54. Steps 2-3 (class decomposition with markouts; class-3 book function on BUILD-live) not run."),
        "X230": ("tried", P + "assumptions P4: test whether the 16-22 Oct fan-out survived after T0",
                 f"code/iter16/fanout_after_t0.py, results/fanout_after_t0.json: reference 16-22 Oct {fo['reference']['clusters']} clusters in "
                 f"{fo['reference']['events_with_clusters']} events (P4e in 285, first in 251); after T0 on the four completely decoded operator units: "
                 f"P4e 0 takes, takes by member {fo['after_t0']['takes_by_member_after_t0']}; trio internal lags unchanged (median 0-9 ms, IQR 10-37 ms). "
                 "The fan-out lost its first signer; gp72 can fall by at most 1 where P4e alone covered a league. h1 / h2 cannot be checked (sealed); "
                 "evaluate() unchanged (the examiner's listing halves separate earlier and later units)."),
        "X231": ("tried", "self-proposed (iteration 16): a small net cap turns the public bid-side ladder's PnL into locked pair margin", tc_ev),
    }
    for k, (st, src, ev) in new.items():
        c[k] = {"status": st, "source": src, "evidence": ev}
    if (RES / "taker_map_counts.json").exists():
        tmc = J("taker_map_counts.json")
        if tmc.get("offset_only"):
            c["X225"]["status"] = "tried"
            c["X225"]["evidence"] += (f" | Iteration 16, clock-free step 4 (code/iter16/taker_map_counts.py, results/taker_map_counts.json): "
                                      f"{tmc.get('maps_with_orders')} taker-regime maps (10-01..10-15), sign moments per map: kills per round "
                                      f"{tmc['offset_only']['kpr_c']}, plants per round {tmc['offset_only']['ppr_c']}; log(rounds) free "
                                      f"{tmc['rounds_free']['l_rounds']}. The bracket fit (steps 1-3) still needs a taker-regime round clock.")
    tk_clock, tk_track, dctl = J("taker_moment_clock.json"), J("taker_moment_tracker.json"), J("counts_duration_control.json")
    c["X225"]["evidence"] += (f" | Steps 4b-4c (taker_moment_clock.json, taker_moment_tracker.json): the sign moments are not a round clock: "
                              f"cumulative-duration fit {tk_clock['snaps']} vs {tk_clock['snaps_reversed']} reversed ({tk_clock['ratio']}x), "
                              f"winner-direction tracker {tk_track['snaps']} vs {tk_track['snaps_reversed']} ({tk_track['ratio']}x); gap CV "
                              f"{tk_clock['cv_gap_median']} vs round-duration CV {tk_clock['cv_round_duration_median']}: arming at a roughly constant "
                              "rate; with log(duration) added (counts_duration_control.json) the moments follow rounds 0.94 and duration 0.67, "
                              "kills / plants per round stay negative. The per-round re-arm reading is withdrawn.")
    c["X226"]["evidence"] += (" | Duration control (counts_duration_control.json): with log(map duration) added, all V-changes follow rounds "
                              f"{dctl['maker_X226']['n_all|dur_and_rounds']['l_rounds']} and not duration {dctl['maker_X226']['n_all|dur_and_rounds']['l_dur']}; "
                              "kills per round stays <= 0, plants n.s.: the R reading survives.")
    c["X195"]["status"] = "tried"
    c["X195"]["evidence"] += (" | Iteration 16: every available anchor set measured as a non-GRID round clock fails (block print 1.30x, "
                              "match-time print 1.33x (X229), informed takes 1.34-1.39x, taker-regime sign moments 1.04-1.07x (X225 4b-4c)); "
                              "the sports socket has rounds for GRID events only. A true clock needs the vendor feed (X219) or demos (X37).")
    c["X190"]["status"] = "tried"
    c["X190"]["evidence"] += (" | Iteration 16: re-stamping the prints at the CLOB match does not sharpen the public round clock (1.33x vs 1.30x, "
                              "X229); about 90% of its value changes precede any public trade (X229 step 2), so a public round-end signal "
                              "cannot carry the price item; closed as tried.")
    c["X189"]["status"] = "tried"
    c["X189"]["evidence"] += (" | Iteration 16: R vs K now leans R (X226 counts follow rounds, not time, no kills / plants term; X229 decided-early "
                              "contrast R-compatible on the match clock); the economy input was rejected in iteration 15 (X160); the score-table "
                              "fit on a feed clock stays blocked by the absence of a clock (X195).")
    I.append({"name": "X225_taker_moment_clock", "dimension": "feed_time_round_end_clock", "definition": "taker-regime sign moments as round-end anchors (cumulative bo3 durations; winner-direction tracker) vs reversed sequences",
              "event": "sign moment", "period": "taker regime 10-01..10-15", "result": {"cumulative": tk_clock, "tracker": tk_track}, "verdict": "not a clock (1.04-1.07x)"})
    I.append({"name": "X226_X225_duration_control", "dimension": "feed_time_round_end_clock", "definition": "per-map counts with log(rounds) and log(duration) both in the NB model",
              "event": "bo3 per-map totals", "period": "16-22 Oct and 10-01..10-15", "result": dctl, "verdict": "maker V-changes follow rounds, not time; taker arming follows both"})
    wm, p4 = J("wallet_markouts_t0.json"), J("p4e_after_t0.json")
    c["X230"]["evidence"] += (f" | Step 3 (wallet_markouts_t0.json): its 10-31 12-18 new highs move the clean print +{wm['mean_m60_c']}c at 60 s "
                              f"(n {wm['new_highs']}) vs +2.62 / +2.50c in 16-22 Oct. Qualifier (p4e_after_t0.json): P4e has no trade in any known "
                              "development unit of 10-31 12-18 (127 rows elsewhere, dropped unread) and no trade at all in 11-01 06-12; RN1 and the "
                              "trio are active. The first signer is gone; the wallet's edge remains at about three quarters of its size.")
    I.append({"name": "X230_wallet_newhigh_markout_after_T0", "dimension": "push_feed_inround_events", "definition": "60-s clean-print markout of its new-high value changes",
              "event": "own V-change (decision)", "period": "development block 10-31 12-18 vs 16-22 Oct", "result": wm, "verdict": "edge persists (+1.89c vs +2.5-2.6c)"})
    if (RES / "selection_without_p4e.json").exists():
        sw = J("selection_without_p4e.json")
        c["X230"]["evidence"] += (f" | Exam-risk check (selection_without_p4e.json): frozen v5 on VALIDATE with gp72 recomputed without P4e "
                                  f"(coefficients unchanged): {sw['without_P4e']} vs all members {sw['all_members']}.")
        s["target_metrics_notes"]["selection_iter16_p4e"] = (f"robustness: v5 VALIDATE selection without P4e in gp72 {sw['without_P4e']} "
                                                             f"vs {sw['all_members']} (frozen coefficients)")
    cc = J("censoring_check.json")
    I.append({"name": "censoring_check_buildlive", "dimension": "own_resting_levels", "definition": "visibility of uncensored value changes on the filled record vs print-jump proximity",
              "event": ">= 2c clean-print jump within +-10 s", "period": "BUILD-live 10-31 12-18", "result": cc,
              "verdict": "fills not concentrated at jump moments (6.0% vs 7.4%); size-biased (>= 4c 0.48 vs 0.37)"})
    c["X226"]["evidence"] += (f" | Censoring check (censoring_check.json, BUILD-live): {cc['filled_share']} of {cc['value_changes_uncensored']} uncensored "
                              f"value changes are filled; near a >= 2c jump {cc['filled']['near_2c_jump_10s']} (filled) vs {cc['unfilled']['near_2c_jump_10s']} "
                              "(unfilled): the filled record is not a jump-timed sample.")
    cr = J("clamp_regime.json")
    c["X224"]["evidence"] += (f" | Live part (clamp_regime.json, BUILD-live first half fit / second half scored): regime shares {cr['regime_shares']}; "
                              f"public classifier accuracy {cr['public']['regime_accuracy']} vs largest class {cr['public']['largest_class_share']} "
                              f"(own state {cr['with_own_state']['regime_accuracy']}); rule within one tick {cr['public']['w1_rule']} vs J "
                              f"{cr['public']['w1_J']}, oracle {cr['public']['w1_oracle_J_or_askm1']}: the anchor choice is V*, the frozen touch rule stays.")
    I.append({"name": "X224_clamp_regime_classifier", "dimension": "pm_book_levels_queue_cancels", "definition": "public live-book state -> clamp regime of the new top (pinned / join / between / below)",
              "event": "own add (BUILD-live)", "period": "BUILD-live 10-31 12-18 (time split)", "result": cr, "verdict": "no usable selector (0.387 vs base 0.305)"})
    e5 = J("e5_gdelt_hourly.json")
    c["E5"]["status"] = "tried"
    c["E5"]["evidence"] += (f" | Iteration 16 (code/iter16/e5_gdelt_hourly.py, results/e5_gdelt_hourly.json): GDELT DOC 2.0 answered (200): "
                            f"{e5['articles_total']} 'counter-strike' articles in {e5['hours']} hours of 16-22 Oct; Spearman with hourly V-change "
                            f"decisions {e5['spearman_art_dec']}, partial given events in play and hour of day {e5['partial_rank_corr_art_dec_given_events_hod']}: "
                            "no news effect at the hour scale; sub-second timing is out of reach of wires; the selection residual is allocation.")
    D["news_rss_wires"]["status"] = "have"
    D["news_rss_wires"]["note"] = (D["news_rss_wires"].get("note", "") + " | iteration 16: GDELT hourly article counts (24 in 163 h) vs decisions: "
                                   "Spearman -0.07, partial -0.15; one indicator at one horizon, so the verdict stays untested by the brief's no_effect rule")
    I.append({"name": "E5_gdelt_hourly_articles", "dimension": "news_rss_wires", "definition": "GDELT DOC 2.0 timelinevolraw 'counter-strike' hourly article count",
              "event": "level (hourly)", "period": "BUILD+VALIDATE (16-22 Oct)", "result": e5, "verdict": "no effect at the hour scale"})
    if (RES / "taker_map_counts.json").exists():
        I.append({"name": "X225_taker_regime_map_counts", "dimension": "feed_time_round_end_clock",
                  "definition": "taker-regime sign moments per map on kills / plants per round, log(rounds) offset, NB", "event": "bo3 per-map totals (clock-free)",
                  "period": "taker regime 10-01..10-15 (development)", "result": J("taker_map_counts.json"), "verdict": "about one sign moment per round; negative kills / plants terms (R)"})
    s["progress_gauges"]["iter16_note"] = ("No gauge moved. The price item's private part is now stated by clock class (about 90% of value changes "
                                           "carry V before any public trade); no inventory cap lets a public ladder track the outcome (X231); "
                                           "the historical book that would lift the live and historical anchors is for sale (Telonex, key needed).")
    s["target_metrics_notes"]["iter16"] = ("unchanged from iteration 15 (rule v6 frozen): own-inventory skew 0.305 -> 0.311 (wallet-free order unit) "
                                           "not adopted; capped outcome ladders negative on VALIDATE (X231)")
    c["X207"]["status"] = "open"
    c["X191"]["evidence"] = (c["X191"].get("evidence") or "") + (" | Iteration 16: one Leaguepedia cargo query (ScoreboardGames, 2026-10-20) "
                             "answered HTTP 200 with error code 'ratelimited' on the shared connection; not run.")
    c["X207"]["evidence"] += (" | Iteration 16: premise restored for 0x10d79cc7, which the operator's shadows follow at 0-5 ms in 16-22 Oct (X228 "
                              "step 1); its LoL quoting is the operator's (separate loop). The Leaguepedia / Riot livestats fit is not run.")
    c["X216"]["status"] = "tried"
    c["X216"]["evidence"] += (" | Iteration 16 (X228): 0x10d79cc7 is the operator's by the shadow fingerprint (separate loop), with 20-share ladders; "
                              "its GRID value is not print + offset (at most 0.147 within one tick), so the 'same machine on a public value' "
                              "reading fails; the GRID arm runs on its own input.")
    c["X215"]["evidence"] += " | Iteration 16: the information form of the gate (same feed, X227) fails too."
    c["X209"]["evidence"] += (" | Iteration 16 (X229): on the match-time print clock the difference is -0.138 [-0.451, +0.085]; R's predicted -0.28 "
                              "is no longer excluded; K is not favored by this test.")
    c["X206"]["evidence"] += (" | Iteration 16: key-free veto-timing test run as X221 (no pre-game vendor fingerprint); live token test is X219.")
    c["X188"]["evidence"] += (" | Iteration 16: by the shadow fingerprint 0x10d79cc7 is the operator's GRID / LoL loop (X228); its GRID value is not "
                              "the public print (0.147 within one tick).")
    c["X168"]["evidence"] += (" | Iteration 16: no tommy_tp_odds2 record of any operator unit in 11-01 06-12 (bo3's live index carried odds only for "
                              "GRID matches among the Polymarket events); no unit before the recorders stop.")
    c["X208"]["evidence"] += (" | Iteration 16: the operator sibling fails the same-feed gate on its Dota units (X227: 0 of 78 Dota takes "
                              "co-signed); exploratory Valve lock on dota2-synaps-hn null (0.56-0.85 of the shifted null).")
    c["X212"]["evidence"] += " | Iteration 16: co-repricings are too rare on the filled record to serve as a clock (1.2 per map, X226)."
    # dimensions
    D = s["dimensions"]
    D["kill_level_inround_state"]["verdict"] = "untested"
    D["kill_level_inround_state"]["note"] += (" | iteration 16 (filled record; fills cluster at sweeps): clock-free per-map counts show no kills or plants effect at fixed rounds "
                                              "(X226; one-move-per-kill excluded); on the match-time print clock the decided-early contrast is "
                                              "-0.14 [-0.45, +0.09], R-compatible (X229). The R reading is favoured; a small in-round part "
                                              "(plants / duels) is not excluded by power (plants SE 0.38).")
    D["kill_level_inround_state"]["min_detectable_share"] = "per-map count test: +0.15 per kill per round excluded (upper CI +0.05); plant effect of +0.4 not excluded"
    D["feed_vendor_identity"]["note"] += (" | iteration 16: no pre-game veto fan-out (X221: 20 pre-start clusters in 5 of 73 events, spread like "
                                          "in-play); the first signer P4e left the fan-out after T0 (X230).")
    D["operator_multi_account"]["note"] += (" | iteration 16: the shadows follow 0x10d79cc7 at 0-5 ms in 16-22 Oct (10 vs 2 pairs, controls 0): "
                                            "0x10d79cc7 is the operator's GRID / LoL loop; 0xd2bb9459 unattributed")
    D["grid_official_data"]["note"] = (D["grid_official_data"].get("note", "") + " | iteration 16: the operator's GRID arm (0x10d79cc7) does not "
                                       "quote at the public print (0.147 within one tick), so it runs on another input; GRID's official data is "
                                       "the candidate (blocked: signup)")
    D["dota_spectator_state_valve"]["note"] = (D["dota_spectator_state_valve"].get("note", "") + " | iteration 16: the only operator unit with "
                                               "snapshots (dota2-synaps-hn, 0x7d67f01d) fails the same-feed gate; exploratory lock null")
    D["pm_book_history_vendor"] = {"family": "polymarket_internal", "status": "blocked",
                                   "source": "Telonex (api.telonex.io): book_snapshot_full / 25 / 5, quotes, onchain_fills per market-day",
                                   "resolution": "tick (book snapshots; cadence not verified)", "publication_latency": "daily files after midnight UTC",
                                   "best_indicator": "others' best bid J at signing - 100 ms (0.499 on BUILD-live set unit vs print 0.322)",
                                   "min_detectable_share": None, "verdict": "untested",
                                   "note": "iteration 16: availability verified key-free for development CS2 markets (10-19..10-22); downloads need the user's API key"}
    D["pm_book_levels_queue_cancels"]["note"] = (D["pm_book_levels_queue_cancels"].get("note", "") + " | iteration 16: clob_wallets is "
                                                 "subscribed after the wallet's first trade in 8 of 9 markets (X222): never a presence input")
    # indicators
    I = s["indicators"]
    I.append({"name": "X226_per_map_counts", "dimension": "kill_level_inround_state",
              "definition": "per-map count of V-changes (all, >= 4c, 1-3c, co-repriced) on kills per round and plants per round, log(rounds) offset, NB",
              "event": "bo3 per-map totals (clock-free)", "period": "BUILD+VALIDATE (16-22 Oct, 94 maps)",
              "result": {k: v for k, v in mc.items() if "|" in k and k.split("|")[0] in ("n_all", "n_large", "n_small")}, "verdict": "no kills / plants effect (R signature)"})
    I.append({"name": "X229_match_time_print_clock", "dimension": "feed_time_round_end_clock",
              "definition": "print-anchored round clock with prints re-stamped at min(block, taker sign + 1.04 s)", "event": ">= 2c clean-print jumps",
              "period": "BUILD+VALIDATE (historical)", "result": {"snapped": dek["snapped"], "reversed": dek["snapped_placebo_reversed"],
                                                                   "decided_early_diff": dem["diff_before_share_decided_minus_elim_V"]},
              "verdict": "clock not sharper (1.33x); decided-early contrast R-compatible"})
    I.append({"name": "X221_pregame_fanout_clusters", "dimension": "feed_vendor_identity",
              "definition": ">= 2 group-P / G members within 300 ms before the scheduled start", "event": "fan-out cluster", "period": "BUILD+VALIDATE (16-22 Oct)",
              "result": pg["pre_start"], "verdict": "not LLF-like (no veto bursts)"})
    I.append({"name": "X227_same_feed_gate", "dimension": "pm_other_wallets_feed_subscribers",
              "definition": "operator sibling takes co-signed with group P / G within 300 ms; new-high markout at 60 s", "event": "fan-out message",
              "period": "development blocks 10-31 12-18, 11-01 06-12", "result": {"G1": sfg["G1_pooled"], "G2": {"n": sfg["G2_newhigh"]["n"], "mean_m60_c": sfg["G2_newhigh"]["mean_m60_c"]}, "gate": sfg["gate"]},
              "verdict": "gate failed"})
    I.append({"name": "X227_valve_lock_exploratory", "dimension": "dota_spectator_state_valve",
              "definition": "operator sibling Dota V-changes vs Valve kill-count snapshot events, lags -60..+60 s, circular shifts",
              "event": "team kill count rises between snapshots", "period": "development block 11-01 06-12 (one event)",
              "result": J("valve_lock_a7.json").get("windows"), "verdict": "exploratory null (gate failed)"})
    # hypotheses
    H = s["hypotheses"]
    H += [
        {"id": "H159", "family": "price", "description": "R (iteration-16 explanation 1): round results from the push feed, early.", "validate_metrics": {"map_counts_large_kpr": mc["n_large|offset_only"]["kpr_c"], "decided_early_match_clock": dem["diff_before_share_decided_minus_elim_V"]}, "verdict": "favoured on the filled record (X226 with duration control, X229); fills cluster at sweeps, so the uncensored ladder must confirm; the taker-regime arming is not round-locked (X225 4b-4c)"},
        {"id": "H160", "family": "price", "description": "K (explanation 2): kill / bomb state from a vendor low-latency feed.", "validate_metrics": {"map_counts_all_kpr": mc["n_all|offset_only"]["kpr_c"]}, "verdict": "disfavoured in its per-kill form; plant form not excluded"},
        {"id": "H161", "family": "price", "description": "T (explanation 3): V* is a public round-score table hidden by the clamp and fill censoring.", "validate_metrics": {"co_repricings_per_map": mc["means"]["n_co_large"] + mc["means"]["n_co_small"]}, "verdict": "untestable on the filled record (no clock); needs X220 books"},
        {"id": "H162", "family": "price", "description": "D (explanation 4): the feed's Dota half is Valve's spectator state.", "validate_metrics": {"gate": sfg["gate"]}, "verdict": "not testable on the operator's units (gate failed); exploratory null"},
        {"id": "H163", "family": "price", "description": "O (explanation 5): the value is a bookmaker's in-play line (Thunderpick).", "validate_metrics": {"operator_units_with_tp_records": 0}, "verdict": "no unit; open"},
        {"id": "H164", "family": "price", "description": "W (explanation 6): dark re-pricings read other makers' public cancel waves.", "validate_metrics": {"telonex_availability": "verified, key needed"}, "verdict": "untested (needs books)"},
        {"id": "H165", "family": "selection", "description": "F (explanation 7): the feed or the routing changed after H.", "validate_metrics": {"p4e_takes_after_t0": 0}, "verdict": "partly: P4e left the fan-out after T0; trio and RN1 unchanged"},
    ]
    # components
    C = s["components"]
    C["price"]["description"] += (" | Iteration 16 [hypothesis]: on the filled record the input is mostly round results delivered early (R): no "
                                  "kills or plants effect on clock-free per-map counts that follow rounds, not time (X226), and the decided-early "
                                  "contrast is R-compatible on the match-time clock (X229); about 90% of its value changes precede any public trade "
                                  "(X229 step 2); own-inventory skew -1c / -2c by net bucket (X224, +0.006 only).")
    C["selection"]["description"] += (" | Iteration 16: the operator also quotes GRID (and LoL) events through 0x10d79cc7 (shadow fingerprint, "
                                      "X228), a separate loop on a non-public input; never-GRID is the wallet loop's boundary. The fan-out's first "
                                      "signer P4e is absent after T0 (X230).")
    C["timing"]["description"] += (" | Iteration 16: re-stamped at the CLOB match, about 0.14 of its pre-print move falls at or after the trade "
                                   "(X229); the operator sibling's takes are rarely on the 16-22 Oct fan-out after T0 (5 of 127, X227).")
    C["timing"]["confidence"] = 0.66
    s["strategy_statement"] = STATEMENT
    s["status"] = "continue"
    s["wall_reason"] = None
    s["next_steps"] = NEXT
    s["iterations"].append({"n": 16, "minutes": minutes, "best_validate_score": s["target_metrics"]["presence_auc"], "status": "continue",
                            "paradigm": "operator sibling as the unit on the recorded development blocks (same-feed gate), clock-free per-map totals, the public tape re-stamped at the CLOB match, shadow re-attribution of the GRID accounts, and the historical book's availability",
                            "families": ["same-feed gate on 0x7d67f01d's development units (X227)", "exploratory Valve lock (X227)", "clock-free per-map counts (X226)",
                                         "match-time print clock and decided-early / previous-winner re-run (X229)", "pre-game vendor fan-out clusters (X221)",
                                         "clob_wallets presence leak (X222)", "own-inventory skew on the order unit (X224)", "Telonex availability (X220)",
                                         "shadow persistence 16-22 Oct (X228 step 1)", "GRID arm anchoring to the print (X228 step 2)", "fan-out after T0 (X230)",
                                         "small-net-cap pair-lock outcome replay (X231)"],
                            "now_ts": now_ts})
    s["updated"] = now_ts
    s["tool_bugs"].append("tools/live.py iter_live('subs', ...) raises zlib.error ('invalid block type') on the 10-31 12:00 hour file as well (subs, sports and clob hour 12 are affected); read in 15-min slices with try/except")
    s["data_sources"].append("iteration 16: data-api trades and publicnode calldata of 0x7d67f01d's four development-block units; data-api activity (16-22 Oct) of 0x67119033 / 0x52661b8e / 0x10d79cc7 / 0xd2bb9459 and 1,761 decoded txs; data-api taker tapes of 0x10d79cc7's GRID markets of 10-16; Telonex availability endpoint (key-free, development tokens); tommy_tp_odds2 / tommy_dota_rt / subs via iter_live (development blocks)")
    json.dump(s, open(SP, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("catalog open:", [k for k, v in s["catalog"].items() if v.get("status") == "open"])


STATEMENT = (
    "[VALIDATE-only] A CS2 and Dota 2 in-play bot of one operator who signs for several accounts (the wallet 'TommyLeePeeca'; "
    "0x7d67f01d, the earlier account of the same maker strategy; the shadow accounts 0x52661b8e and 0x67119033; and, from the "
    "shadows' 0-5 ms fingerprint in iteration 16, 0x10d79cc7, a separate 20-share GRID / LoL loop). [VALIDATE-only] Selection: whole "
    "events of non-GRID CS2 / Dota 2 leagues covered by its push-feed product, minus a small share routed to 0x7d67f01d; frozen v5 AUC "
    "0.970 vs activity 0.886, recall 0.74 at lift 3.16, coverage 1.0. [VALIDATE-only] Maker: whole-cent BUY ladders on both outcome "
    "tokens (100 shares in CS2, 10 in Dota 2, an event-wide 54-100 ramp in some events), never sells, merges pairs in a 300-s loop (pair "
    "cost 0.978), band [0.05, 0.95], net position capped near 600 CS2 shares with a long-side taper from 200 and a 1-2c price skew "
    "when long; a burst of n adds takes the n highest free slots V .. V - 4c, clamped at or below others' ask - 1c (oracle 0.875 "
    "live). [hypothesis] V is its own win-probability value driven by a private esports push feed whose informative messages are "
    "mostly round results delivered early (no kills or plants effect on clock-free per-map counts; decided-early rounds compatible "
    "with round-end messages on the match-time clock), with a small in-round part; it re-prices in the same second as the informed "
    "trades at their CLOB match and at many messages no public trade shows. Vendor unidentified (no pre-game veto fan-out; PandaScore "
    "needs a token). [hypothesis] Taker: FAK buys of the team that gained on the feed's messages (>= 19 co-subscribers at fixed lags in "
    "16-22 Oct; the first signer P4e is absent after T0). Not decoded to the exam bar: the price item needs V to the cent at the "
    "message, and the outcome item needs its informed takes; the frozen v6 rule replaces V with public anchors (price 0.322 within "
    "one tick; outcome 0.197 / 0.027)."
)

NEXT = [
    "User asks, ranked: (1) a PandaScore token with live LLF access, recorded at receipt (X219); (2) a Telonex API key (free trial: 5 market-day files; availability verified) for the uncensored 16-22 Oct ladder, J at signing and cancel waves (X220 / X223 / W); (3) demos (X37 / X122); (4) the exam wallet list (0x7d67f01d, 0x52661b8e, 0x67119033, and now 0x10d79cc7).",
    "With Telonex files: label the wallet's levels (F_mkt), free vs clamped tops, the Tobit table fit of X223, cancel-wave lock of the dark V-changes (W), and J at t - 100 ms as a reported anchor.",
    "X225 clock-free: taker-regime sign moments per map against bo3 rounds / kills (as X226).",
    "X207: LoL twin on 0x10d79cc7 via Leaguepedia RiotGameId and Riot livestats (key-free).",
    "Keep v6 frozen; nothing in iteration 16 beat it on VALIDATE under its pre-registered rules.",
]


if __name__ == "__main__":
    main(int(sys.argv[1]), float(sys.argv[2]))
