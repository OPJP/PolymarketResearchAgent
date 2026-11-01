"""Iteration 13: update state.json (catalog X113-X124 from the iteration-12 panel, X84 closed, components, strategy statement,
hypotheses, data_sources, iterations). target_metrics are unchanged (no candidate was adopted this iteration).
Usage: python update_state_iter13.py MINUTES"""
import os, json, shutil, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
P = os.environ.get("STATE_PATH") or (_ROOT + "/research/reverse_engineering/btc5m-bot/state.json")
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
(None if os.environ.get("STATE_PATH") else shutil.copy(P, _ROOT + "/.cache/re/btc5m-bot/state_backup_iter12.json"))
s = json.load(open(P, encoding="utf-8"))
MIN = float(sys.argv[1]) if len(sys.argv) > 1 else None


def J(name):
    p = f"{R}/{name}"
    return json.load(open(p)) if os.path.exists(p) else None


two, ls, tr, sd, sdp = J("two13.json"), J("ls13.json"), J("track13.json"), J("side13.json"), J("side13_ps.json")
dcf, dcs, dco, late, opn = J("dcfeat13_2026-10-20.json"), J("dcside13_2021.json"), J("dcown13_2021.json"), J("late13_2021.json"), J("open13_2021.json")
bas, iv, ivs, dcp, dsp, shr = J("basis13.json"), J("iv13.json"), J("iv13_split.json"), J("dcprice13.json"), J("dispatch13_2021.json"), J("share13.json")
dc13, dcfull = J("dc13_2026-10-20.json"), J("dcside13.json")
cat = s["catalog"]
I12 = "panel iteration 12"
SP = "session scratchpad it13/ (hfprobe13.py, hfingest13.py)"
oc = (two or {}).get("oracle_ceilings_validate", {})

cat["X113"] = {"status": "open", "source": f"{I12}, information P1 (public historical Polymarket capture Fahri-5/updown-5m-polymarket-raw as the decision clock and book for VALIDATE and h1)",
               "evidence": "Steps 1-4 tried on development days (NOTES iteration 13 findings 5-6; " + SP + "; code/dc13.py, dcfeat13.py, dcside13.py, dcown13.py, dcprice13.py). "
                           "Dataset CC0, not gated, revision pinned f848a77ccfce4421d3cedbbe585576db77d36662; only day names < H kept from the listing. 10-20: 97.3% of the operator's "
                           "39,899 txs carry an archive match ms (99.1-100% in hours 0-22; the day file ends 23:00), block - match q05/q50/q95 1,247 / 2,202 / 3,138 ms. "
                           "Decision-clock side (a = m - 180 ms), fit 10-20 -> score 10-21 and the reverse (a disclosed deviation from the pre-registered 10-17..19 fit): full coverage "
                           f"per taker order {((dcs or {}).get('fit_A_score_B') or {}).get('full', {}).get('acc')} / {((dcs or {}).get('fit_B_score_A') or {}).get('full', {}).get('acc')} "
                           "(GF 0.81-0.82, XM 0.80-0.85, DS 0.75), venue-only 0.761 / 0.763, Polymarket-state-only 0.588 / 0.586, + own-state pairing kernel 0.776 / 0.774; top input the "
                           "Binance spot book microprice over the last 250 / 100 ms; 81-83% in minutes 0-2, 62-72% after 180 s. The frozen live vote windows with the archive's two Binance "
                           "series agree only 0.657 on 57% (frozen) / 0.559 on 52% (PIT): the live 83% needs USD-M bookTicker + ETH series the archive lacks. Price: the taker limit is "
                           f"within a tick of o's archive ask at the arrival for {((dcp or {}).get('ask_0') or {}).get('within_tick')} of {((dcp or {}).get('ask_0') or {}).get('n')} "
                           f"calldata orders (exact {((dcp or {}).get('ask_0') or {}).get('exact')}; at a - 30 ms {((dcp or {}).get('ask_30') or {}).get('within_tick')}; touch at the match "
                           f"{((dcp or {}).get('ask_m') or {}).get('within_tick')}; XM {((dcp or {}).get('by_wallet_ask_30') or {}).get('XM')}). The pre-registered split (fit 10-17..19, "
                           "score 10-20..22), the decision-level replica (step 5) and the exam route through evaluate() (step 6) are open."}
