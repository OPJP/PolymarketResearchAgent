"""Iteration 14: bring state.json up to date (catalog X125-X138 and closures, components, target_metrics, hypotheses, iteration entry)."""
import json, os, sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
B = _ROOT + "/research/reverse_engineering/btc5m-bot"
R = B + "/results"
s = json.load(open(f"{B}/state.json"))
L = lambda f: json.load(open(f"{R}/{f}"))
dc, ab, th, nfm, pr, kn, hz, lg = L("dcclock14.json"), L("ab14.json"), L("thin14.json"), L("nfms14.json"), L("pres14.json"), L("knee14.json"), L("hazard14.json"), L("legs14.json")
hf = L("hazflow14.json") if os.path.exists(f"{R}/hazflow14.json") else None
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 95.0

sp = dc["models"]["dc14_spot"]; fu = dc["models"]["dc14_full"]
cat = s["catalog"]
src = {"X125": "panel iteration 13, information P1 (re-clock the side on exchange time at the bot's information knee)",
       "X126": "panel iteration 13, information P2 (selection and hazard on the knee clock with a 30-ms label)",
       "X127": "panel iteration 13, information P3 (per-venue and per-trader knee map)",
       "X128": "panel iteration 13, information P4 (follower legs fired on the bot's own acknowledgements; dispatch route to condition 7)",
       "X129": "panel iteration 13, information P5 (audit the presence margin against a capture-aware market baseline)",
       "X130": "panel iteration 13, mechanics P1 (window-index A/B experiment schedule)",
       "X131": "panel iteration 13, mechanics P2 (early-segment millisecond exposure model for condition 5)",
       "X132": "panel iteration 13, mechanics P3 (the true size decision: original sizes at the decision clock with the capture's L2 book)",
       "X133": "panel iteration 13, mechanics P4 (the maker-role net as a lost-race remainder process replayed on the archive book)",
       "X134": "panel iteration 13, mechanics P5 (dispatch as a scheduled lottery: condition 7 for XM as a random-thinning limit)",
       "X135": "panel iteration 13, assumptions P1 (re-anchor the decision clock on Binance's own clock)",
       "X136": "panel iteration 13, assumptions P2 (re-open timing and selection on the full-rate spot book at the corrected clock)",
       "X137": "panel iteration 13, assumptions P3 (condition 5 from a millisecond nowcast of already-decided operator flow)",
       "X138": "panel iteration 13, assumptions P4 (condition 7 for XM as a formal random-thinning ceiling)"}
side_ev = (f"PRE-REGISTRATION 5 met (dcclock14.py, dcfit14.py, results/dcclock14.json): anchor X = m - 260 ms exchange time (book receive m - 129), "
           f"fit 10-17..19, scored once on 10-20..22: dc14_spot per order {sp['own']['all']} (DS {sp['own']['by_wallet']['DS']}, GF {sp['own']['by_wallet']['GF']}, XM {sp['own']['by_wallet']['XM']}), "
           f"per decision {sp['dec']['all']}, first legs {sp['own']['first_legs']}; by day {sp['own']['by_day']}; dc14_full {fu['own']['all']} / {fu['dec']['all']}; "
           f"placebo m -/+ 3 s {sp['plm']['all']} / {sp['plp']['all']}; old anchor {dc['old_anchor_frozen_route_same_orders']['all']}; market-only (capture Polymarket trades) "
           f"{dc['models']['market_only_pm']['own']['all']}; own-inventory {dc['own_inventory_baseline']['all']}; fit-day knee {dc['knee_fit_days']['fit_first_legs']['two_segment']}, "
           f"gain 260->200 {dc['knee_fit_days']['fit_first_legs']['gain_260_to_200']}; crowd control flat (gain 320->260 {dc['crowd_control_non_coarriving_buys']['all_days']['gain_320_to_260']}). "
           "Exam route code/dc_exam14.py (model_it14_dcside_spot.txt) wired into final_rule.evaluate(); end to end on 10-20 11-12 it reproduces the offline frame exactly (929 orders, 0.8364).")
