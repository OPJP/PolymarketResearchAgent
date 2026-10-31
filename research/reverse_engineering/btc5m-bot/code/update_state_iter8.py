"""Iteration 8: update state.json (catalog X44-X58 from the iteration-7 panel, components, strategy statement, hypotheses,
live_lab, data_sources, iterations, target_metrics notes)."""
import os, json, shutil, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
P = _ROOT + "/research/reverse_engineering/btc5m-bot/state.json"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
shutil.copy(P, _ROOT + "/.cache/re/btc5m-bot/state_backup_iter7.json")
s = json.load(open(P))


def J(name):
    p = f"{R}/{name}"
    return json.load(open(p)) if os.path.exists(p) else None


own = J("own8_side.json"); size = J("size8.json"); rep = J("replica8.json"); live = J("live8.json"); gate = J("gate8_1793458500.json")
haz = J("hazard8_frozen_C.json"); wf = J("weakflow8.json"); pms = J("pmside8_1793458500.json"); fb = J("fallback8.json"); ptb = J("ptb8.json")
lst = J("lstar8.json"); ref = J("refractory8.json"); ev = J("events8_1793458500.json"); ver = J("version8.json"); eco = J("econ8.json"); msg = J("msg8.json")

cat = s["catalog"]
I7 = "panel iteration 7"
cat["X44"] = {"status": "open", "source": f"{I7}, information P1 (record the rest of the Binance family, Deribit quotes, L2 depth, liquidations; test on weak-vote decisions)",
              "evidence": "Step 0 done (weakflow8.py, results/weakflow8.json): signed aggressive notional of Binance USD-M over [m-600, m-100) on weak votes BTC 55.1% (placebo 55.8%, n = 68), "
                          "ETH 47.3% (40.0%); no vote 45% / 40% (n = 25): no signal. Step 1 done: rec_fam8.py (pid 20608) records btc5m_xfam (USDC-M perps, COIN-M perps, spot USDC/FDUSD, "
                          "Deribit perp quotes, Bybit L1) and btc5m_xliq (USD-M liquidations) in every block 10-31 17:45 -> 11-03 18:00 UTC. Step 2 (kernels and weak-vote agreement of the new "
                          "series) needs the next development block (11-01 06-12): open. L2 depth@100ms not recorded (disk)."}
cat["X45"] = {"status": "tried", "source": f"{I7}, information P2 (settlement index from Gamma priceToBeat; time-driven value / TWAP lock-in as the quiet late trigger)",
              "evidence": "fetch_ptb8.py: priceToBeat for all 4,032 BUILD+VALIDATE windows (ptb.parquet). ptb8.py (results/ptb8.json): FV from Binance spot x a basis fixed at the open from "
                          "priceToBeat, TWAP and spot versions, vol multiplier 0.8-2.0: 'buy Up iff FV_up > last Up price' 50-55% on all VALIDATE one-sided seconds (psb 75.3%), 47-55% on quiet late "
                          "seconds (psb 61.5%), 51-54% in the quiet last minute (psb 56.3%); when FV_TWAP and FV_spot disagree the bot follows TWAP 42-53%; psb + gap lowers accuracy (69.9-73.3%). "
                          "Rejected at the block clock. Not done: the theta hazard on the live unit."}
cat["X46"] = {"status": "tried", "source": f"{I7}, information P3 (complete the future-block exam inputs: weekday sealed blocks, Bybit, near-touch depth, new series)",
              "evidence": "rec_exam8.py (launcher pid 19600) runs rec_exam7's recorder unchanged as btc5m_xclob8 / btc5m_xven8 from 11-02 05:59 to 11-03 18:00 UTC (weekday sealed blocks 11-02 06-12, "
                          "18-24, 11-03 00-06, 12-18); rec_fam8 adds Bybit L1 and the Binance family in every block; final_rule reads both feed-name sets and reports the pre-registered "
                          "eight-series vote (side_live_decision_ext). Not done: near-touch depth in sealed blocks (disk budget) and the Bybit ob200 archive input (replaced by the recorded Bybit L1)."}
