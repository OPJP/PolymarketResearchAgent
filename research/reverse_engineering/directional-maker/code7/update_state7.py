"""Iteration 7: bring state.json up to date (catalog statuses with evidence, components, live lab, iteration entry,
strategy statement, target metrics). Reads the iteration-7 result files."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent / "state.json"
R = HERE.parent / "results"
s = json.loads(P.read_text())
cat = s["catalog"]
i1 = json.loads((R / "iter7_i1_cl_hist.json").read_text())
i2 = json.loads((R / "iter7_i2_publish_1793467740_1793469600.json").read_text())
sc = json.loads((R / "iter7_sel_clock_1793455600_1793464202.json").read_text())
st_ = i1["stack"]["rule"]
b3 = i1.get("b3_fill_price", {})
a15 = i2["agreement"]["15m_c500"]


def src(k):
    e = cat.get(k, {}).get("evidence", "")
    return e.split(". Not done yet.")[0] if e.startswith("source:") else ""


def setc(k, status, evidence):
    pre = src(k)
    cat[k] = {"status": status, "evidence": (pre + ". " if pre else "") + evidence}


setc("X42", "tried", "Reopened by panel iter6 I1: Polymarket's own endpoint polymarket.com/api/crypto/crypto-price?symbol=BTC&variant=fiveminute&eventStartTime=<ISO s> serves the Chainlink value stamped at any second (openPrice) and 300 s later (closePrice); verified in iteration 7 (priceToBeat = mean CL[st-61..st-2] exactly on 10-24 13:05, within $0.17 elsewhere; finalPrice within $0.01-1.07). It sustains ~1.5 requests/s (HTTP 429 above). The data.chain.link 429 is superseded. See X43.")
setc("X43", "tried", (f"Pre-registered stride-16 half of the planned sample: {i1['n']['study_windows']} STUDY + {i1['n']['valid_windows']} VALIDATE windows, Chainlink stamped at every bin start - 3 s (code7/fetch_cl.py, code7/i1_cl_hist.py, results/iter7_i1_cl_hist.json). "
                      f"Chainlink fair vs R3's Binance fair: corr {i1['gap_describe']['corr_fair_cl_fair_bn']:.3f}, |gap| median {i1['gap_describe']['study_abs_gap_median']:.3f}. "
                      f"VALIDATE-sample presence: R3 {st_['auc_base']:.4f} vs R3 + Chainlink stack {st_['auc_base+cl']:.4f} (2-h block bootstrap gain {st_['boot_gain']['mean']:+.4f}, 95% [{st_['boot_gain']['lo95']:+.4f}, {st_['boot_gain']['hi95']:+.4f}]); "
                      f"univariate Chainlink edge {i1['univariate_valid']['edge_cl_s']:.3f} vs Binance edge {i1['univariate_valid']['edge_s']:.3f}; side R3 {i1['side_valid']['r3']['acc']:.3f} vs stack {i1['side_valid']['r5_stack']['acc']:.3f}; "
                      + (f"fill prices vs fairs (VALIDATE sample, {b3['validate']['fills']} fills): MAD Chainlink {b3['validate']['mad_cl']:.4f} vs Binance {b3['validate']['mad_bn']:.4f}, corr {b3['validate']['corr_cl']:.3f} vs {b3['validate']['corr_bn']:.3f}. " if 'validate' in b3 else "")
                      + "Adopted as R5 by the pre-registered criterion (gain > 0 with 2-h block-bootstrap lower bound > 0); the gain is small because the lot's Chainlink stream is smooth (no 1-s noise). The stride-8 remainder of the sample was started detached at 18:27 UTC (log_it7_fetch_cl_b.txt)."))
setc("X44", "tried", f"Own streaming recorder code7/rtdsstream.py (dy_rtds, filters '', publish ms; started 17:29 UTC 10-31, hard stop 11-03 00:00). Event study 17:29-18:00 (code7/i2_publish.py): publish - stamp p10/50/90 {i2['publish_minus_stamp_ms_p10_50_90']} ms; BTC 15m cluster exact-500 re-posts agree with dCL_S {a15['agree_post_0_200'][0]} in the 200 ms after the publish (n {a15['agree_post_0_200'][1]}) vs {a15['agree_pre_600_100'][0]} before (n {a15['agree_pre_600_100'][1]}); bursts 0.76-0.81 at 0-150 ms. The engine re-prices on the public relay's publish (within ~0-150 ms; clock offset estimate RTDS - CLOB {i2['clock']['rtds_minus_clob_clock_ms_est']} ms), not 0.5-1 s before it. BTC 5m not testable in this half hour (cluster off BTC 5m since 16:53).")
setc("X45", "tried", "code7/i3_display.py (17:29-18:00, 1,801 publishes, 8,438 trades): net taker Up selling in the 1 s after a publish vs the displayed change corr 0.03 (5m) / -0.01 (15m), vs the futures move 0.09 / 0.12; print rates after big changes equal the rates before them. Takers do not trade on the Chainlink display; rejected in this form.")
setc("X46", "tried", "Lag-1 autocorrelation of 1-s Chainlink changes: six 60-s lot runs (10-23..26) +0.23, +0.11, +0.27, -0.32, -0.03, +0.01 (sd $0.65-3.17); 10-31 17:29-17:44 five 180-s runs -0.46..-0.60 (sd $8.3-9.4). The noise regime is new on 10-31 (panel's C3 confirmed); the exact change hour (10-30 15:00 - 10-31 00:30) is not pinned (needs ~1-s fetches of 10-30 evening at 1.5 requests/s).")
setc("X47", "tried", "Other makers' re-posts do not respond to Chainlink publishes: sizes 5-50 agree 0.515 after vs 0.503 before (n 5,080 / 12,240, BTC 5m) and 0.51 / 0.50 (15m); exact-100s 0.53 / 0.48; only the cluster's exact-500s step (0.44 -> 0.72). The skew is the cluster's own reading (I5 null rejected).")
setc("X49", "tried", f"Print selection with the Chainlink value on several clocks (code7/sel_clock.py, live split): D = 700 ms (engine clock S+0.7) {sc['a+r+cl@700']['test_auc']}, 1,083 {sc['a+r+cl@1083']['test_auc']}, 1,432 {sc['a+r+cl@1432']['test_auc']} (best; recall {sc['a+r+cl@1432']['recall_at_train_top15']} at lift {sc['a+r+cl@1432']['lift']}), 2,000 (t-2) {sc['a+r+cl@2000']['test_auc']}, 3,000 {sc['a+r+cl@3000']['test_auc']}; activity {sc['activity']['test_auc']}. The engine is not ahead of the public relay; with the publish test (X44) the 'S+0.7 s' switch is the earliest publishes (p10 0.79 s). The nowcast step and the triplet/single split on the engine clock are not done.")
for k, e in (("X48", "Kalshi KXBTC15M not fetched yet."),
             ("X50", "Not done (needs order-level ladder state; next development block 11-01 06-12 UTC)."),
             ("X51", "Not done."),
             ("X52", "Not done (needs in-block order of every print; the data-api tape has block seconds only)."),
             ("X53", "Not done; the publish-aligned Chainlink clock (X44, X49) gives its gap_cl input."),
             ("X54", "Not done."), ("X55", "Not done."), ("X56", "Not done."),
             ("X57", "Not testable before the 11-02 development blocks (00-06 and 12-18 UTC).")):
    setc(k, "open", e)
setc("X58", "open", "source: iteration 7 (own). Live: BTC 5m switched off in all three wallets at 16:53:5x UTC 10-31, inside a window that lost $1,565 of $2,426 bought, at the day's PnL low (-$2,424; $3,062 below the 15:40 peak), BTC 15m continued. Historical switch-offs (code7/stoploss.py, 5 BUILD + 1 VALIDATE): AUC of the day PnL so far 0.80, window loss 0.71 (own state). Next: exact mark-to-market path before each switch-off, threshold consistency, and the re-enable times.")
cat["X9"]["evidence"] = cat["X9"]["evidence"] + " Iteration 7: a live switch-off at the day's PnL low (X58)."
cat["X39"]["evidence"] = cat["X39"]["evidence"] + " Iteration 7: the live 16:53 switch-off followed the cluster's own loss (X58), not a visible competitor change (not measured)."
s["live_lab"] = [x for x in s.get("live_lab", []) if "rtdsstream" not in x.get("what", "")]
s["live_lab"].append({"what": "code7/rtdsstream.py: dy_rtds, unfiltered RTDS streaming updates (btc/eth/sol Chainlink + TWAP-60) with value stamp, server publish ms and receive ms; Binance clock calibration every 10 min; disk cap 60 MB", "start": 1793467740, "end": 1793664000})
s["live_lab"].append({"what": "code6/examrec.py restarted (it had died at 16:53:27 UTC 10-31): dx_* feeds as before", "start": 1793468496, "end": 1793664000})
s["status"] = "continue"
s["strategy_statement"] = (
    "[engine: VALIDATE-only] One engine signs every order of the three wallets (per-wallet salt counters, timestamp 0, daily 01:00 UTC restart). "
    "[selection: hypothesis] It quotes nearly every BTC 5m and 15m Up/Down window (plus some hourly, 4h, ETH/SOL/XRP); BTC 5m is switched off for hours at a time by an operator or loss controller (live: at the day's PnL low after a $1.6k losing window). "
    "[information + price: VALIDATE-only live / hypothesis] Both outcomes carry ladders of 500-share bids around one reservation price; the ladders are re-priced on each Chainlink BTC/USD report (the settlement stream) within ~0-150 ms of the moment Polymarket's public RTDS relay publishes it, which no other maker does, and re-anchored to the futures-driven mid between reports. "
    "[timing: VALIDATE-only] The orders that fill are fresh joins at the touch about 0.05-0.1 s after a trade sold that token, matched ~0.7 s later; fill price = last print - 1 tick on the match clock (exam-verified on the block clock at 0.69). "
    "[side: exam-verified partial] The filled side is the one whose quote is at the touch when a seller arrives; sellers follow the futures, not the displayed Chainlink price. "
    "[size: VALIDATE-only] 500 in the weekday US session or high futures vol, else 62/250. "
    "[exit: VALIDATE-only] Holds to resolution with small complement taker buys and merges. "
    "Profit = the ~6-cent spread paid by non-HFT sellers, minus losses where the Chainlink report overvalues the token relative to the faster futures.")
comp = s["components"]
comp["timing"]["description"] = ("re-price pass on each Chainlink report within ~0-150 ms of the public relay's publish (live 15m) plus single-wallet re-posts after trades; filled orders are fresh joins at the touch posted ~52-95 ms after a trade that sold that token, matched ~0.7 s later; stops ~30 s before the end.")
comp["timing"]["confidence"] = 0.7
comp["price"]["description"] = ("fill price = last clean print - 0.01: block clock 0.709 VALIDATE (exam 0.688); match clock (R4) 0.828 live VALIDATE; trivial anchor on a fresh clock. Ladder center skewed by the Chainlink report as published by the RTDS relay (print selection best with the report stamped t-1.43 s: 0.764 vs 0.637 activity) [hypothesis/live].")
comp["side"]["description"] = comp["side"]["description"] + " Takers do not trade on the displayed Chainlink price (iteration 7)."
comp["selection"]["description"] = comp["selection"]["description"] + " Live 10-31: BTC 5m off from 16:53:5x UTC in all wallets at the day's PnL low (stop-loss hypothesis, own state)."
s["target_metrics_live"]["selection_auc_print_level_cl_1432ms"] = sc["a+r+cl@1432"]["test_auc"]
s["target_metrics_live"]["selection_recall_cl_1432ms"] = sc["a+r+cl@1432"]["recall_at_train_top15"]
s["target_metrics_live"]["selection_lift_cl_1432ms"] = sc["a+r+cl@1432"]["lift"]
s["target_metrics_live"]["note_iter7"] = "print selection with the Chainlink report stamped t - 1.432 s (D scanned on this live VALIDATE: optimistic; pre-registered for 11-01 06-12 UTC); exploratory, not frozen."
s.setdefault("hypotheses", []).extend([
    {"id": "R5-cl-stack", "family": "A1/X43 historical Chainlink", "description": "R3 stacked (logistic) with Chainlink features (fair, edge, gap to Binance fair, 10-s change, z) stamped t-3 s, fit on the STUDY sample",
     "validate_metrics": {"auc_r3_sample": st_["auc_base"], "auc_r5_sample": st_["auc_base+cl"], "gain_ci": [st_["boot_gain"]["lo95"], st_["boot_gain"]["hi95"]]}, "verdict": "adopted as R5 (small gain, VALIDATE sample only)"},
    {"id": "K1-direct-feed", "family": "X44/X49", "description": "engine reads Chainlink 0.5-1 s before the public relay", "validate_metrics": {"agree_post_publish": a15["agree_post_0_200"], "agree_pre_publish": a15["agree_pre_600_100"]}, "verdict": "rejected (re-price pass at the relay publish, +-0.1 s)"},
    {"id": "K3-inherited-skew", "family": "X47", "description": "Chainlink skew inherited from other makers", "validate_metrics": {"other_small_after_before": [0.515, 0.503]}, "verdict": "rejected"},
    {"id": "I3-display-takers", "family": "X45", "description": "takers trade on the displayed Chainlink price", "validate_metrics": {"corr_5m": 0.032, "corr_15m": -0.013, "futures_corr": [0.088, 0.118]}, "verdict": "rejected"},
    {"id": "X58-stoploss", "family": "on/off", "description": "BTC 5m switched off after own losses (daily loss limit)", "validate_metrics": {"build_auc_daycum": 0.80, "events": 6}, "verdict": "open (hypothesis)"},
])
s["iterations"].append({"n": 7, "minutes": 100, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half)",
                        "paradigm": "the settlement stream on its publish clock (historical endpoint + streaming relay)",
                        "families": ["X42/X43 historical Chainlink endpoint (lot sample)", "X44 streaming RTDS publish-ms event study", "X47 other makers vs Chainlink",
                                     "X49 print selection on several Chainlink clocks", "X45 takers vs the display", "X46 noise regime", "X58 live switch-off / stop-loss",
                                     "exam recorder restart"]})
s["best"] = {"rule_id": "R5-R3+chainlink-stack+match-clock-price",
             "validate_metrics": dict(s["best"]["validate_metrics"], r5_sample={"windows": i1["n"]["valid_windows"], "bins": i1["n"]["valid_bins"],
                                                                                 "auc_r3": st_["auc_base"], "auc_r5": st_["auc_base+cl"], "gain_boot": st_["boot_gain"],
                                                                                 "side_r3": i1["side_valid"]["r3"]["acc"], "side_r5": i1["side_valid"]["r5_stack"]["acc"]}),
             "note": "R3/R4 metrics are measured on the full VALIDATE; R5's only on the pre-registered VALIDATE sample (144 windows with Chainlink)."}
s["target_metrics"]["_notes"] = ("rule R5 = R4 + Chainlink stack; the values below are R3/R4 on the full historical VALIDATE 2026-10-27..30 (R5 needs the Chainlink series, "
                                 f"available for a 144-window VALIDATE sample: presence {st_['auc_base']:.4f} -> {st_['auc_base+cl']:.4f}, side {i1['side_valid']['r3']['acc']:.3f} -> {i1['side_valid']['r5_stack']['acc']:.3f}). "
                                 "R4's match-clock price scores only where the shared recorder ran: see target_metrics_live. coverage_fills / coverage_abs_pnl: BTC 5m on VALIDATE (BTC 5m + 15m 0.868 / 0.891). "
                                 "side_baseline = market-activity-only model; own-inventory side baseline 0.70.")
P.write_text(json.dumps(s, indent=1))
print("open:", [k for k, v in cat.items() if v["status"] == "open"])