pay, dcx = J("payrank13.json"), J("dcside13_2021x.json")
if dcfull:
    _a, _b = dcfull.get("fit_A_score_B") or {}, dcfull.get("fit_B_score_A") or {}
    cat["X113"]["evidence"] += (f" PRE-REGISTERED split (pre-registration 3; fit {dcfull.get('fit_days')} -> score the rest of {dcfull.get('days')}; Polymarket touch only on "
                                f"10-20 / 10-21, NaN elsewhere): full {(_a.get('full') or {}).get('acc')} (by wallet {(_a.get('full') or {}).get('by_wallet')}), venue-only "
                                f"{(_a.get('venue_only') or {}).get('acc')}, market-only {(_a.get('market_only') or {}).get('acc')}; reverse {(_b.get('full') or {}).get('acc')}. "
                                f"Success (>= 0.80) {'met' if ((_a.get('full') or {}).get('acc') or 0) >= 0.80 else 'NOT met'}.")
if pay:
    cat["X113"]["evidence"] += (f" Per-wallet pay-up (payrank13): limit - ask premium rises with the leg rank (mean {json.dumps(pay.get('mean_premium_by_rank'))} c by rank); "
                                f"anchor ask + c_w (DS 0, GF 1 c, XM 1 c) within a tick {json.dumps(pay.get('within_tick_ask_plus_cw'))} vs plain ask {json.dumps(pay.get('within_tick_ask'))}.")
rab, dlg = J("rabbit13.json"), J("dclegs13.json")
if dlg:
    cat["X113"]["evidence"] += (" Per DECISION (first legs of fan-out events) the decision-clock side is "
                                f"{[v.get('events_acc_first_leg') for v in dlg.values()]} (follower legs 80-87%: they see more of the move).")
if rab:
    cat["X113"]["evidence"] += (" The missing USD-M bookTicker (RabbitGo777 10-20 capture, revision 1e0218e1, 11:00-12:00 UTC, 926 orders) does not close the gap: "
                                f"USD-M 250 ms {rab.get('usdm_250')} vs spot {rab.get('spot_250_same_orders')} [agree, cover]; decision-clock model {rab.get('dc_model_same_orders')}, "
                                f"with the USD-M tick first {rab.get('usdm250_vote_then_model')}.")
dsp_, dwin = J("dcside13_spot.json"), J("dcwin13.json")
if dsp_:
    cat["X113"]["evidence"] += (f" Pre-registration 4 (exam route, spot-book-only model fitted on 10-17..19): 10-20..22 per order {dsp_.get('per_order')} "
                                f"(by wallet {dsp_.get('by_wallet')}), XM one-sided windows {dsp_.get('XM_one_sided_window_acc')} (by day {dsp_.get('XM_one_sided_by_day')}); "
                                "built into final_rule.evaluate() as 'side_decision_clock' (code/dc_exam13.py), reproducing the offline frame exactly on 10-20 11:00-12:00 "
                                "(929 orders, 0.7104). Step 6 is done for the spot route; the full-venue route and the decision-level replica (step 5) remain.")
if dwin:
    cat["X113"]["evidence"] += (f" Full venue model (model_it13_dcside_A.txt): XM one-sided windows {dwin.get('XM_one_sided_window_side_acc')} of {dwin.get('XM_one_sided_windows_by_taker_orders')} "
                                f"(share {dwin.get('XM_one_sided_share')}), XM per order {((dwin.get('per_order_by_wallet_halves') or {}).get('XM') or {}).get('all')}.")
cat["X114"] = {"status": "open", "source": f"{I12}, information P2 (Polymarket touch-queue fade: size-only maker requotes as the trigger of the quiet decisions)",
               "evidence": "Not tested in iteration 13 (the quiet-instant event unit on 10-31 A / C and its 11-01 replication). Note for the test: book state counts as market activity "
                           "for the examiner's baseline, so it cannot raise the presence gain over a market-activity baseline. Open."}
cat["X115"] = {"status": "open", "source": f"{I12}, information P3 (crowd co-arrival instants as the event clock: kernel search feed by feed)",
               "evidence": "Not tested in iteration 13 (needs the 11-01 06-12 / 18-24 recordings for the new feeds). Open."}