cat["X47"] = {"status": "tried", "source": f"{I7}, information P4 (decision instant on Polymarket's clock: limit vs touch at m - L)",
              "evidence": "lstar8.py (results/lstar8.json; 171 live taker orders with calldata limits in the unthrottled book 14:14-14:47): P(limit == ask(m - L)) 29.8% at 0 ms, 74.9% at 50, "
                          "73.7% at 100, 70.8% at 200, 62.6% at 300, 49.1% at 500, 38% at 1,000 (placebo 5-7%): the bot's view of the touch is <= ~50-150 ms old; pay-up 21/171, 18 deliberate, 1 stale. "
                          "The 250-350 ms venue-to-match lag is upstream of the Polymarket leg; kernel re-alignment changes it by <= 100 ms (not redone)."}
cat["X48"] = {"status": "open", "source": f"{I7}, information P5 (co-terminal cross-market consistency with the Polymarket BTC 15m / 1h / 4h windows)", "evidence": "Not tested in iteration 8."}
cat["X49"] = {"status": "tried", "source": f"{I7}, mechanics P1 (operator-level position-scaled sizing)",
              "evidence": "size8.py (results/size8.json): within-wallet VALIDATE AUC of the large size (BUILD-fitted): market controls GF 0.489 / XM 0.353 / DS 0.546; + market analog (BTC return "
                          "since open toward o) 0.528 / 0.420 / 0.558; + operator net 0.751 (halves 0.72 / 0.81) / 0.666 (0.64 / 0.71) / 0.578 (0.56 / 0.73); siblings' net only 0.650 / 0.642 / 0.598; "
                          "P(large) GF 12% (net < -200) -> 77% (flat) -> 59-63% (long); large orders lose after fees (DS -1.92, GF -1.06, XM -1.62 c/share). replica8.py: own-net size rules in the "
                          "executable replica do not lift the PnL correlation (convention b pool 0.128-0.156 vs 0.179 presence-weighted). Size = own-book overlay (VALIDATE-only, own state); "
                          "the PnL bottleneck is decision overlap."}
cat["X50"] = {"status": "tried", "source": f"{I7}, mechanics P2 (complete sets: does the side reference the set?)",
              "evidence": "own8.py (results/own8_side.json; 90,170 VALIDATE one-sided seconds): short-leg rule 51.0% (57.6% at 240-300 s); psb 75.3% -> psb + own state 75.5% (+0.7-0.9 at "
                          "240-300 s); half-fitted diagnostic 75.9% vs 75.6%. Rejected. econ8.py (results/econ8.json): 87.4% of shares paired at a pair cost of 0.9786; gross $65,960 = locked "
                          "sets $48,923 + unpaired $17,037; fees $61,572; taker rebate $30,786; per-window total vs unpaired r = 0.93. Step 2 (|net| null) not done."}
cat["X51"] = {"status": "open", "source": f"{I7}, mechanics P3 (depth-aware strict fills from calldata: provable resting maker depth)", "evidence": "Not tested (needs ~1.4k matchOrders calldata per window)."}
cat["X52"] = {"status": "tried", "source": f"{I7}, mechanics P4 (identify the single triggering message per decision)",
              "evidence": "msg8.py (results/msg8.json): per-series lags from the iteration-7 kernels (fitted 14:50-16:04); trigger = the tick with the latest effective time in [m - W, m]; "
                          + (json.dumps({k: {kk: (v.get(kk) if isinstance(v, dict) else None) for kk in ("trigger_cover", "trigger_agree")} for k, v in (msg or {}).items() if k != "lags_ms"})[:600] if msg else "pending")
                          + ". On weak votes the single message does not beat the vote; on no-vote decisions it is anti-predictive at short W. The single-message form is rejected; "
                          "the composite-threshold hazard (step 3) is covered by X56 (_live_hazard)."}
