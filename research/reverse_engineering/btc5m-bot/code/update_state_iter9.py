"""Iteration 9: update state.json (catalog X59-X71 from the iteration-8 panel, X18 re-opened as X60, components, strategy
statement, hypotheses, data_sources, iterations, target_metrics with the stronger presence baseline)."""
import os, json, shutil, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
P = _ROOT + "/research/reverse_engineering/btc5m-bot/state.json"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
shutil.copy(P, _ROOT + "/.cache/re/btc5m-bot/state_backup_iter8.json")
s = json.load(open(P))
MIN = float(sys.argv[1]) if len(sys.argv) > 1 else None


def J(name):
    p = f"{R}/{name}"
    return json.load(open(p)) if os.path.exists(p) else None


ins = J("ins9.json"); insb = J("ins9b.json"); ceil = J("pnlceil9.json"); cen = J("census9.json"); st9 = J("stale9.json")
dep = J("depth9.json"); oth = J("other9.json"); who = J("who9.json"); flg = J("flag9.json"); aug = J("blkaug9.json"); fee = J("fee9.json"); feeb = J("fee9b.json")

cat = s["catalog"]
I8 = "panel iteration 8"
cat["X18"]["status"] = "open"
cat["X18"]["evidence"] += (" | Iteration 9: RE-OPENED as X60. The data host is not archive.pmxt.dev: https://r2v2.pmxt.dev/polymarket_orderbook_2026-08-01T12.parquet answers HTTP 206 "
                           "to a 1-byte range request without a key (Content-Range bytes 0-0/477191092, 0.39 s, 10-31 19:57 UTC). Coverage 2026-04-13 .. 08-10 (panel); not downloaded yet.")
cat["X59"] = {"status": "open", "source": f"{I8}, information P1 (per-block historical match clock from fresh-signed anchors; strong form of X12 / X22 / X40)",
              "evidence": "Not tested in iteration 9 (the decision-record pivot came first). Panel numbers: within-block log-index vs match-ms Spearman 0.80; oracle-anchor interpolation 54.9% of txs "
                          "within 200 ms vs 24.5% for a constant lag; naive fresh-signed anchors 38.9% vs 25.3%."}
cat["X60"] = {"status": "open", "source": f"{I8}, information P2 (historical live lab: pmxt v2 archive with server ms and tx hashes 2026-04-13..08-10, Tardis free days 07-01 / 08-01)",
              "evidence": "Endpoint verified in iteration 9 (HTTP 206, no key; see X18). The reducer and the decision-level tests are not run (disk fell to 3.3 GB free at 20:00 UTC, external)."}
cat["X61"] = {"status": "tried", "source": f"{I8}, information P3 (who takes the liquidity at the instants the trigger flags: a lost race or no decision?)",
              "evidence": "who9.py (results/who9.json): the asks the cluster's lost races aimed at were taken by other takers 52.9%, by the cluster's own earlier legs 19.2%, requoted away 27.9%. "
                          "flag9.py (results/flag9.json; FULL hazard on the decision label, fit A, scored C, AUC 0.728): top 1% of the score P(cluster decision) 23.3%; where it did not decide another "
                          "taker bought o in [t+100, t+600) in 79.8% (bottom 50%: 35.1%), nothing 17.7%; top 3% 17.4% / 72.5%; own busy slots do not suppress decisions (23.5% busy vs 16.5%). "
                          "Decision count (ins9b): ~1.45 decisions per filled order. Answer: mostly NO DECISION at instants other fast takers take; the selection rule is open."}
cat["X62"] = {"status": "open", "source": f"{I8}, information P4 (which reference: an absolute digital at implied vol vs a Polymarket-anchored value; bracket midpoints of opposite-outcome pairs)",
              "evidence": "Part (b) in hazard form tested by X63 (a Polymarket-anchored edge since o's last touch change adds < 0.002 AUC; weak-vote side 52-72%). The bracket-midpoint regression is not done."}