new = {
    "X125": ("tried", side_ev),
    "X135": ("tried", "Same test as X125 (run once): " + side_ev),
    "X126": ("tried", f"Compact form (hazard14.py, results/hazard14.json; dc_hazard14.py exam route): 50-ms bins on the knee clock, label = operator first leg with m0 in [e+205, e+255), "
                      f"fit 10-17..19, scored once on 10-20..22: weighted AUC {hz['auc_full']} vs Polymarket-only {hz['auc_pm_only']} (gain {hz['gain_full_vs_pm_only']}, 2-h CI {hz['gain_block_ci95_300']}), "
                      f"spot-only {hz['auc_spot_only']}; per wallet {hz['by_wallet_first_legs']}; locked share at the knee band (knee14.json) {kn['locked_share_knee_band']['all']}. "
                      "The 30-ms label, the crowd co-take OR on the knee-clock design and the replica are in X136 (open)."),
    "X136": ("open", f"Partly tried: the hazard (X126: AUC {hz['auc_full']} vs {hz['auc_pm_only']}) and X111's locked share with spot BTC at the corrected clock "
                     f"(7.7% vs 1.2% placebo). Open: the reverse fit (day B -> day A), the crowd co-take log OR explained on the knee-clock design (X101), hawkes12's own-kernel increment."),
    "X127": ("open", f"Partly tried (knee14.py, results/knee14.json; on-disk venues, fit days, first legs): knees spot book 230 / spot trades 220 / USD-M BTC 220 / USD-M ETH 210 / OKX 200 ms; "
                     "Bybit BTC 100-ms bins keep rising past the arrival (a lagging copy). No venue adds information after the Binance knee. Open: Deribit / Coinbase / Kraken trade histories and the per-trader knees."),
    "X128": ("open", f"Partly tried (results/legs14.json): sequential followers (150-300 ms) score {lg['sequential_gap_150_300']['acc_own_anchor']} at their own anchor vs "
                     f"{lg['sequential_gap_150_300']['acc_first_leg_anchor']} at the first-leg anchor (re-decisions on fresher information); transitions fan-out DS->GF, sequential GF->DS. "
                     "Open: limits vs own-instant ask (calldata), P(follower | previous leg's fill outcome), the dispatch replay."),
    "X129": ("tried", f"pres14.py, results/pres14.json: on 10-20..22 block seconds the frozen full model {pr['auc_frozen_full']} vs a capture-aware market baseline (augmented baseline + others' "
                      f"server-ms prints on o / other outcome in 500-ms bins over [s-3.5, s-1)) {pr['auc_MSB']}: gain {pr['gain_frozen_full_vs_MSB']} (CI {pr['boot_frozen_full_vs_MSB']['lo95']}..{pr['boot_frozen_full_vs_MSB']['hi95']}), "
                      f"below 0.05; vs the same-split augmented baseline {pr['gain_frozen_full_vs_AUGR']}; FULLMS refit {pr['auc_FULLMS']} (+{pr['gain_FULLMS_vs_MSB']}). The block-second presence margin belongs to the block clock."),
    "X130": ("open", f"Step 1 tried (ab14.py, results/ab14.json, ab14_hours.csv): arm B = (start/300) mod 4 in {{1, 2}}; size phases (37 hours |t| >= 4) in BUILD and VALIDATE, B windows fill "
                     f"{ab['VALIDATE']['size_phase_in']['sh']} (A, B) shares per taker order inside them; LARGE shares from B on 10-16..19 {ab['LARGE_share_of_shares_from_B_by_day']}; one dispatch phase "
                     f"{ab['disp_phases']} (DS share A/B {ab['VALIDATE']['disp_phase_in']['ds']}). Open: arm-aware relabel and rerun of two13 / ls13 / side13, natural experiments per arm, exam-risk simulation."),
    "X131": ("tried", f"As nfms14 (pre-registration 6; results/nfms14.json): early-flow r [0,150) {nfm['early_flow_r_0_150']} (avg target 0.540), window-net r {nfm['window_net_r_10_20_22']}; "
                      f"tracker {nfm['tracker_trk_a_nfms14']['pool']} vs avg {nfm['tracker_trk_a_avg']['pool']}: not adopted. Signature-if-false holds (early-flow r <= 0.55)."),
    "X137": ("tried", f"Pre-registration 6 (nfms14) not adopted ({nfm['tracker_trk_a_nfms14']['pool']} vs {nfm['tracker_trk_a_avg']['pool']} on 10-20..22); pre-registration 7 (hazard nowcast) "
                      + (f"window-net r {hf['window_net_r_10_20_22']}, tracker mix14 {hf['tracker_trk_a_mix14']['pool']} vs avg {hf['tracker_trk_a_avg']['pool']}: adopted={hf['adopted_mix14']}." if hf else "not completed.")),
    "X132": ("open", "Not tested this iteration (original sizes at the decision clock with the capture L2 book; X130's arms must label the size first)."),
    "X133": ("open", "Not tested this iteration (maker-role remainder process replayed on the archive book)."),
    "X134": ("tried", f"thin14.py, results/thin14.json (10-20..22, 864 windows): P(wallet | public state) AUC {th['public']['auc_one_vs_rest']}; oracle with the TRUE decisions weighted by P^(XM): "
                      f"XM total PnL r {th['public']['oracle_xm_total_pnl_r']} (halves {th['public']['oracle_xm_total_pnl_r_halves']}); redraw corr with true XM PnL {th['public']['redraw_corr_with_true_xm_taker_pnl']}, "
                      f"redraw test-retest {th['public']['redraw_test_retest']}: condition 7 for XM is a random-thinning ceiling below 0.47. Step 3 (PRNG link, X105) open."),
    "X138": ("tried", "Same test as X134 (run once): " + f"oracle {th['public']['oracle_xm_total_pnl_r']}, sqrt test-retest ceiling {th['public']['redraw_test_retest']['sqrt_median_ceiling']} < 0.47."),
}
for k, (st, ev) in new.items():
    cat[k] = {"status": st, "source": src[k], "evidence": ev}