b1 = ((bas or {}).get("ols") or {})
cat["X116"] = {"status": "tried", "source": f"{I12}, information P4 (settlement-feed basis Chainlink RTDS vs Binance as the slow input of the window net path)",
               "evidence": "Pre-registered (NOTES iteration 13, pre-registration 2) and run on VALIDATE (code/basis13.py, results/basis13.json; RTDS Chainlink btc/usd from the HF capture, "
                           f"6 days, {(bas or {}).get('windows_with_basis')} windows): the basis is {(bas or {}).get('basis_usd_q')} USD (q05..q95; the USDT premium); basis terms vs the "
                           f"residual of the window net |r| <= 0.045; OLS fit 10-17..19 -> 10-20..22 gain {(b1.get('fit_17_19_score_20_22') or {}).get('gain')}, reverse "
                           f"{(b1.get('fit_20_22_score_17_19') or {}).get('gain')} (threshold +0.03). E5 not supported. The RabbitGo777 constituent and August Data Streams steps were not run "
                           "after the main test failed."}
cat["X117"] = {"status": "tried", "source": f"{I12}, information P5 (short-dated implied vol as the scale of the buy-back)",
               "evidence": "Deribit DVOL 1-min (public get_volatility_index_data, resolution 60, 10-09..22, end < H; 20,190 minutes; code/iv13.py, results/iv13.json, iv13_split.json). "
                           f"Window-minute panel: earlier-move x log(DVOL / RV15) BUILD {((iv or {}).get('BUILD') or {}).get('coef', {}).get('E_z')} (t {((iv or {}).get('BUILD') or {}).get('t', {}).get('E_z')}), "
                           f"VALIDATE {((iv or {}).get('VALIDATE') or {}).get('coef', {}).get('E_z')} (t {((iv or {}).get('VALIDATE') or {}).get('t', {}).get('E_z')}): replicated, but split into "
                           f"log RV15 and log DVOL the interaction is realized vol (E x log RV {json.dumps((ivs or {}).get('BUILD', {}).get('E_rv'))} / {json.dumps((ivs or {}).get('VALIDATE', {}).get('E_rv'))}, "
                           f"[coef, t]) and DVOL's own term is insignificant ({json.dumps((ivs or {}).get('BUILD', {}).get('E_dv'))} / {json.dumps((ivs or {}).get('VALIDATE', {}).get('E_dv'))}). "
                           "The buy-back scales with recent realized vol (sigma-unit moves), which the nf features already carry; the implied-vol fair value (E4) is not supported, so no nf candidate "
                           "was pre-registered (step 3)."}
mech = (sdp or {}).get("mechanism_offset_logit", {})
cat["X118"] = {"status": "tried", "source": f"{I12}, mechanics P1 (two-leg inventory policy: large directional fills plus operator-level complement pairing by the small orders)",
               "evidence": "Step 1 (code/side13.py, results/side13_ps.json; VALIDATE one-sided seconds, offset = the frozen side model, window-clustered): on small-order seconds the "
                           f"realized operator LARGE net over [s - 180, s - 2] (60-s decay) has coef {mech.get('small', {}).get('coef', {}).get('KL')} (t {mech.get('small', {}).get('t', {}).get('KL')}), "
                           f"the small-order placebo {mech.get('small', {}).get('coef', {}).get('KS')} (t {mech.get('small', {}).get('t', {}).get('KS')}), the crowd's 120-s flow "
                           f"{mech.get('small', {}).get('coef', {}).get('CR')} (t {mech.get('small', {}).get('t', {}).get('CR')}); on large-order seconds {mech.get('large', {}).get('coef', {}).get('KL')} "
                           f"(t {mech.get('large', {}).get('t', {}).get('KL')}): small orders pair the realized large inventory, large orders pyramid. Step 2 (pre-registered tilt, cross-fit on "
                           f"VALIDATE halves): {((sdp or {}).get('tilt_cross_fit') or {}).get('pooled_cross_fit')} (success >= 0.78 not met); at the decision clock + 0.1-0.4 points "
                           "(dcown13). Step 3 = X121's two-stream tracker (not adopted). Step 4 (decision replica on recorded books) not run. Tried: the mechanism is real own-state "
                           "feedback; it does not close the side gap."}
cat["X119"] = {"status": "open", "source": f"{I12}, mechanics P2 (the selection shared with the crowd as a pre-onset Polymarket repricing state: the maker requote cascade)",
               "evidence": "Not tested in iteration 13. Open."}