cat["X63"] = {"status": "tried", "source": f"{I8}, mechanics P1 (stale-quote edge since o's touch last changed; inverse-fit of the trigger's quote function)",
              "evidence": "stale9.py (results/stale9.json): E = mid_o(a) + k Delta dS - ask_o (anchor = last change of o's bid or ask, k = 2 chosen on A among 6 variants, univariate AUC 0.48-0.52); "
                          "hazard U-shaped in E; FULL + E vs FULL +0.0002 / +0.0003 (match label, B / C), +0.0013 / +0.0009 (decision label), CIs include 0; weak / no-vote side by argmax E 52-72%. "
                          "Rejected: subsumed by the tick terms. With decisions as positives the frozen FULL design rises 0.759 -> 0.768 (B), 0.700 -> 0.728 (C)."}
cat["X64"] = {"status": "tried", "source": f"{I8}, mechanics P2 (visible Polymarket depth sets the pay-up level, the size and the fan-out)",
              "evidence": "depth9.py (results/depth9.json; 1,326 taker-first orders, book at m - 50 ms): pay-up limit == depth-cover level 17.6% (touch + 1 c 51.8%); the touch covered the order in "
                          "54.8% of pay-ups; P(pay-up | touch < size) 30.4% vs 25.3%. Large size vs depth: within-wallet AUC of the touch size DS 0.37 / GF 0.46 / XM 0.53 (thin books; 16-20 large "
                          "orders per wallet, under-powered). Rejected for the price; size stays own-state policy. Fan-out from depth not tested (X54 covers intensity)."}
cat["X65"] = {"status": "tried", "source": f"{I8}, mechanics P3 (ghost orders: the full decision record from the touch feeds)",
              "evidence": "ins9.py / ins9b.py: truth set of 502 MT remainders (finder 92.4%); 1,041 maker-first insertions: lost races 79.7% (73.9% + 19.7% of unambiguous ones), passive 3.1% of "
                          "unambiguous; pi_rem = 0.458 -> 1.42-1.46 decisions per filled order (q = 0.69-0.70): a SELECTIVE bot (panel thresholds: lottery >= 2.5, selective ~1.5). "
                          "Anonymous ghost attribution not needed for the count (X15's identity problem stands for unfilled orders)."}
cat["X66"] = {"status": "open", "source": f"{I8}, mechanics P4 (operator completeness: W4 into the operator net and out of the market-activity baseline)",
              "evidence": "Not tested in iteration 9 (needs W4's fills by topic2 and the BUILD tapes); the baseline audit without W4 removal is X70 (partial)."}
cat["X67"] = {"status": "tried", "source": f"{I8}, assumptions P1 (XM changed role: decode its passive 60-share component; re-derive which conditions bind)",
              "evidence": "ins9b / who9: 346 XM 60-share maker-first orders are lost races in 87% (69% within 300 ms), passive 10%; vote at insertion 79.8% (65 / 77 / 89 / 96% by strength, placebo 51%); "
                          "the ask they aimed at was taken by DS 26% / GF 8% / others 45% / requoted 21%, median 124 ms earlier: XM is the late leg of the fan-out, not a passive quoter. "
                          "census9.py: one-sided share vs the order-count null VALIDATE XM 24.3% vs 26.1%, GF 3.1% vs 3.7%, DS 0.2% vs 0.7%; 10-31 XM 3.5% vs 6.1%: no wallet chooses a side per "
                          "window beyond its order count. Maker share of fills XM 41% / 44% / 91% (BUILD / VALIDATE / 10-31)."}
cat["X68"] = {"status": "tried", "source": f"{I8}, assumptions P2 (score the decisions that lost the race: insertions of filled maker-first orders as decision instants)",
              "evidence": "ins9b: 8-series vote at lost-race insertions 80.5% on 78.9% voted (strength 62.6 / 83.5 / 86.1 / 94.7%; placebo 52.0%) = won races 80.6% (70.9 / 74.6 / 84.0 / 95.5%). "
                          "Gate: o's ask rose before 33.6% of lost races vs 24.5% of won races. Hazard with decisions as positives: OOS AUC +0.009 (B) / +0.028 (C) (stale9)."}