cat["X53"] = {"status": "open", "source": f"{I7}, mechanics P5 (rebate tier as the controller of the large-size base rate)", "evidence": "Not tested in iteration 8 (X33 step 1 found tier bonuses)."}
cat["X54"] = {"status": "tried", "source": f"{I7}, assumptions P1 (multi-leg sweep events: intensity is the size decision; top leg = reservation price)",
              "evidence": "events8.py (results/events8_1793458500.json; 14:55-16:04, 604 taker matches -> 494 events; every multi-leg event spans >= 2 wallets): P(legs >= 2) 16.6%; univariate AUC rel "
                          "0.64, |vote| 0.58, composite toward o 0.58, ask change of o 0.40; half-split activity 0.61 / 0.63 vs + trigger 0.64 / 0.67; P(multi-leg) 12-16% (< 0.5 bp) -> 22-25% (> 0.5 bp). "
                          "Signature (>= 0.70 vs <= 0.60) not met. Not done: the reservation-price fit (FV_bot from the top leg)."}
cat["X55"] = {"status": "tried", "source": f"{I7}, assumptions P2 (wallets as concurrency slots with a refractory period; dispatcher)",
              "evidence": "refractory8.json: taker matches per wallet never < 120 ms apart on two new intervals (DS min 123 / 288 ms, GF 128 / 76 (one gap), XM 171 / 320); same-wallet share of "
                          "< 300 ms pairs 8.7% / 3.9% vs independence 52% / 51%; within 100 ms 0 / 1 same-wallet vs 75 / 37 cross-wallet. Replicated. Not done: dispatcher fit and per-wallet re-dispatch."}
cat["X56"] = {"status": "tried", "source": f"{I7}, assumptions P3 (tick as the clock, stale liquidity as the gate)",
              "evidence": "gate8.py (results/gate8_1793458500.json): hazard by tick x change of o's ask over [t-500, t): > 0.5 bp tick: ask fell 22.2%, rose 12.0%, unchanged 11.4%; no tick 5.3 / 5.2 / "
                          "2.1%: the bot acts in MOVING books (the unrepriced-touch form is reversed). Out of sample (live8.py, fit_hazard8.py): lab feeds fit 14:55-16:04 -> 16:04-16:33 0.759 vs "
                          "Polymarket-activity baseline 0.718 (gain CI [0.016, 0.073]); -> 16:33-17:55 0.700 vs 0.608 ([0.066, 0.119]); exam feeds frozen in final_rule (_live_hazard, fit "
                          "16:04-16:33) -> 16:33-17:55 0.656 vs 0.598, gain +0.058 [0.041, 0.076]."}
cat["X57"] = {"status": "open", "source": f"{I7}, assumptions P4 (aim at the exams: h1 first, weekday sealed recording, fallback, version transfer)",
              "evidence": "Recording re-planned (rec_exam8, weekday sealed blocks); the block-clock fallback is the historical rule already in evaluate (scope 100%); version check (version8.py): signing "
                          "schedule, pay-up share (16.1% vs 16.0%) and cross-wallet multi-leg structure transfer from VALIDATE to 10-31; the large share is day / regime dependent. Open: the "
                          "weekday vs weekend comparison on 11-02 development blocks."}
cat["X58"] = {"status": "open", "source": f"{I7}, assumptions P5 (underdog tilt from a return-unit threshold or a liquidity shape)", "evidence": "Not tested in iteration 8."}
# older items touched this iteration
cat["X39"]["evidence"] = (cat["X39"].get("evidence", "") + " | Iteration 8 (X47): the Polymarket leg of the latency is <= ~50-150 ms (limit = ask 50-100 ms before the match in 74-75%).").strip(" |")
cat["X42"]["evidence"] = (cat["X42"].get("evidence", "") + " | Iteration 8 (lstar8): pay-up is deliberate (18 of 21 pay-up orders saw the consumed touch), not a stale view.").strip(" |")
cat["B4"]["evidence"] = (cat["B4"].get("evidence", "") + " | Iteration 8 (X50): strong form tested: the side does not reference the set (+0.2 points); 87.4% of shares paired at 0.9786.").strip(" |")
cat["B6"]["evidence"] = (cat["B6"].get("evidence", "") + " | Iteration 8 (econ8): VALIDATE gross $65,960 (sets $48,923 + unpaired $17,037), fees $61,572, taker rebate $30,786.").strip(" |")
cat["C1"]["evidence"] = (cat["C1"].get("evidence", "") + " | Iteration 8 (X55): wallets are concurrency slots (no same-wallet taker matches < 120 ms).").strip(" |")
cat["A1"]["evidence"] = (cat["A1"].get("evidence", "") + " | Iteration 8 (X45): Gamma priceToBeat for all BUILD+VALIDATE windows; exact-strike FV (TWAP and spot) has no side information at the block clock.").strip(" |")