cat["X120"] = {"status": "tried", "source": f"{I12}, mechanics P3 (per-wallet allocation of the two legs: sticky dispatcher plus per-wallet menus, the route to condition 7)",
               "evidence": "Steps 1-3 (code/two13.py, track13.py, results/two13.json, track13.json): BUILD per-window loadings of each wallet's net on the pooled L / S nets "
                           f"{json.dumps((tr or {}).get('loadings_BUILD'))}; per-wallet trackers with those loadings on the public L13 / S13 predictions: GF "
                           f"{((tr or {}).get('trk_w_GF') or {}).get('pnl_corr_GF')}, XM {((tr or {}).get('trk_w_XM') or {}).get('pnl_corr_XM')}, DS {((tr or {}).get('trk_w_DS') or {}).get('pnl_corr_DS')} "
                           "(all below the pooled tracker). Thinning ceilings (TRUE pooled legs, BUILD loadings): GF "
                           f"{oc.get('GF', {}).get('aL_bS_pool_BUILDload')}, DS {oc.get('DS', {}).get('aL_bS_pool_BUILDload')}, XM {oc.get('XM', {}).get('aL_bS_pool_BUILDload')}; from the "
                           f"other wallets' legs only GF {oc.get('GF', {}).get('aL_bS_others_BUILDload')}, DS {oc.get('DS', {}).get('aL_bS_others_BUILDload')}, XM "
                           f"{oc.get('XM', {}).get('aL_bS_others_BUILDload')}; with the TRUE per-window gross share x the perfect pooled net XM {((shr or {}).get('XM') or {}).get('oracle_true_share_x_pooledN')}. "
                           "Step 5 on the archive decision clock (dispatch13): the carrying wallet is barely predictable from public state (accuracy "
                           f"{((dsp or {}).get('fit_2026-10-20') or {}).get('acc')} vs base {((dsp or {}).get('fit_2026-10-20') or {}).get('acc_base')}); in fan-out events the legs go DS first "
                           f"({((dsp or {}).get('first_leg_share_multi') or {}).get('DS')}), GF second, then DS / GF / XM. Step 4 (version transfer of the loadings) not run."}
cat["X121"] = {"status": "tried", "source": f"{I12}, assumptions P1 (two-stream exposure target: large-order lean L and small-order counter-flow S)",
               "evidence": "Pre-registered (NOTES iteration 13, 02:17 UTC) and scored once (code/ls13.py, track13.py; results/ls13.json, track13.json): window r L13 vs L "
                           f"{((ls or {}).get('validate_window') or {}).get('L13_vs_L')} (nf12b {((ls or {}).get('validate_window') or {}).get('nf12b_vs_L')}), S13 vs S "
                           f"{((ls or {}).get('validate_window') or {}).get('S13_vs_S')}, L13 + S13 vs N {((ls or {}).get('validate_window') or {}).get('LS_vs_N')} (nf12b "
                           f"{((ls or {}).get('validate_window') or {}).get('nf12b_vs_N')}; corr with nf12b {((ls or {}).get('validate_window') or {}).get('corr_LS_nf12b')}); the window-state "
                           f"features carry {json.dumps((ls or {}).get('w13_share'))} of the gain. Primary candidate trk_a_2s {((tr or {}).get('trk_a_2s') or {}).get('pnl_corr_pool')} vs "
                           f"trk_a_avg {((tr or {}).get('trk_a_avg_check') or {}).get('pnl_corr_pool')}: NOT adopted. The panel's 'signature if false' holds: the public share of the window "
                           "net is bounded by the public share of L."}