cat["X69"] = {"status": "tried", "source": f"{I8}, assumptions P3 (the PnL condition's test-retest ceiling by race-lottery resampling)",
              "evidence": "pnlceil9.py (results/pnlceil9.json; VALIDATE): exact ceiling under independent races r = 1 - (1 - q) kappa; the model reproduces the empirical split-half (pooled 0.199 vs "
                          "0.201, DS 0.011 vs 0.013, GF 0.188 vs 0.193, XM -0.024 vs -0.020). Pooled kappa 0.668: r = 0.74 [0.71, 0.76] at q = 0.61, 0.80 [0.78, 0.82] at q = 0.70; per wallet at "
                          "q = 0.61 DS 0.62, GF 0.73, XM 0.59; q needed for 0.5: 0.25 / 0.49 / 0.27 / 0.52. Hypothesis (ceiling < 0.5) REJECTED: condition 5 is attainable in principle and bound by "
                          "decision overlap (the replica reproduces ~8% of the decision instants)."}
cat["X70"] = {"status": "open", "source": f"{I8}, assumptions P4 (audit the presence gain against an examiner-strength market-only baseline, W4 removed from both models)",
              "evidence": "Partial (blkaug9.py, results/blkaug9.json): baseline + dm1, dm2, the other outcome's tape state, Up + Down ask sum: VALIDATE AUC 0.8211 (pure 0.8193); full 0.8747; gain "
                          "+0.0536, 2-h block bootstrap [0.0506, 0.0563], p = 0 / 2,000; GF +0.063, XM +0.066, DS +0.051; halves +0.053 / +0.053. Open: bot-size print counts, sub-second "
                          "intensities and W4's prints removed (need the tapes and W4's fills); the live 100-ms baseline extension."}
cat["X71"] = {"status": "tried", "source": f"{I8}, assumptions P5 (one process, several assets: shared capacity)",
              "evidence": "other9.py (results/other9.json; 1,882 sampled txs, 11 windows of 10-31 16-17 UTC: ETH 5m x3, SOL 5m x3, BTC 15m x2, BTC 5m x3): operator wallets only in BTC 5m (100% / 88% "
                          "of their orders inside the bursts); no maker with >= 8 orders on another asset signs >= 60% inside the -89.5 / +42 / +172.7 s bursts; fingerprinted orders on other assets "
                          "3.1% in-burst (random). Rejected: the process is BTC-5m-only."}
cat["X72"] = {"status": "open", "source": "iteration 9 (own, from X61 / X65): the SELECTION RULE among flagged instants",
              "evidence": "The bot decides at ~1 of 4-5 top-hazard instants (up to ~1 of 3 with unfilled lost races) while other takers take ~80% of the rest. Ruled out as the selector: own busy "
                          "slots (flag9), other assets (X71), the stale-quote edge (X63), visible depth (X64)"
                          + ((". PARTLY EXPLAINED by a fee-aware delta-scaled edge V = k 100 Delta move - (half spread + 0.035 p(1-p)) (fee9 / fee9b): the hazard steps up ~8x where V crosses 0 "
                             "(A: 3.0% -> 26.2%; C: 3.3% -> 26.7%), within the top 3% of the hazard V separates taken from skipped instants with AUC 0.62 (cost alone 0.61, gain 0.64), FULL + V +0.001 "
                             "[0.0004, 0.0018]; k scan in results/fee9b.json (k = 8: +0.0037 [0.0015, 0.0059]); on the exam feeds the pre-registered rule V_8 > 0 (final_rule edge_rule_V8) has lift 1.5 / 7.7 / 3.1 "
                             "on three 30-60-min intervals (unstable). Own-book set completion tilts it too (setgate9, own state: P(decision | flagged) 31% when the leg pairs unpaired shares "
                             "below 0.97 vs 12% with no holdings of the other outcome; AUC 0.59-0.60)") if fee else "") +
                          ". Next: the competitor set from tx senders, the queue ahead at the touch, the touch size, time since o's last trade, the window's running volume; replicate on 11-01 06-12 "
                          "and on the pmxt summer hours (X60)."}