cat["X113"]["evidence"] += (" Iteration 14: step 6 rebuilt at the corrected clock (dc_exam14, pre-registration 5: 83.7% per order); the decision-level replica (step 5) is open "
                            "(the hazard nowcast of pre-registration 7 is its first form).")
cat["X111"]["status"] = "tried"
cat["X111"]["evidence"] += (" Iteration 14 (step 3, knee14.json): at the corrected clock with spot BTC included, a microprice net move toward o >= 0.1 bp in the knee band precedes 7.7% "
                            "of first legs (placebo 1.2%); the unlocked majority follows sub-tick spot microprice (queue imbalance) moves, which carry the 83% side.")
s["catalog"] = cat
open_ids = sorted([k for k, v in cat.items() if v.get("status") == "open"], key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))
s["catalog_open_after_iteration14"] = open_ids

comp = s["components"]
comp["side"] = {"confidence": 0.85, "tag": "VALIDATE-only",
                "description": ("Per decision: the direction of the Binance SPOT top-of-book microprice (mostly sub-tick queue-imbalance moves) over the ~250 ms ending ~230-260 ms "
                                "before the match on Binance's own clock (the bot reads Binance ~80-110 ms after the stamp and arrives 150 ms before its match). Pre-registered "
                                f"(pre-registration 5), fitted on 10-17..19 and scored once on 10-20..22: {sp['own']['all']} per taker order (DS {sp['own']['by_wallet']['DS']}, GF {sp['own']['by_wallet']['GF']}, "
                                f"XM {sp['own']['by_wallet']['XM']}), {sp['dec']['all']} per decision, 88 / 87 / 84 / 78 / 69% by window minute; market-only 0.568, own-inventory 0.539, "
                                "placebo 0.50, old anchor 0.742; the information arrives in a 60-ms band and nothing is added after it; no knee for the non-co-arriving crowd. "
                                "Exam route dc_exam14 (capture day files). Late decisions (after 180 s) mix weaker tick-following and own-state pairing.")}