s["components"] = {
    "selection": {"confidence": 0.85, "tag": "VALIDATE-only", "description": "Every BTC 5m Up/Down window (94-99% traded), nothing else; prices in the ladder range ~0.12-0.88; whole-cluster outages are bot-side."},
    "timing": {"confidence": 0.8, "tag": "VALIDATE-only", "description": "Decision = submission of a pre-signed ladder order ~250-350 ms after a Binance USD-M / OKX / Bybit microprice tick toward the outcome (Polymarket leg <= 50-150 ms); the hazard doubles when the Polymarket touch of the outcome is moving (22% per 500 ms with a > 0.5 bp tick while o's ask falls, 2% with neither); decision-level hazard frozen on the exam feeds: AUC 0.656 vs Polymarket-activity baseline 0.598 out of sample (+0.058, CI [0.041, 0.076]); historically presence on block seconds 0.875 vs 0.819."},
    "side": {"confidence": 0.6, "tag": "VALIDATE-only", "description": "Per decision (live): the microprice vote over [m-600, m-100) ms, 85.2% on the fourth interval (stable by strength: 70% / 80% / 90% / 97% for 1 / 2 / 3-4 / 5+ agreeing series); exam-feed six-series vote 85.4% on 68% of decisions; pre-registered full-coverage fallbacks (Polymarket ask moves, underdog) 70.6-78.2% in sample; at the block clock 72.7% per order. The side does not reference the operator's book (+0.2 points) nor the exact-strike fair value."},
    "price": {"confidence": 0.9, "tag": "VALIDATE-only", "description": "Limit = the touch it saw 50-150 ms before the match (74-75% exact live, 95.1% within a tick on VALIDATE calldata; trivial touch anchor, stated as such); 16% of orders deliberately 1+ c above the touch (GF 27%, XM 38-46%, DS 9-10%; more for large orders and late in the window)."},
    "size": {"confidence": 0.7, "tag": "VALIDATE-only", "description": "Fixed (small, large) menu per day; the large size follows the OPERATOR's own net on the outcome (own state): large when flat or adding (GF 59-77%, XM 59-83%), small when the order would reduce an opposite position (12-15%); within-wallet AUC GF 0.75, XM 0.67, DS 0.58 vs market controls 0.35-0.55 and a market-trend analog 0.52; large orders lose 1-2 c per share after fees."},
    "exit": {"confidence": 0.9, "tag": "VALIDATE-only", "description": "Taker remainders rest as GTC for at most a few seconds and are cancelled; every position is held to resolution (no sells, merges, splits); 87% of shares end paired in complete sets at a pair cost of 0.979; REDEEM per window; TAKER_REBATE = 0.5 x the previous day's taker fees; one in-flight order per wallet (refractory >= 120 ms), so decisions fan out across wallets."},
}
s["strategy_statement"] = (
    "One operator runs a TypeScript clob-client bot on three (plus a fourth) wallets in every BTC 5-minute Up/Down window. It pre-signs a ladder of BUY orders on both outcomes at every "
    "cent three times per window [VALIDATE-only] and submits one about 250-350 ms after a microprice tick of the Binance USD-M / OKX / Bybit BTC and ETH perps toward an outcome, more often "
    "while the Polymarket touch is moving [VALIDATE-only], at the touch it saw 50-150 ms earlier, deliberately 1+ c higher in 16% of orders [VALIDATE-only]. The side is the tick direction "
    "(85% per decision on live development data, 97% on strong ticks, 70% on single-series ticks) [VALIDATE-only]; the size is small unless the operator's own book is flat or long the outcome "
    "[VALIDATE-only, own state]; each wallet carries one order at a time, so a decision fans out across wallets [VALIDATE-only]. Remainders are cancelled within seconds; positions are held "
    "to resolution; 87% of shares end in complete sets bought at 0.979 [VALIDATE-only]. Income = locked sets (~2.1 c per pair) and the 50% taker-fee rebate; the large-size overlay loses "
    "money [VALIDATE-only]. Nothing is exam-verified; the weak-tick decisions (31-45% of live decisions) remain unexplained [hypothesis: an unrecorded fast stream; recording since 10-31 17:45].")