comp = s["components"]
comp["timing"]["description"] = ("Decision = submission of a pre-signed ladder order ~250-350 ms after a Binance USD-M / OKX / Bybit microprice tick toward the outcome (Polymarket leg <= 50-150 ms); "
                                 "~1.45 decisions per filled order (lost races rest at the old ask and fill as maker in 46%): the bot is SELECTIVE - at the top 1% of the decoded hazard it decides "
                                 "~23% of the time while other takers take ~80% of the instants it skips; its own slots, other assets, a stale-quote edge and visible depth do not explain the skips. "
                                 "Decision-level hazard frozen on the exam feeds: AUC 0.656 vs 0.598 out of sample (0.728 on decisions incl. lost races, lab feeds); historically presence on block "
                                 "seconds 0.875 vs 0.821 for a stronger market baseline (+0.054, CI [0.051, 0.056]).")
comp["timing"]["confidence"] = 0.8
comp["side"]["description"] = ("Per decision (live): the microprice vote over [m-600, m-100) ms, the SAME for won races (80.6%) and lost races (80.5% at the insertion; 63 / 84 / 86 / 95% by strength); "
                               "exam-feed six-series vote 85.4% on 68% of decisions; pre-registered full-coverage fallbacks 70.6-78.2% in sample; at the block clock 72.7% per order. No wallet is "
                               "one-sided beyond its order-count null (XM 24.3% vs 26.1% on VALIDATE, 3.5% vs 6.1% on 10-31), so the side condition does not bind in substance. The side does not "
                               "reference the operator's book, an exact-strike FV or a stale-quote edge; the underdog tilt is consistent with an implied-vol FV (hypothesis).")
comp["price"]["description"] = ("Limit = the touch it saw 50-150 ms before the match (74-75% exact live, 95.1% within a tick on VALIDATE calldata; trivial touch anchor, stated as such); maker-first "
                                "orders are the same limits after a lost race (the ask 150-1,000 ms before the insertion, which the order then rests at); 16% of taker orders deliberately 1+ c above "
                                "the touch (not the depth-cover level: 17.6%).")
comp["size"]["description"] = ("Fixed (small, large) menu per day; the large size follows the OPERATOR's own net on the outcome (own state): large when flat or adding, small when reducing an opposite "
                               "position; within-wallet AUC GF 0.75, XM 0.67, DS 0.58 vs market controls 0.35-0.55; large orders come with thin visible books (weak, under-powered) and lose 1-2 c "
                               "per share after fees. XM's 60-share class on 10-31 is its late-leg size (lost races), not a passive component.")
comp["exit"]["description"] = ("Taker remainders (38% of taker-first orders on 10-31) and lost races rest as GTC bids at the old ask for seconds; 46% of remainders get a maker fill (10-31), then the "
                               "rest is cancelled; every position is held to resolution (no sells, merges, splits); 87% of shares end paired at 0.979; REDEEM per window; TAKER_REBATE = 0.5 x the "
                               "previous day's taker fees; one in-flight order per wallet, so decisions fan out across wallets and XM, the last leg, loses most races.")