comp["timing"] = {"confidence": 0.8, "tag": "VALIDATE-only",
                  "description": ("Decision = submission of a pre-signed ladder order ~150 ms before its match, on the Binance spot book read ~80-110 ms after the stamp (knee at 230-260 ms "
                                  f"before the match on exchange time). At that clock the take is largely decoded: a 50-ms hazard reaches AUC {hz['auc_full']} vs {hz['auc_pm_only']} for "
                                  f"Polymarket activity (per wallet DS {hz['by_wallet_first_legs']['DS']['full']}, GF {hz['by_wallet_first_legs']['GF']['full']}, XM {hz['by_wallet_first_legs']['XM']['full']}); "
                                  "top inputs the 100 / 250-ms spot microprice return toward o and |p - 0.5|. Only ~8% of decisions follow a price-level tick (placebo 1.2%); the rest follow "
                                  "sub-tick queue-imbalance moves. Follower legs 180-220 ms later are re-decisions on fresher spot (86% at their own anchor vs 79%). An operator-level "
                                  "30-60-s activity state remains (iteration 12). Block-second presence 0.870 vs a capture-aware market baseline 0.846 (+0.024): at the block clock the "
                                  "crowd's co-arrivals reveal most of the operator's takes.")}
comp["selection"] = {"confidence": 0.85, "tag": "VALIDATE-only",
                     "description": "Every BTC 5m Up/Down window (94-99% traded), nothing else; prices in the ladder range ~0.12-0.88; whole-cluster outages are bot-side."}
comp["size"] = {"confidence": 0.7, "tag": "VALIDATE-only",
                "description": ("Configuration plus own state, not an input response: the operator runs window-index A/B arms (arm B = (start/300) mod 4 in {1, 2}); in size phases "
                                "(37 development hours, BUILD and VALIDATE, boundaries at restarts) B windows carry the larger base size (33.9 vs 24.6 filled shares per taker order; "
                                "76-84% of the >= 45-share shares on 10-16..19 come from B windows). Large orders pyramid the operator's held leg (own state); the immediate spot move "
                                "does not set the size (AUC ~0.6 at the corrected clock). The window PnL is the lean's size: the public share of the window net stays ~0.5 even at ms.")}
comp["exit"]["description"] += (" Iteration 14: a millisecond nowcast (nfms14) and a decision-hazard nowcast do not lift the tracker (pre-registrations 6 / 7); XM's PnL is a random "
                                 f"thinning of the operator's decisions (oracle {th['public']['oracle_xm_total_pnl_r']}, redraw ceiling {th['public']['redraw_test_retest']['sqrt_median_ceiling']} < 0.47).")
comp["price"]["description"] += " Iteration 14: unchanged (within a tick of the touch the bot saw 95.1%); the dispatch-phase arm does not change the price level."
s["components"] = comp

tm = s["target_metrics"]
tm_old = dict(tm)
tm.update({"presence_auc": pr["auc_frozen_full"], "presence_baseline": pr["auc_MSB"], "side_accuracy": sp["own"]["all"],
           "side_baseline": dc["models"]["market_only_pm"]["own"]["all"]})
s["target_metrics"] = tm
s["target_metrics_notes"]["iteration14"] = (
    f"presence_auc / presence_baseline now compare the frozen block-second model with the STRONGER, capture-aware market baseline (pres14: VALIDATE 10-20..22 block seconds, "
    f"{pr['auc_frozen_full']} vs {pr['auc_MSB']}, gain {pr['gain_frozen_full_vs_MSB']}, CI [{pr['boot_frozen_full_vs_MSB']['lo95']}, {pr['boot_frozen_full_vs_MSB']['hi95']}]: condition 2 FAILS); "
    f"over all VALIDATE against the block-clock baseline it was 0.8747 / 0.8211. Decision-clock hazard (dc_hazard14, VALIDATE-only, not pre-registered as the target metric, "
    f"taker first legs only): {hz['auc_full']} vs {hz['auc_pm_only']}. side_accuracy = decision-clock per taker order (pre-registration 5, dc_exam14), {sp['own']['all']} on 10-20..22; "
    f"per decision {sp['dec']['all']}; side_baseline = market-only from the capture's Polymarket trades on the same orders; block-clock side 0.7666 (baseline 0.6323) kept apart. "
    "XM is the only wallet the side condition applies to (one-sided in 24.9% of its windows): one-sided windows 84.3% (halves 91.1 / 76.8%), per order halves 84.7 / 78.6%. "
    f"pnl_corr unchanged (all VALIDATE 0.4758 / 0.4404; on 10-20..22 {nfm['tracker_trk_a_avg']['pool']}); per wallet XM 0.06 vs a random-thinning ceiling of "
    f"{th['public']['redraw_test_retest']['sqrt_median_ceiling']} (condition 7 unattainable for XM).")