s["hypotheses"].extend([
    {"id": "H78", "family": "complete-set side (X50)", "description": "side references the operator's book", "validate_metrics": (own or {}).get("lag1"), "verdict": "rejected (+0.2 points)"},
    {"id": "H79", "family": "own-net size (X49)", "description": "P(large) from the operator net", "validate_metrics": {w: (size or {}).get(w) for w in ("GF", "XM", "DS")}, "verdict": "supported for GF/XM (VALIDATE-only, own state)"},
    {"id": "H80", "family": "replica with own-net size (X49 step 4)", "description": "executable replica sized by its own simulated net", "validate_metrics": {k: v for k, v in (rep or {}).items() if k.startswith("b_")}, "verdict": "no gain (0.128-0.156 vs 0.179)"},
    {"id": "H81", "family": "stale-touch gate / decision-level hazard (X56)", "description": "hazard by tick x touch repricing; frozen exam-feed hazard", "validate_metrics": {"gate_table": (gate or {}).get("hazard_tick_x_repr"), "frozen_exam_C": haz}, "verdict": "gate reversed (moving touch); hazard gain +0.058 out of sample"},
    {"id": "H82", "family": "fourth live interval", "description": "frozen exam-feed vote and ten-series vote on 16:33-17:55", "validate_metrics": {"exam": (live or {}).get("frozen_live_vote_exam_feeds_C"), "ten": (live or {}).get("ten_series_vote_C")}, "verdict": "85.4% / 85.2%"},
    {"id": "H83", "family": "weak-vote inputs (X44 step 0)", "description": "signed aggressive Binance USD-M flow on weak votes", "validate_metrics": {k: (wf or {}).get(k, {}).get("weak_1_2") for k in ("BTCUSDT", "ETHUSDT")}, "verdict": "no signal"},
    {"id": "H84", "family": "full-coverage live side (pre-registered)", "description": "vote -> PM ask rose 600 ms -> PM ask fell 3 s -> underdog", "validate_metrics": fb, "verdict": "70.6-78.2% in sample; first clean test 11-01 06-12"},
    {"id": "H85", "family": "time-driven value with exact strike (X45)", "description": "FV_TWAP / FV_spot vs last price", "validate_metrics": {k: (ptb or {}).get(k, {}).get("late_quiet") for k in ("k1.0", "k1.3", "k1.6")}, "verdict": "rejected at the block clock"},
    {"id": "H86", "family": "decision instant (X47)", "description": "limit vs ask at m - L", "validate_metrics": {k: v for k, v in (lst or {}).items() if k != "profile_L_all_changed_placebo"}, "verdict": "Polymarket leg <= 50-150 ms; pay-up deliberate"},
    {"id": "H87", "family": "concurrency slots (X55) and multi-leg intensity (X54)", "description": "refractory per wallet; P(legs >= 2)", "validate_metrics": {"refractory": ref, "intensity": (ev or {}).get("intensity")}, "verdict": "refractory replicated; intensity weakly predictable (0.64-0.67)"},
    {"id": "H88", "family": "single triggering message (X52)", "description": "latest lag-shifted tick as the trigger", "validate_metrics": msg, "verdict": "does not beat the vote"},
    {"id": "H89", "family": "economics (X50 step 4)", "description": "locked sets vs unpaired remainder", "validate_metrics": eco, "verdict": "sets $48.9k + unpaired $17.0k gross; fees $61.6k; rebate $30.8k (VALIDATE)"},
])
s["live_lab"].extend([
    {"what": "rec_fam8.py (pid 20608): feeds btc5m_xfam (Binance USDC-M perps, COIN-M perps, spot BTCUSDC/ETHUSDC/BTCFDUSD bookTicker, Deribit quote.*-PERPETUAL, Bybit linear orderbook.1; 30 ms) and btc5m_xliq (Binance USD-M !forceOrder BTC*/ETH*), EVERY block via tools/live.py Writer (sealed blocks filed by the Writer, never read); cap 290 MB; status .cache/re/btc5m-bot/rec_fam8.status",
     "start": 1793468719, "end": 1793728800},
    {"what": "rec_exam8.py (launcher pid 19600): sleeps until 11-02 05:59:00 UTC, then rec_exam7's recorder unchanged as btc5m_xclob8 / btc5m_xven8 (EVERY block via the Writer; weekday sealed blocks 11-02 06-12, 18-24, 11-03 00-06, 12-18); cap 290 MB; status .cache/re/btc5m-bot/rec_exam78.status",
     "start": 1793599140, "end": 1793728800},
])
s["data_sources"].extend(["Iteration 8: on-chain cluster fills 10-31 16:33-17:56 (development block; post/own_1793464380_1793469400.parquet)",
                          "Iteration 8: Gamma /events eventMetadata.priceToBeat for all 4,032 BUILD+VALIDATE windows (ptb.parquet; finalPrice settlement-only)",
                          "Iteration 8: own recorders rec_fam8 (Binance USDC-M / COIN-M / spot USDC-FDUSD books, Deribit, Bybit L1, liquidations) and rec_exam8 (exam inputs on weekday blocks)"])