cat["X122"] = {"status": "open", "source": f"{I12}, assumptions P2 (condition 7 as a dispatch problem with version-specific roles; per-wallet attainability ledger)",
               "evidence": "Step 3 (attainability ledger) done (two13.json, share13.json): per-wallet PnL r under (i) the pooled T oracle GF "
                           f"{oc.get('GF', {}).get('T_pool')}, DS {oc.get('DS', {}).get('T_pool')}, XM {oc.get('XM', {}).get('T_pool')}; (ii) pooled L + S with BUILD mixes GF "
                           f"{oc.get('GF', {}).get('aL_bS_pool_BUILDload')}, DS {oc.get('DS', {}).get('aL_bS_pool_BUILDload')}, XM {oc.get('XM', {}).get('aL_bS_pool_BUILDload')}; (iii) the "
                           f"TRUE per-window share x pooled net GF {((shr or {}).get('GF') or {}).get('oracle_true_share_x_pooledN')}, DS {((shr or {}).get('DS') or {}).get('oracle_true_share_x_pooledN')}, "
                           f"XM {((shr or {}).get('XM') or {}).get('oracle_true_share_x_pooledN')}: XM stays below 0.47 under every pooled-stream oracle. Step 2 partly (dispatch13 on the "
                           "archive clock: the wallet is barely predictable from public state; DS-first / GF-second leg order). Steps 1 (role table per version), 4 and (iv) the W4 / W5 "
                           "test-retest are open."}
cat["X123"] = {"status": "open", "source": f"{I12}, assumptions P3 (the ~25 independent fresh-signing co-taker bots: their signing ms as exact decision clocks)",
               "evidence": "Not tested in iteration 13. Open."}
cat["X124"] = {"status": "open", "source": f"{I12}, assumptions P4 (the window open as its own decision type: the opening snipe seeds the lean)",
               "evidence": "Step 1 run on the public archive instead of the live lab (code/open13.py, results/open13_2021.json; 10-20 / 10-21 taker orders): decisions in [0, 15) s "
                           f"follow the spot tick {((opn or {}).get('tick_bs_mic_250') or {}).get('0-15')} (after 30 s {((opn or {}).get('tick_bs_mic_250') or {}).get('30-300')}); the "
                           f"exact-strike value side {((opn or {}).get('value_exact_strike') or {}).get('0-15')} (anti-value: the bot's FV is wider than an RV digital), favourite "
                           f"{((opn or {}).get('fav_exact_strike') or {}).get('0-15')}; P(large) {json.dumps((opn or {}).get('p_large'))} (1.4x, not 2x). The signature is not met. Step 2 "
                           "(BUILD side model of each window's first fills vs sign(netLarge)) is open; X121's window-state features (first k-bp move) carried 2% of L13's gain."}
if "X84" in cat:
    cat["X84"]["status"] = "tried"
    cat["X84"]["evidence"] = cat["X84"].get("evidence", "") + (" | Iteration 13 (X121): large and small as two BUILD-fitted per-second streams with window-level initiation features "
                                                              "(first k-bp move after the open, move counts) on the weekday VALIDATE week: L13 vs the window L r 0.324 (nf12b 0.309), "
                                                              "initiation features 2.0-2.3% of the gain, the two-stream tracker not adopted; the open is not a distinct side regime "
                                                              "(X124 step 1). Tried.")

_sup = (" | Iteration 13: SUPERSEDED by X113: the public HF capture (Fahri-5/updown-5m-polymarket-raw, revision f848a77c) gives the operator's "
        "server-ms match time directly for 97.3% of its txs on 10-20 (99.1-100% in hours 0-22; block - match q05 / q50 / q95 1,247 / 2,202 / 3,138 ms) and lists "
        "day files for every development and exam day; an anchor-interpolated clock is no longer needed. Tried (the historical decision clock exists).")
for _k in ("X59", "X89", "X108"):
    if _k in cat and cat[_k].get("status") == "open":
        cat[_k]["status"] = "tried"; cat[_k]["evidence"] = cat[_k].get("evidence", "") + _sup
comp = s["components"]
comp["side"]["confidence"] = 0.62
comp["side"]["description"] = ("Per decision: the direction of the fast venues' microprice over the last ~100-250 ms before the decision. Live (10-31) the six-series vote "
                               "[m - 650, m - 180) 83.3% on 67.6% voted. Iteration 13, HISTORICAL decision clock (public HF capture, VALIDATE weekdays 10-20 / 10-21, fit one day, "
                               "score the other): full coverage per taker order 77.2-77.3% (GF 81-82%, XM 80-85%, DS 75%), Binance spot microprice 250 / 100 ms the top inputs, "
                               "81-83% in minutes 0-2 and 62-72% after 180 s (late decisions mix weak tick-following and pairing of the operator's realized inventory). At the block "
                               "clock 76.7% per one-sided second (72.7% per taker order); part of the block clock's accuracy is post-decision continuation (its inputs end a median "
                               "~0.2 s after the match). Small orders buy the complement of the operator's realized LARGE inventory (t -26.5, placebo opposite, crowd null) and large "
                               "orders pyramid, but this own-state tilt adds < 0.5 point. No settlement-TWAP lock-in late (52%). No wallet is one-sided beyond its order-count null "
                               "pooled; XM is one-sided in 24% of its windows.")