s["best"] = {"rule_id": "it14: presence rule unchanged since iteration 8 (block seconds); side = decision-clock dc14_spot (dc_exam14, pre-registration 5); price unchanged; PnL = exposure tracker trk_a_avg",
             "validate_metrics": dict(s["best"]["validate_metrics"], **{"presence_auc_10_20_22": pr["auc_frozen_full"], "presence_capture_aware_baseline_10_20_22": pr["auc_MSB"],
                                                                       "presence_gain_vs_capture_aware": pr["gain_frozen_full_vs_MSB"], "side_accuracy_decision_clock": sp["own"]["all"],
                                                                       "side_accuracy_per_decision": sp["dec"]["all"], "side_by_wallet": sp["own"]["by_wallet"],
                                                                       "presence_decision_clock": {"auc": hz["auc_full"], "baseline_pm_only": hz["auc_pm_only"], "by_wallet": hz["by_wallet_first_legs"]},
                                                                       "side_accuracy_block_clock": 0.7666})}
H_ = s["hypotheses"]; n0 = len(H_)
add = [
    ("decision clock on exchange time (pre-registration 5)", "dc14_spot: spot book + trades cut at m - 260 ms exchange time, fit 10-17..19, scored once 10-20..22",
     {"per_order": sp["own"]["all"], "per_decision": sp["dec"]["all"], "by_wallet": sp["own"]["by_wallet"], "placebo": [sp["plm"]["all"], sp["plp"]["all"]], "old_anchor": dc["old_anchor_frozen_route_same_orders"]["all"]},
     "MET (>= 80% per order and per decision, DS >= 77%); adopted as the exam route and target_metrics.side_accuracy"),
    ("decision clock, full venue set", "dc14_full: + USD-M BTC / ETH, OKX, Bybit at the same exchange cut", {"per_order": fu["own"]["all"], "per_decision": fu["dec"]["all"]}, "reported, not exam-routed"),
    ("window-index A/B arms (X130)", "arm B = (start/300) mod 4 in {1,2}; per-hour Welch t", {"size_phase_hours": ab["size_phase_hours"], "disp_phases": ab["disp_phases"]}, "confirmed: size and dispatch are scheduled configuration"),
    ("random-thinning dispatch ceiling (X134 = X138)", "true decisions allocated by P^(wallet | public state); 2,000 redraws",
     {"oracle_xm_total_pnl_r": th["public"]["oracle_xm_total_pnl_r"], "redraw_test_retest": th["public"]["redraw_test_retest"]}, "condition 7 for XM unattainable (< 0.47)"),
    ("millisecond net-flow nowcast (pre-registration 6)", "nfms14 stacked on nf / nf12b with capture spot and Polymarket ms features", {"window_net_r": nfm["window_net_r_10_20_22"], "tracker": nfm["tracker_trk_a_nfms14"]["pool"], "avg": nfm["tracker_trk_a_avg"]["pool"]}, "not adopted"),
    ("capture-aware presence baseline (X129)", "augmented baseline + others' server-ms prints", {"full": pr["auc_frozen_full"], "MSB": pr["auc_MSB"], "gain": pr["gain_frozen_full_vs_MSB"]}, "presence margin fails (+0.024 < 0.05)"),
    ("knee-clock take hazard (X126)", "50-ms bins, label first leg at m0 - [205, 255) ms", {"auc": hz["auc_full"], "pm_only": hz["auc_pm_only"], "by_wallet": hz["by_wallet_first_legs"]}, "selection decoded at the decision clock (VALIDATE-only, taker first legs)"),
    ("per-venue knee map (X127)", "univariate, fit days", {v: kn["venues"][v]["fit_days"]["two_segment_full"] for v in kn["venues"]}, "no venue after the Binance knee"),
]
if hf:
    add.append(("decision-hazard nowcast tracker (pre-registration 7)", "mix14 = 0.5 avg + 0.5 c x hazard imbalance",
                {"window_net_r": hf["window_net_r_10_20_22"], "mix14": hf["tracker_trk_a_mix14"]["pool"], "nfhaz": hf["tracker_trk_a_nfhaz"]["pool"], "avg": hf["tracker_trk_a_avg"]["pool"]},
                "adopted" if hf["adopted_mix14"] else "not adopted"))