s["strategy_statement"] = (
    "One operator runs a TypeScript clob-client bot on three (plus a fourth) wallets in every BTC 5-minute Up/Down window, and only there [VALIDATE-only]. It pre-signs a ladder of BUY orders on "
    "both outcomes at every cent three times per window [VALIDATE-only] and submits one about 250-350 ms after a microprice tick of the Binance USD-M / OKX / Bybit BTC and ETH perps toward an "
    "outcome, at the touch it saw 50-150 ms earlier, deliberately 1+ c higher in 16% of orders [VALIDATE-only]. It is selective: about 1.45 decisions per filled order, and at the instants its "
    "decoded trigger flags most strongly it acts about one time in four while other fast takers take the liquidity [VALIDATE-only; what selects those instants is a hypothesis-level open "
    "question]. The side is the tick direction (85% per decision on live development data, 97% on strong ticks; the same for races it wins and races it loses) [VALIDATE-only]; a lost race "
    "rests at the old ask and fills as maker about half the time, which is where half of its 10-31 maker fills (and XM's 91% maker share) come from [VALIDATE-only]. The size is small unless "
    "the operator's own book is flat or long the outcome [VALIDATE-only, own state]; each wallet carries one order at a time, so a decision fans out across wallets [VALIDATE-only]. Positions "
    "are held to resolution; 87% of shares end in complete sets bought at 0.979 [VALIDATE-only]. Income = locked sets (~2.1 c per pair) and the 50% taker-fee rebate; the large-size overlay "
    "loses money [VALIDATE-only]. Nothing is exam-verified. The PnL condition is attainable in principle (true-rule test-retest ceiling 0.74-0.80 pooled) and is bound by decision overlap.")

s["hypotheses"].extend([
    {"id": "H100", "family": "decision record: maker-first orders = lost races (X68 / X65)", "description": "insertions of maker-first orders classified by the ask path; vote at insertion",
     "validate_metrics": {"refined": (insb or {}).get("M_first_refined", {}).get("class"), "vote_lost_300": (insb or {}).get("vote_by_refined_class", {}).get("lost_300", {}).get("agree_on_voted")},
     "verdict": "supported (live development): lost races 80% of maker-first orders, vote 80.5% = won races"},
    {"id": "H101", "family": "XM passive 60-share component (X67)", "description": "post-only quotes below the ask", "validate_metrics": (insb or {}).get("vote_by_refined_class", {}).get("XM60_all"),
     "verdict": "rejected: late taker legs (lost races 87%, vote 79.8%)"},
    {"id": "H102", "family": "race lottery vs selective bot (X65)", "description": "decisions per filled order", "validate_metrics": (insb or {}).get("decisions"), "verdict": "selective (~1.45 per filled order)"},
    {"id": "H103", "family": "PnL test-retest ceiling (X69)", "description": "r = 1 - (1 - q) kappa under independent races", "validate_metrics": (ceil or {}).get("pooled"),
     "verdict": "ceiling 0.74-0.80 pooled: condition 5 attainable in principle; bound by decision overlap"},
    {"id": "H104", "family": "stale-quote edge (X63)", "description": "edge since o's last touch change", "validate_metrics": (st9 or {}).get("models_fit_A"), "verdict": "rejected (< 0.002 AUC over the tick)"},
    {"id": "H105", "family": "visible depth (X64)", "description": "pay-up at the depth-cover level; size from depth", "validate_metrics": {"payup": (dep or {}).get("payup"), "size": (dep or {}).get("size_from_depth")},
     "verdict": "rejected for the price (17.6%); size weakly inverse, under-powered"},
    {"id": "H106", "family": "shared capacity across assets (X71)", "description": "fingerprinted wallets on ETH / SOL 5m, BTC 15m", "validate_metrics": {k: (oth or {}).get(k) for k in ("operator_orders_by_kind", "other_assets_fingerprinted_in_burst")},
     "verdict": "rejected (BTC-5m-only)"},
    {"id": "H107", "family": "flagged instants (X61)", "description": "what happens at top-hazard instants without a decision", "validate_metrics": {k: (flg or {}).get(k) for k in ("top1pct", "top3pct", "bottom50pct")},
     "verdict": "others take ~80%; the cluster decides ~23%; busy slots do not suppress"},
    {"id": "H108", "family": "stronger presence baseline (X70 partial)", "description": "pure + dm1/dm2 + other outcome + ask sum", "validate_metrics": aug, "verdict": "gain +0.054 [0.051, 0.056]: presence holds"},
])
if fee:
    s["hypotheses"].append({"id": "H109", "family": "fee-aware delta-scaled edge (X72 step)", "description": "V = 100 Delta move - half spread - net fee", "validate_metrics": fee, "verdict": "see NOTES iteration 9 finding 12"})
