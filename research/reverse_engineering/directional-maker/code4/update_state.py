"""Bring state.json to the 2026-10-31 brief format and record iteration 4 (run after the R3 VALIDATE evaluation)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parent
st = json.loads((D / "state.json").read_text())
r3 = json.loads((D / "results" / "iter4_r3_validate_1793059200_1793404800.json").read_text())
r2 = json.loads((D / "results" / "iter4_r2_validate_1793059200_1793404800.json").read_text())

st["split"] = {
    "BUILD": [1791504000, 1793059200],
    "STUDY": [1792713600, 1793059200],
    "VALIDATE": [1793059200, 1793404800],
    "note": ("iteration 4 (after exam round 1 released lot h1+h2): BUILD = 2026-10-09..26 (old BUILD + old VALIDATE + the "
             "lot's first half); STUDY = lot first half 2026-10-23..26 (case-by-case study allowed, part of BUILD); VALIDATE "
             "= lot second half 2026-10-27..30 (aggregate metrics only). Iterations 1-3 used BUILD 10-09..16 / VALIDATE "
             "10-16..23."),
    "description_only": "history before 2026-10-09; development live-lab blocks after T0",
}
st["primary_metric"] = ("presence_auc_validate: AUC of P(cluster gets >=1 maker BUY fill on side s in 10-s bin) over all (BTC 5m "
                        "window, side, bin in [0,300) s) of VALIDATE, point-in-time features, no own-state, clean tape (every "
                        "print in a cluster transaction removed). From iteration 4 VALIDATE = 2026-10-27..30.")
st["status"] = "continue"
st["wall_reason"] = None
st["sealed_from"] = 1792713600
st["sealed_note"] = ("lots h1 and h2 (2026-10-23..30) released after exam round 1; future 6-hour blocks from T0 = 1793404800 "
                     "follow tools/sealed.py (sealed iff d + j odd); future sealed blocks examined up to 2026-10-31T00:00Z")
st["live_lab"] = []
st["live_lab_note"] = ("no own recorder. Shared recorder (pid 27184) running; development recordings exist from 2026-10-31 "
                       "12:18 UTC. Its rtds feed had 330 messages and 0 written records at 12:50 UTC (no Chainlink recording).")

pres, side, price, pnl, sel = r3["presence"], r3["side"], r3["price"], r3["pnl"], r3["selection"]["all"]
st["target_metrics"] = {
    "presence_auc": round(pres["auc"], 4),
    "presence_baseline": round(pres["auc_activity_baseline"], 4),
    "selection_auc": round(sel["auc"], 4),
    "selection_recall": round(sel["recall_at_theta"], 4),
    "selection_lift": round(sel["lift_at_theta"], 4),
    "selection_baseline": round(r3["selection"]["activity"]["auc"], 4),
    "side_accuracy": round(side["acc"], 4),
    "side_baseline": round(r3["side_activity_baseline"], 4),
    "price_within_tick": round(price["within_0.01"], 4),
    "pnl_corr_pearson": round(pnl["pearson"], 4),
    "pnl_corr_spearman": round(pnl["spearman"], 4),
    "coverage_fills": 0.55,
    "coverage_abs_pnl": None,
    "_notes": ("rule R3 on VALIDATE 2026-10-27..30 (code/final_rule.py, results/iter4_r3_validate_*.json). coverage_fills: "
               "BTC 5m maker fills are ~55% of the cluster's fills (dossier; scope below the 80% target), coverage_abs_pnl "
               "not measured. side_baseline = market-activity-only model; own-inventory side baseline 0.70 (BUILD4 refit)."),
}
st["best"] = {"rule_id": "R3-presence-lgbm-refit-build4-clock", "validate_metrics": {
    "presence_auc": pres["auc"], "presence_auc_activity_baseline": pres["auc_activity_baseline"],
    "presence_gain_over_baseline": pres["auc"] - pres["auc_activity_baseline"],
    "presence_auc_with_own_inventory": pres["auc_with_own_inventory"],
    "presence_auc_within_active_windows": pres["auc_within_active_windows"],
    "active_window_share": pres["active_window_share"], "side": side, "side_activity_baseline": r3["side_activity_baseline"],
    "price": price, "pnl": pnl, "selection": r3["selection"], "per_wallet": r3.get("per_wallet"),
    "frozen_R2_on_same_validate": {"presence_auc": r2["presence"]["auc"], "baseline": r2["presence"]["auc_activity_baseline"],
                                   "side": r2["side"]["acc"], "price_within_0.01": r2["price"]["within_0.01"],
                                   "pnl_pearson": r2["pnl"]["pearson"], "pnl_spearman": r2["pnl"]["spearman"],
                                   "selection_auc": r2["selection"]["all"]["auc"]},
}}

st["strategy_statement"] = (
    "Three wallets run by one engine (one order counter per wallet, restarted together daily at 01:00 UTC) quote "
    "BUY orders on both outcomes of BTC 5m Up/Down windows (and other crypto Up/Down markets) on the 0.01 grid, at or "
    "near the top of the book [exam-verified: top-of-book 0.01-grid maker]. Quotes follow a TWAP-60 fair value of Binance "
    "(best explained by the futures price at the match time) and are re-signed 10-23 times a second per wallet, more "
    "when Binance moves; moves older than about 1-1.5 s are already priced into its quotes, while other makers stay "
    "exposed for 3-5 s [VALIDATE-only/STUDY: requote window from calldata match clocks]. It bids the side its fair "
    "value says the market underprices, most clearly at the open, and keeps adding to the side it holds [exam-verified "
    "partially: side 0.65 vs 0.60]. Order size follows a clock schedule: 500 shares on weekdays from 12:00 to about "
    "21:00 UTC, 62 or 250 at night and on weekends, with a one-fifth second level [STUDY + VALIDATE aggregate]. Which "
    "windows it trades is a switch inside the running engine (off overnight or on weekends on some days, back on at "
    "12:00-15:30 UTC), invisible in public data [hypothesis: operator decision]. It holds to resolution. It earns the "
    "spread from dispersed larger takers plus a small rebate (8% of PnL); liquidity rewards are negligible ($0.81). "
    "Not decoded: when its bid is at the top of the book (the quote state), which caps the presence AUC near 0.73 even "
    "with oracle taker flow.")
st["components"] = {
    "selection": {"confidence": 0.3, "tag": "hypothesis",
                  "description": ("BTC 5m enabled per period inside the running engine (not process restarts): on in weekday "
                                  "US hours; off overnight/weekends on some days (10-23 21:00 -> 10-24 15:25, 10-24 23:00 -> "
                                  "10-25 13:33 UTC); 94.5% of VALIDATE windows active. No public correlate beyond the clock "
                                  "(+0.002 AUC).")},
    "timing": {"confidence": 0.55, "tag": "VALIDATE-only",
               "description": ("continuous requoting: 10-23 orders/s per wallet, rising with Binance activity (Spearman 0.67); "
                               "exposed only to the last ~0.25-1.5 s of Binance moves (others 3-5 s); orders rest at the open "
                               "and stop ~30 s before the end; fills follow a favourable 2-5 s move of the token.")},
    "side": {"confidence": 0.45, "tag": "exam-verified",
             "description": ("side with the higher predicted presence (fair value vs market edge, opening strike gap, momentum "
                             "of the token's fair): VALIDATE 0.66 vs 0.61 market-activity baseline (0.70 with own inventory); "
                             "exam round 1 0.655 vs 0.600.")},
    "price": {"confidence": 0.5, "tag": "exam-verified",
              "description": ("0.01 grid at the best bid: last clean print on s minus 0.01 is within one tick for 71% of "
                              "VALIDATE fills (exam 0.688); live pilot: fill price = best bid in 11 of 15; limit price corr "
                              "0.85 with a futures TWAP-60 fair at the match time.")},
    "size": {"confidence": 0.6, "tag": "VALIDATE-only",
             "description": ("clock schedule from calldata: 500 shares weekdays 12:00-~21:00 UTC, 62 (or 250) nights and "
                             "weekends, second level one fifth (100/12/50); earlier ladders 500/1000 (10-09..16) and "
                             "500/250/125 (10-16..22); size does not depend on edge within a session.")},
    "exit": {"confidence": 0.5, "tag": "hypothesis",
             "description": ("holds to resolution (REDEEM rows; occasional MERGE of pairs); adds to the side it holds; "
                             "stops BTC 5m after losing evenings on some nights (own-state, two events in 10-16..22).")},
}

def item(status, evidence):
    return {"status": status, "evidence": evidence}

st["catalog"] = {
    "A1": item("open", "settlement source: Gamma resolutionSource Chainlink TWAP-60 verified; priceToBeat(W) = finalPrice(W-1); Binance TWAP proxy matches 98.1% of outcomes (iteration 1). No 1-s Chainlink history (data.chain.link 429 per brief); the shared recorder's rtds feed wrote 0 records by 12:50 UTC 10-31."),
    "A1_B3b": item("open", "last-60-second lock-in: the cluster stops quoting ~30 s before the end (fills in last 30 s fall to a third, iteration 3); its response to the partly observed settlement not measured (needs Chainlink 1-s)."),
    "A2": item("open", "partial: Binance spot aggTrades ms (10-26) used as match clock and fair; Kraken 1-s (iteration 3) fits worse than Binance. Coinbase, OKX, composites not tested."),
    "A3": item("tried", "Binance USD-M futures aggTrades 10-08..30 (10-28 from Bybit perp): futures fair explains limit prices better than spot for the cluster (0.846 vs 0.838) and for other makers (0.846 vs 0.814); presence +0.0007, side +0.005 on VALIDATE (not adopted). Funding, liquidations, options not tested."),
    "A4": item("open", "ETH/SOL/XRP moves and the cluster's overlapping 15m/1h/4h windows not used as features yet."),
    "A4b": item("open", "Kalshi crypto 15m/hourly and Polymarket perps not fetched."),
    "A5": item("not_applicable", "crypto Up/Down strategy: no sports or esports markets."),
    "A6": item("not_applicable", "no event markets traded; macro news reaches BTC 5m through spot prices already in the features."),
    "A7": item("open", "partial: tape-based last trade / spread / flow features in R2-R3; constant fee 0.07 and reward parameters for all windows (iteration 3); live books pilot on 15 fills (iteration 4). Up+Down ask/bid sums need books (live lab)."),
    "A8": item("open", "partial: the cluster's own engine restarts measured from the salt counter (daily 01:00 UTC + ad hoc) and they do not switch BTC 5m on/off; the 10-29 18:00-19:00 UTC pause seen. Matching-engine restarts, post-only periods and tick changes not obtained (recorder 'c' records not analysed yet)."),
    "B1": item("tried", "V2 matchOrders calldata of all 34,606 lot txs that filled the cluster in BTC 5m (+6,026 other-market, +10,500 public samples): cluster timestamp = 0 (no signing time), salt = per-wallet counter (restarts, 10-23 orders/s, rate follows Binance), original sizes (clock schedule), signature types; takers' and other makers' ms signing times used as the match clock."),
    "B2": item("tried", "orders consumed within 0-2 s (iterations 2-3); signing-rate from the salt counter; other makers' order ages at fill (median 4.7 s; older orders hit after 4x larger adverse moves)."),
    "B3": item("tried", "fair-value variants (vol scale, lookback; iterations 1-3), ms clock and futures reference (iteration 4: corr 0.85, MAD ~0.055); no quote function of fair alone reaches the touch-anchored price rule."),
    "B4": item("open", "MERGE rows (1,667 in the lot) and REDEEMs present; pair/merge mechanics not analysed; dossier: locked pair spread about zero or negative."),
    "B5": item("tried", "anti-balancing inventory (adds to the held side, iteration 1); overnight stops after losing evenings (iteration 2); size schedule by clock, not by edge or inventory (iteration 4)."),
    "B6": item("tried", "MAKER_REBATE $4,975 over 2026-10-22..30 = 8% of the lot PnL; Gold tier 18% (dossier); verdict PnL at 0% tier 97%."),
    "B7": item("ruled_out", "88% of STUDY orders >= 50 shares, but REWARD rows total $0.81 over 2026-10-22..30 for all three wallets: rewards are not a motive."),
    "B8": item("open", "holdingRewardsEnabled not checked for BTC 5m listings."),
    "B9": item("open", "maker rebate pool share by market not computed."),
    "C1": item("tried", "same-engine fingerprint (timestamp 0 + counter salt) searched in 7,500 public BTC 5m txs (5,000 in off periods): no fourth wallet; mo-money's Safe owner EOA 0xd1f9bc03... signs for no other maker in the samples; almach/bosona owner keys need ERC-1271 recovery (not done)."),
    "C2": item("open", "lead-lag against other large wallets not tested."),
    "C3": item("tried", "dispersed takers (3,200-5,300, top-10 11-13%; iterations 2-3); iteration 4: takers' signing ms show other makers are picked off within 100-250 ms of Binance moves, the cluster much less."),
    "C4": item("tried", "versions: ladder 500/1000 (10-09..16) -> 500/250/125 (10-16..22) -> clock schedule 500 / 62 / 250 (lot); restarts daily 01:00 UTC and ad hoc; models refit on the lot regime (+0.008)."),
    "C4b": item("open", "change points not matched against Polymarket announcements."),
    "C5": item("tried", "clock schedule: size switch at 12:00 UTC weekdays (to ~21:00), daily 01:00 UTC restart, weekend/overnight BTC 5m off periods with manual-looking returns (13:33, 15:25 UTC); clock features +0.002 presence AUC."),
    "C6": item("open", "rfqEnabled / combos not checked."),
    "C7": item("open", "self-matching between the three wallets and referrals not checked (2.5% of taker txs fill two cluster wallets, iteration 1)."),
    "C8": item("open", "partial: fingerprint = timestamp 0, metadata 0, builder 0, sequential salt counter, sizes 500/62/250 with a one-fifth level; public GitHub bot search not done."),
    "D1": item("tried", "per bin (primary), per print (selection), per order (orderHash, calldata); oracle-flow diagnostic shows the quote state is the missing unit."),
    "D2": item("open", "only LightGBM and explicit rules; hazard / HMM / sequence models not tried."),
    "D3": item("open", "examiner's strict replay of R2 (-12.8%); own replay with sub-second requote not built."),
    "D4": item("open", "partial: PnL by session (US +4.7-5.1%, night +0.4-3.3%), by size (> 40 shares), by time in window; full decomposition not done."),
    "X1": item("tried", "source: exam round 1 diagnosis (calldata order reconstruction: original size, expiration, signer). Done as B1: original sizes and signers decoded; V2 has no expiration; cluster timestamp = 0."),
    "X2": item("open", "source: exam round 1 (live lab: book at its decision times). Pilot on 15 fills of 2026-10-31 12:18-13:00 UTC; needs more development blocks."),
    "X3": item("open", "source: exam round 1 (settlement feed). No Chainlink 1-s history; recorder rtds writes 0 records."),
    "X4": item("tried", "source: exam round 1 (sibling wallets). Fingerprint search negative (see C1)."),
    "X5": item("tried", "source: exam round 1 (bot versions). Size schedule and restarts decoded (see C4, C5)."),
    "X6": item("ruled_out", "source: reviewer lead 2026-10-31 (liquidity-reward eligibility, rewardsMinSize 50 / maxSpread 4.5). REWARD income $0.81 in 9 days (see B7)."),
    "X7": item("open", "source: reviewer lead 2026-10-31 (operational events: matching-engine restarts with 2-min post-only, tick changes, pauses as the cause of 19-97% daily activity). Own restarts do not explain the on/off; exchange events not obtained."),
    "X8": item("tried", "source: reviewer lead 2026-10-31 (V2 signing times to measure requote speed vs Binance, settlement TWAP and books). Cluster leaves timestamp 0; measured with takers' signing ms: exposure window ~0.25-1.5 s vs 3-5 s for other makers."),
    "X9": item("open", "source: exam round 1 (selection of windows undecoded). Clock features tried (+0.002); runtime switch inside the engine; no public correlate yet."),
}

st.setdefault("hypotheses", []).extend([
    {"id": "H40", "family": "B1 calldata fingerprint", "description": "decode V2 matchOrders of every lot tx that filled the cluster",
     "validate_metrics": {"cluster_timestamp_zero_share": 1.0, "salt_counter_monotone": 0.975, "orders_per_s_median": 13},
     "verdict": "no signing time; salt is a per-wallet counter (restarts daily 01:00 UTC); signing rate follows Binance"},
    {"id": "H41", "family": "liquidity rewards (B7, X6)", "description": "orders >= 50 shares near the mid for the reward pool",
     "validate_metrics": {"orders_ge_50_share": 0.879, "reward_usd_9d": 0.81}, "verdict": "ruled out"},
    {"id": "H42", "family": "size schedule (C5/C4)", "description": "original order size vs clock",
     "validate_metrics": {"us_session_500_share_study_val": [0.757, 0.704], "night_62_share_study_val": [0.653, 0.388]},
     "verdict": "decoded: 500 on weekdays 12-21 UTC, 62/250 otherwise (+ one-fifth level)"},
    {"id": "H43", "family": "requote latency (ms match clock)", "description": "Binance move before fills, cluster vs other makers",
     "validate_metrics": {"adv5_250ms": [0.041, 0.072, 0.014], "adv5_1s": [0.098, 0.125, 0.06], "groups": "cluster, others, random"},
     "verdict": "cluster exposed to the last ~0.25-1.5 s only; others 3-5 s"},
    {"id": "H44", "family": "A3 futures reference", "description": "Binance USD-M futures fair and lead features",
     "validate_metrics": {"price_corr_cluster_spot_fut": [0.838, 0.846], "presence_auc_with_without": [0.7142, 0.7135]},
     "verdict": "explains quotes slightly better for all makers; no presence gain; not adopted"},
    {"id": "H45", "family": "E6 same-engine siblings", "description": "timestamp-0 + counter-salt makers in public txs",
     "validate_metrics": {"sampled_txs": 7500, "siblings_found": 0}, "verdict": "ruled out for this fingerprint"},
    {"id": "H46", "family": "oracle-flow ceiling (diagnostic)", "description": "presence with the bin's own future taker flow",
     "validate_metrics": {"oracle_flow_only": 0.682, "r2_plus_oracle_flow": 0.7298, "p_fill_given_hits": 0.117},
     "verdict": "taker flow is not the bottleneck; the quote state (top of book) is"},
    {"id": "H47", "family": "refit on BUILD4 + clock (R3)", "description": "R2 features refit on 10-09..26, plus UTC hour, weekday, US session",
     "validate_metrics": {"refit": 0.7135, "refit_clock": 0.7159, "frozen_r2": 0.7051}, "verdict": "adopted as R3 (small gain)"},
])
st.setdefault("data_sources", []).extend([
    "V2 calldata (decoded orders) of the lot txs that filled the cluster, other-market STUDY txs and public samples (.cache/re/directional-maker/calldata/; iteration 4)",
    "Binance spot aggTrades 2026-10-26 (ms) and Binance USD-M futures aggTrades 2026-10-08..30 reduced to 1-s (10-28 from Bybit perp; .cache/re/directional-maker/fut1s/; iteration 4)",
    "released lot files of the examiner (.cache/re/directional-maker/exam/: windows, taker tapes, activity, spot, panels; iteration 4)",
    "cluster activity of the 2026-10-31 12:00-18:00 development block and the live recorder's clob_crypto books (iteration 4)",
])
st.setdefault("iterations", []).append({"n": 4, "minutes": 95, "best_validate_score": round(pres["auc"], 4),
    "validate_definition": "2026-10-27..30 (lot second half)",
    "families": ["B1 calldata fingerprint and counter", "B7 rewards", "C1 siblings", "C5 clock schedule / size", "A3 futures reference",
                 "ms requote latency", "oracle-flow diagnostic", "live lab pilot", "refit on BUILD4", "clock features"]})
(D / "state.json").write_text(json.dumps(st, indent=1, default=str))
print("state.json updated; open:", [k for k, v in st["catalog"].items() if v["status"] == "open"])
print(json.dumps(st["target_metrics"], indent=1))