comp["side"]["description"] += (" Iteration 13 exam route: final_rule.evaluate() reports 'side_decision_clock' (spot-book-only frozen model on the public "
                                 "capture; 74.2% per order on 10-20..22, XM one-sided windows 81.4%; the full venue model 76.3% / 84.3%). XM is the only "
                                 "wallet the side condition applies to (one-sided in 24.9% of its windows).")
comp["price"]["description"] = comp["price"]["description"] + (" Iteration 13: at the decision clock on VALIDATE (public capture, 2,476 calldata taker orders on 10-20 / 10-21) the limit "
                                                               "is within a tick of o's archive ask at the arrival for 93.4% (exact 74.3%), at arrival - 30 ms 92.7%, vs 81.3% for the "
                                                               "touch at the match itself; XM 66%.")
comp["exit"]["description"] = comp["exit"]["description"] + (" Iteration 13: the inventory path is two operator-level streams, a large-size lean (cross-wallet r 0.35-0.47) and a small-size "
                                                             "taker counter-flow that buys back the REALIZED large inventory (within-wallet corr(L, S) -0.26..-0.60; dose-dependent "
                                                             "pairing, t -26.5); public data predicts L at r 0.32 and the counter-flow residual at ~0.3, and a two-stream target adds "
                                                             "nothing to the window-net prediction (0.4195 vs 0.4237). Per-wallet PnL is bounded by dispatch: XM <= 0.30-0.41 under "
                                                             "every pooled-stream oracle.")
comp["timing"]["description"] = comp["timing"]["description"] + (" Iteration 13: the decision instant is now observable on VALIDATE from the public HF capture (97% of operator txs "
                                                                 "matched to a server-ms trade); block - match 1.25 / 2.20 / 3.14 s (q05 / q50 / q95) on 10-20.")
s["strategy_statement"] = (
    "One operator runs a TypeScript clob-client bot on three (plus a fourth and a fifth) wallets in every BTC 5-minute Up/Down window, and only there [VALIDATE-only]. "
    "It pre-signs BUY orders on both outcomes at every cent in bursts each window (three bursts at -89.5 / +42 / +173 s since 08-22) [VALIDATE-only]. It submits one at "
    "the ask it saw ~30 ms before arriving (93% within a tick of the archive ask at the arrival on VALIDATE weekdays) [VALIDATE-only]. Polymarket holds every marketable "
    "order 150 ms, so the bot races the crowd in that delay queue [VALIDATE-only]. Which flagged episodes it takes is not decoded beyond small gains; the take rate follows "
    "an operator-level state with a 30-60-s time scale, and the independent fast crowd takes the same onsets on an input the recorded feeds explain only 14-21% of "
    "[VALIDATE-only; open]. The side is the direction of the fast venues' microprice over the last ~100-250 ms (live 83% where the six-series vote fires; on VALIDATE "
    "weekdays at the historical decision clock 77% of taker orders at full coverage, 81-83% in the first two minutes and 62-72% after three; 76.7% per one-sided block "
    "second) [VALIDATE-only]. Lost races rest at the old ask for ~0.1-1 s and fill as maker about half the time [VALIDATE-only]. The inventory is two operator-level "
    "streams: a large-size lean fanned out to every wallet and pyramided, and a small-size taker counter-flow that buys the complement of the REALIZED large inventory "
    "within ~2 minutes (own-state feedback, t -26) [VALIDATE-only]. Public data predicts the window net at r ~0.48 (the lean at ~0.32), and an executable exposure tracker "
    "reproduces the pooled per-window PnL at r 0.4758 / 0.4404 under strict fills with >= 2 s latency (per wallet 0.06-0.43; XM is bounded at 0.30-0.41 even by perfect "
    "pooled-stream oracles, because its PnL is the side of its own dispatched legs) [VALIDATE-only]. Positions are held to resolution; 87% of shares end in complete sets "
    "bought at 0.979; income = locked sets (~2.1 c per pair) and the 50% taker-fee rebate; the lean is a coin with respect to the outcome and carries the per-window PnL "
    "variance [VALIDATE-only]. Nothing is exam-verified.")