s["data_sources"].extend(["Iteration 9: V2 calldata of all 7,179 cluster txs of 10-31 12:00-17:56 (it9/cd9.parquet + post/cd*.parquet)",
                          "Iteration 9: calldata of 1,882 sampled ETH 5m / SOL 5m / BTC 15m / BTC 5m txs of 10-31 16-17 UTC (decoded in memory; results/other9.json)",
                          "Iteration 9: pmxt v2 archive host verified (r2v2.pmxt.dev, HTTP 206 without a key)"])
tm = s["target_metrics"]
if aug:
    tm["presence_baseline"] = aug["auc_augmented_baseline"]
s["target_metrics_notes"]["presence_baseline"] = ("Iteration 9: the STRONGER of my two market-activity baselines on VALIDATE block seconds: the iteration-5 pure baseline (0.8193) augmented with "
                                                  "dm1, dm2, the other outcome's tape state and the Up + Down ask sum (blkaug9.py: 0.8211); gain of the frozen full model +0.0536, 2-h block "
                                                  "bootstrap [0.0506, 0.0563]; per wallet GF +0.063, XM +0.066, DS +0.051.")
s["target_metrics_notes"]["iteration9"] = ("Historical rule unchanged; presence_baseline now the stronger baseline. Side: no wallet is one-sided beyond its order-count null (XM 24.3% vs 26.1%), so the "
                                           "side condition does not bind in substance; side_accuracy keeps the per-one-sided-second value. PnL: the true-rule test-retest ceiling is 0.74 [0.71, "
                                           "0.76] pooled at q = 0.61 (DS 0.62, GF 0.73, XM 0.59): attainable in principle; the replica's 0.18 is a decision-overlap gap.")
s["best"]["rule_id"] = "it9: unchanged frozen rule of iteration 8 (code/final_rule.py); iteration 9 added measurements, no new rule component"
s["best"]["validate_metrics"]["iteration9"] = {"presence_gain_vs_stronger_baseline": (aug or {}).get("gain_vs_augmented"), "pnl_ceiling_pooled_q061": (ceil or {}).get("pooled", {}).get("boot_r_q0.61")}
s["status"] = "continue"
s["iterations"].append({"n": 9, "minutes": MIN, "best_validate_score": 0.9132, "block_seconds_presence": 0.8747, "block_seconds_stronger_baseline": (aug or {}).get("auc_augmented_baseline"),
                        "pnl_corr": 0.1755, "paradigm": "decision record from the book (insertions incl. lost races) + PnL test-retest ceiling + selectivity of flagged instants",
                        "families": ["decision record: maker-first insertions as decisions (X68, X65)", "XM role change decoded as late legs (X67)", "side-condition applicability by order-count null (X67)",
                                     "PnL test-retest ceiling under a race lottery (X69)", "stale-quote edge (X63)", "visible depth for pay-up and size (X64)", "other assets fingerprint search (X71)",
                                     "flagged-instant classification and own slots (X61)", "stronger presence baseline (X70 partial)", "fee-aware delta-scaled edge (X72 step)",
                                     "pmxt archive host verification (X18 / X60)"]})
json.dump(s, open(P, "w"), indent=1, default=str)
op = [k for k, v in s["catalog"].items() if v.get("status") == "open"]
print("catalog", len(s["catalog"]), "open", len(op), op)