for i, (fam, d, m, v) in enumerate(add):
    H_.append({"id": f"H{178 + i}", "family": fam, "description": d, "validate_metrics": m, "verdict": v})
s["hypotheses"] = H_
s["status"] = "continue"; s["wall_reason"] = None
s["strategy_statement"] = (
    "One operator runs a TypeScript clob-client bot on three (plus a fourth and a fifth) wallets in every BTC 5-minute Up/Down window, and only there [VALIDATE-only]. "
    "It pre-signs BUY orders on both outcomes at every cent in bursts each window [VALIDATE-only]. It sits next to Polymarket's engine and reads the Binance SPOT book "
    "~80-110 ms after Binance stamps it; when the spot microprice (mostly sub-tick queue-imbalance moves) shifts toward an outcome over the last ~100-250 ms against the "
    f"Polymarket price, it submits the pre-signed order at the ask it saw ~30 ms before arriving; the take hazard on that clock reaches AUC {hz['auc_full']} against "
    f"{hz['auc_pm_only']} for Polymarket activity [VALIDATE-only] and the side is {sp['own']['all']} per taker order on the pre-registered split [VALIDATE-only]. "
    "Polymarket holds every marketable order 150 ms, so it races the fast crowd in that delay queue; followers ~200 ms later are fresh re-decisions [VALIDATE-only]. "
    "Lost races rest at the old ask and fill as maker about half the time [VALIDATE-only]. Order sizes are scheduled configuration (window-index A/B arms with a larger base "
    "size in B windows during size phases) plus pyramiding of the held leg (own state) [VALIDATE-only]. Positions are held to resolution; most shares end paired; about "
    "half the profit is the taker-fee rebate [VALIDATE-only]. The window PnL is the size of the lean, which public data predicts at r ~0.5 even at millisecond resolution "
    "(exposure tracker 0.476 / 0.440 [VALIDATE-only]); which wallet carries a decision is a near-random thinning (XM's PnL ceiling < 0.47 for any rule) [VALIDATE-only]. "
    "At the block clock the presence gain over a capture-aware market baseline is only +0.024 [VALIDATE-only]. Nothing is exam-verified yet.")
s["iterations"].append({"n": 14, "minutes": MINUTES, "best_validate_score": 0.9132, "block_seconds_presence": pr["auc_frozen_full"], "block_seconds_stronger_baseline": pr["auc_MSB"],
                        "side_accuracy": sp["own"]["all"], "pnl_corr": 0.4758, "pnl_corr_spearman": 0.4404,
                        "paradigm": "The decision clock on Binance's own clock (the knee 230-260 ms before the match): side and take decoded at the decision instant; configuration (A/B arms) and random-thinning dispatch as the account of size and condition 7; capture-aware baselines",
                        "families": ["re-clocked decision-clock side, pre-registration 5 (X125 = X135)", "window-index A/B arms (X130 step 1)", "random-thinning dispatch ceiling (X134 = X138)",
                                     "millisecond net-flow nowcast, pre-registration 6 (X131 / X137)", "capture-aware presence baseline (X129)", "per-venue knee map (X127 partial)",
                                     "locked share at the corrected clock (X111 step 3 / X136 partial)", "knee-clock take hazard and its exam route (X126)", "follower legs as re-decisions (X128 partial)",
                                     "decision-hazard nowcast tracker, pre-registration 7 (X113 step 5 / X137)"]})
s["frozen_rule"] = ("code/final_rule.py (iteration 14: + dc_exam14 decision-clock side = target_metrics.side_accuracy, + dc_hazard14 decision-clock presence (reported); presence, price "
                    "and the PnL tracker unchanged)")
json.dump(s, open(f"{B}/state.json", "w"), indent=1)
print("open", len(open_ids), open_ids)
print(json.dumps(s["target_metrics"]))