H = s["hypotheses"]
nid = 1 + max(int(h["id"][1:]) for h in H if str(h.get("id", "")).startswith("H") and h["id"][1:].isdigit())
def add(fam, desc, vm, verdict):
    global nid
    H.append({"id": f"H{nid}", "family": fam, "description": desc, "validate_metrics": vm, "verdict": verdict}); nid += 1
add("two-stream decomposition (X121 / X118 step 0)", "cross-wallet and within-wallet correlations of large / small window nets; oracle ceilings per wallet",
    {"validate": (two or {}).get("validate"), "oracle_ceilings_validate": oc}, "streams real (L cross-wallet 0.35-0.47, within corr(L,S) -0.26..-0.60); XM bounded <= 0.37 by pooled oracles")
add("two-stream net-flow models + tracker (X121, pre-registered)", "L13 / S13 per-second LightGBM (nf12b + W13 features), trk_a_2s",
    {"window": (ls or {}).get("validate_window"), "trk_a_2s": ((tr or {}).get("trk_a_2s") or {}).get("pnl_corr_pool"), "trk_a_avg": ((tr or {}).get("trk_a_avg_check") or {}).get("pnl_corr_pool")},
    "not adopted (lower on both); same public information as nf12b (corr 0.957)")
add("pairing kernel mechanism + side tilt (X118, pre-registered tilt)", "operator realized large net K_L (60-s decay) on small / large one-sided seconds; tilt cross-fit",
    {"mechanism": mech, "tilt": ((sdp or {}).get("tilt_cross_fit") or {}).get("pooled_cross_fit")}, "mechanism confirmed (t -26.5, placebo opposite, crowd null); tilt +0.2 point, success not met")
add("decision-clock side model (X113 step 3)", "HF capture match ms, a = m - 180; Binance spot book / Bybit / USD-M / OKX / Polymarket features; fit 10-20 -> 10-21 and reverse",
    {"fit_A_score_B": (dcs or {}).get("fit_A_score_B"), "fit_B_score_A": (dcs or {}).get("fit_B_score_A"), "own_state": {k: v.get("full_own") for k, v in (dco or {}).items() if k.startswith("fit_")}},
    "77.2-77.3% full coverage per order (+4.5 over the block-clock per-order 72.7%); below 80%; pre-registered 10-17..19 split pending")
add("late-window side drivers / settlement TWAP lock-in (B3b)", "agreement of late decisions with partial TWAP, Chainlink favourite, complement of net, tick", late or {}, "no TWAP lock-in (52%); late = weak tick + pairing")
add("opening decision type (X124 step 1)", "decisions in [0, 15) s vs later: tick, exact-strike value, P(large)", opn or {}, "not a distinct decision type")
add("settlement basis (X116, pre-registered)", "Chainlink - Binance basis terms on the window-net residual", (bas or {}).get("ols"), "no gain (-0.007 / +0.0004)")
add("implied vs realized vol scale of the buy-back (X117)", "window-minute panel with DVOL / RV interactions", {"iv13": iv, "split": ivs}, "replicated interaction is realized vol; IV not supported")
add("decision-clock price (X113 step 4)", "taker limit vs archive ask at arrival - Lambda", dcp or {}, "93.4% within a tick at the arrival; trivial touch anchor")
add("dispatch predictability (X120 step 5 / X122 step 2)", "multiclass P(wallet | public state at the decision), fan-out leg order", dsp or {}, "barely above base rate; DS-first / GF-second")
add("per-wallet / per-leg pay-up (X113 step 4 follow-up)", "limit - archive ask at arrival - 30 ms by wallet and fan-out leg rank", pay or {}, "premium rises with leg rank; XM pays up 1-3 c; ask + c_w within a tick 94.5% (XM 83%)")
add("decision-clock side + signed flow / imbalance (secondary, not pre-registered)", "dcside13 with DC_EXTRA=1 on 10-20 / 10-21", {k: v.get("full") for k, v in (dcx or {}).items() if k.startswith("fit_") and isinstance(v, dict)}, "+0.4 point (77.6-77.7%); saturates below 80%")
add("decision-clock side per decision vs per order (X113)", "first legs vs follower legs of fan-out events", dlg or {}, "per decision ~75%, per order 77%")
add("USD-M bookTicker at the decision clock (X113)", "RabbitGo777 10-20 11-12 UTC USD-M microprice vs the archive spot book on the same orders", rab or {}, "no gain: the side information at the decision instant is ~75-77% on VALIDATE weekdays")
if dcfull:
    add("decision-clock side, pre-registered split (pre-registration 3)", "fit 10-17..19 -> score 10-20..22", {k: v for k, v in dcfull.items() if k.startswith("fit_") or k in ("coverage_archive_ms", "days", "fit_days")},
        "success >= 0.80 " + ("met" if (((dcfull.get("fit_A_score_B") or {}).get("full") or {}).get("acc") or 0) >= 0.80 else "not met"))