s["sealed_from"]["development_after_H_used"] = [[1793404800, 1793426400], [1793448000, 1793469600]]
s["target_metrics_notes"]["iteration8"] = ("VALIDATE target_metrics unchanged (historical rule unchanged). Live development (not VALIDATE, not counted): exam-feed side vote 85.4% on 68% of "
                                           "decisions (16:33-17:55); pre-registered full-coverage side 70.6% / 78.2% in sample; decision-level presence (frozen exam-feed hazard) 0.656 vs a "
                                           "Polymarket-activity baseline 0.598 out of sample (gain +0.058, CI [0.041, 0.076]). Executable PnL: no size rule lifts the replica (0.13-0.18).")
s["best"]["rule_id"] = "it8: it7 rule + full-coverage live side + decision-level hazard (exam feeds) + rec_exam8 / rec_fam8 inputs (code/final_rule.py)"
s["best"]["validate_metrics"]["live_iteration8"] = {"exam_vote_C": (live or {}).get("frozen_live_vote_exam_feeds_C"), "hazard_frozen_C": haz,
                                                    "full_coverage_in_sample": {k: (v or {}).get("full_coverage_accuracy") for k, v in (fb or {}).items()}}
s["status"] = "continue"
s["iterations"].append({"n": 8, "minutes": None, "best_validate_score": 0.9132, "block_seconds_presence": 0.8747, "block_seconds_pure_baseline": 0.8193, "pnl_corr": 0.1755,
                        "families": ["complete-set side with own state (X50)", "own-net size and the size-aware executable replica (X49)", "stale-touch gate / decision-level hazard on the exam feeds (X56)",
                                     "fourth out-of-sample live interval", "weak-vote inputs: signed aggressive flow (X44 step 0) and the Polymarket book", "full-coverage live side (pre-registered)",
                                     "exact-strike time value from Gamma priceToBeat (X45)", "decision instant on Polymarket's clock (X47)", "concurrency slots / refractory (X55)",
                                     "multi-leg intensity (X54)", "single triggering message (X52)", "version transfer (X57 step 4)", "economics: locked sets vs unpaired (X50 step 4)",
                                     "new recorders: Binance family + Deribit + Bybit + liquidations (rec_fam8), weekday exam inputs (rec_exam8)"]})
json.dump(s, open(P, "w"), indent=1, default=str)
op = [k for k, v in s["catalog"].items() if v.get("status") == "open"]
print("catalog", len(s["catalog"]), "open", len(op), op)