s["data_sources"].append("Iteration 13: Hugging Face Fahri-5/updown-5m-polymarket-raw (CC0, not gated), revision f848a77ccfce4421d3cedbbe585576db77d36662, polymarket/ and btc/ day files "
                         "for 10-17..22 only, read by HTTP range requests and reduced at once (trades with server ms + tx hash, touch changes, Binance spot book / trades, RTDS Chainlink); "
                         "reduced copies in the session scratchpad it13/hf_dl (not in the workspace cache); HF answers 429 under parallel ingests")
add("exam-route decision-clock side (pre-registration 4)", "spot-book-only LightGBM fit 10-17..19, scored 10-20..22; XM one-sided windows", dsp_ or {}, "74.2% per order; XM windows 81.4%; in evaluate() as side_decision_clock")
add("XM one-sided window side at the decision clock (full venue model)", "window side = mean predicted probability of XM's orders", dwin or {}, "XM windows 84.3% (24.9% one-sided); DS / GF not one-sided")
s["data_sources"].append("Iteration 13: Hugging Face RabbitGo777/polymarket.btc_20261020.v4.parquet (not gated), revision 1e0218e12491c7e1d6183350a424fb3489539129: footer of binance.btc_20261020.v4.parquet and its USD-M BTCUSDT bookTicker rows for 10-20 11:00-12:00 UTC (133 row groups by ts_local statistics, microseconds); reduced copy in the session scratchpad it13/rabbit")
s["data_sources"].append("Iteration 13: Deribit public get_volatility_index_data BTC resolution 60 (1-min DVOL), 10-09..22, end < H, via the polyrea HTTP cache")
it = {"n": 13, "minutes": MIN, "best_validate_score": 0.9132, "block_seconds_presence": 0.8747, "block_seconds_stronger_baseline": 0.8211, "pnl_corr": 0.4758, "pnl_corr_spearman": 0.4404,
      "paradigm": "Two-stream inventory account (large lean + small pairing counter-flow) with per-wallet attainability ceilings for condition 7; the public HF capture as a historical decision clock (side and price at the decision instant on VALIDATE)",
      "families": ["two-stream decomposition and per-wallet oracle ceilings (X121, X120, X122 step 3)", "pre-registered two-stream net-flow models and tracker (X121)",
                   "pairing kernel mechanism with placebo and crowd control; pre-registered side tilt (X118)", "public HF capture ingest and verification (X113 steps 1-2)",
                   "decision-clock side model and per-horizon information content (X113 step 3)", "decision-clock price vs archive touch (X113 step 4)",
                   "late-window side drivers and settlement-TWAP lock-in (B3b)", "opening decision type on the archive (X124 step 1)", "settlement basis (X116, pre-registered)",
                   "implied vs realized vol scale of the buy-back (X117)", "dispatch predictability at the decision clock (X120 step 5 / X122 step 2)"]}
s["iterations"].append(it)
s["status"] = "continue"
s["catalog_open_after_iteration13"] = sorted([k for k, v in cat.items() if v.get("status") == "open"], key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))
_en = s.get("environment_notes") or []
_note = "Iteration 13: HF range reads of ~6,300 requests per day file are fine alone but draw 429 when two run in parallel; hfingest13.py coalesces column chunks and backs off 45 s."
s["environment_notes"] = (_en + [_note]) if isinstance(_en, list) else (str(_en) + " | " + _note)
json.dump(s, open(P, "w", encoding="utf-8"), indent=1)
print("open", len(s["catalog_open_after_iteration13"]), s["catalog_open_after_iteration13"])
