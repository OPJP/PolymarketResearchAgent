"""Iteration 5: bring state.json to the 2026-10-31 brief format (catalog with X items, target_metrics, components with tags,
sealed_from, live_lab, strategy_statement) and append this iteration. Usage: python update_state_iter5.py MINUTES NOW_TS"""
import os, json, sys
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
from catalog_iter5 import CATALOG
R = os.path.abspath(os.path.join(CODE, ".."))
S = json.load(open(f"{R}/state.json"))
J = lambda f: json.load(open(f"{R}/{f}")) if os.path.exists(f"{R}/{f}") else {}
dp = J("results_decision_presence_iter5.json"); pbk = J("results_presence_book_iter5.json")
ll = J("results_live_lab_iter5.json"); lt = J("results_live_trigger_iter5.json")
minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
now_ts = int(sys.argv[2]) if len(sys.argv) > 2 else 0

TM = {"presence_auc": 0.8747, "presence_baseline": 0.8193, "selection_auc": 0.8693, "selection_recall": 0.6858, "selection_lift": 4.625,
      "selection_baseline": 0.8461, "side_accuracy": 0.7666, "side_baseline": 0.6323, "price_within_tick": 0.532,
      "pnl_corr_pearson": 0.1755, "pnl_corr_spearman": 0.1692, "coverage_fills": 1.0, "coverage_abs_pnl": 1.0}
COMP = {
    "selection": {"confidence": 0.85, "tag": "VALIDATE-only", "description": "Every BTC 5m Up/Down window (94-99% traded, all wallets in the same windows), nothing else; inside a window only prices in the ladder range ~0.12-0.88."},
    "timing": {"confidence": 0.65, "tag": "VALIDATE-only", "description": "Orders are pre-signed in 3 bursts per window (rel -89.5/+42.0/+172.7 s, decoded exactly from calldata); the decision is the submission, within ~1 s of a move of a multi-venue/multi-asset BTC composite (live: BTC/ETH futures trade or quote moves in the last 1 s agree 78-87% when present) and inside bursts of other takers lifting the same asks; matches ~2.2 s before its block; activity given mid-range prices rises through the window and stops ~270-290 s. Presence on block seconds 0.875 vs pure market baseline 0.819 (+0.055, CI [0.052, 0.058])."},
    "side": {"confidence": 0.55, "tag": "VALIDATE-only", "description": "Per second: the outcome toward which the composite (BTC venues, ETH/alt perps, Bybit perp book imbalance) just moved, 76.7% of one-sided seconds (taker 79.4%); both outcomes in 99.8% of windows (no window-level side)."},
    "price": {"confidence": 0.85, "tag": "VALIDATE-only", "description": "Limit = the best ask of the chosen outcome at the decision instant, implemented by submitting the pre-signed 1-cent ladder order at that price; never sweeps; remainder rests at that price (its only maker activity). Live development block (frozen code, 95 taker orders): fill price = recorded ask 50 ms before the match in 86.7%, within one tick 96.7%; historically (no book) 53% within a tick of the last implied ask."},
    "size": {"confidence": 0.7, "tag": "VALIDATE-only", "description": "Fixed (small, large) menu per day signed at every price (60/100, 30/50, 30/100); large share is a per-wallet setting (DS 5%, GF 30%, XM 32%), weakly higher after big moves."},
    "exit": {"confidence": 0.9, "tag": "VALIDATE-only", "description": "Holds to resolution; no sells, merges, splits or conversions; one REDEEM per window; daily MAKER_REBATE (~$3.1k/week); no liquidity or holding rewards."},
}
STATEMENT = ("One operator runs a TypeScript clob-client bot on (at least) four wallets [VALIDATE-only]. For every BTC 5-minute Up/Down "
             "window it pre-signs a full ladder of BUY limit orders on both outcomes at every cent, in bursts 90 s before the open and "
             "again at +42 s and +173 s, signing the wallets one after another [VALIDATE-only, decoded from calldata]. When BTC (on "
             "Binance, OKX, Bybit; or ETH and other coins that lead it) moves in the last second or two, it submits the pre-signed order "
             "at the current best ask of the outcome the move favours [VALIDATE-only], racing other latency takers; an unfilled remainder "
             "rests at that price [VALIDATE-only]. Sizes come from a fixed daily menu (mostly 30 shares, some 60/100) [VALIDATE-only]. It "
             "buys both outcomes in almost every window and holds everything to resolution, redeeming winners [VALIDATE-only]. It earns "
             "the latency edge after clear moves plus fee rebates on its large volume [VALIDATE-only]; its quiet-period volume roughly "
             "breaks even [VALIDATE-only]. Nothing is exam-verified yet.")
NEW_H = [
    {"id": "H38", "family": "order generation (B1 calldata)", "description": "Orders are pre-signed in bursts (1-cent BUY ladder, both outcomes, copies, two sizes) at rel -89.5/+42/+173 s; submission is the decision", "validate_metrics": {"orders": 13443, "share_in_bursts": 0.999, "gap_median_s": 71.5, "gap_99pct_s": 133}, "verdict": "supported (deterministic, 100% of 1,514 orders in the end-to-end check)"},
    {"id": "H39", "family": "wallet coordination (C1)", "description": "One process signs the wallets sequentially (XM, DS +1.06 s, GF +2.17 s); fourth wallet 0xd84403ef... with the same fingerprint", "validate_metrics": {"fourth_wallet_fills_in_sampled_hour": 344}, "verdict": "supported"},
    {"id": "H40", "family": "baseline correction", "description": "Pure market-activity baseline (no Binance FV gaps or spot-since-print)", "validate_metrics": {"pure_baseline": 0.8781, "gain": 0.0351, "selection_pure_baseline": 0.8461, "selection_gain": 0.0232}, "verdict": "measurement fixed; gain +0.035 < 0.05"},
    {"id": "H41", "family": "D1 decision-aligned presence", "description": "Label = fill at block second s+k from cell-s features (k=1: horizon at the decision time)", "validate_metrics": dp.get("k1", {}), "verdict": "rejected as a gain: +0.0353 (k=1) vs +0.0351 (k=0), +0.020 (k=2)"},
    {"id": "H42", "family": "perp order book (A3, Bybit orderbook.200)", "description": "Bybit perp top-of-book features in the side model", "validate_metrics": {"side": 0.7666, "without": 0.7546, "mcnemar_p": 1e-32}, "verdict": "supported (+1.2 points); in the frozen side model"},
    {"id": "H43", "family": "perp order book in presence (X6)", "description": "Bybit perp book features in the presence model", "validate_metrics": {k: pbk.get(k) for k in ("auc_full_plus_book", "auc_full", "auc_pure_baseline")}, "verdict": "rejected (+0.0002)"},
    {"id": "H44", "family": "time stop vs price range (B3b)", "description": "Activity taper at 240-270 s = price leaving the ladder range; true stop ~270-290 s", "validate_metrics": {"fill_rate_given_mid_240_270": 0.33, "fill_rate_given_mid_0_15": 0.11, "fill_rate_given_mid_285_300": 0.07}, "verdict": "supported"},
    {"id": "H45", "family": "rewards / merges / holding (B4, B7, B8)", "description": "Non-trade activity types", "validate_metrics": {"REWARD": 0, "YIELD": 0, "MERGE": 0, "SPLIT": 0, "CONVERSION": 0}, "verdict": "ruled out"},
    {"id": "H46", "family": "live lab: limit vs recorded touch; match latency", "description": "Taker limit vs the recorded best ask just before the match; match -> block", "validate_metrics": {k: ll.get(k) for k in ("T_n", "T_limit_within_tick_share", "T_limit_eq_ask_share", "T_match_to_block_q")}, "verdict": "consistent with 'at the touch' (small n; T12 file unreadable after 12:24:51)"},
    {"id": "H47", "family": "live lab: trigger lead-lag (Chainlink RTDS, Binance futures, ETH, tape, book)", "description": "Event study at the bot's match times vs placebo", "validate_metrics": {k: v for k, v in lt.items() if k.startswith(("chainlink_[-3000,0)", "bnf_[-2000,0)", "bot_since", "placebo_since", "ask_change"))}, "verdict": "suggestive, small n"},
]
NEW_H += [
    {"id": "H48", "family": "copy trading, strong form (C2)", "description": "Does one wallet lead the cluster's taker orders with a fixed lag / size ratio?", "validate_metrics": {"orders": 21863, "wallets": 246, "top_same_second_share": 0.123, "top_wallet": "0xd84403ef (sibling)"}, "verdict": "rejected: co-racers (incl. the sibling), no leader"},
    {"id": "H49", "family": "live price rule (frozen code)", "description": "Fill price = recorded best ask 50 ms before the recorded match", "validate_metrics": {"n": 95, "within_tick": 0.9667, "exact": 0.8667, "fixed_lag_block_minus_2s": 0.6526}, "verdict": "supported on the 10-31 13:00 development block (small n)"},
    {"id": "H50", "family": "operational outages (A8) and versions (C4)", "description": "Whole-cluster gaps and config changes at restarts", "validate_metrics": {"empty_windows": 292, "gaps_3_5h": 4, "size_change_at_restart": "10-19 13:40: large 50 -> 100"}, "verdict": "measured"},
]
NEW_H += [
    {"id": "H51", "family": "presence unit = Polygon block seconds (D1)", "description": "1 second in 3 has no block (1.5-s blocks) and cannot hold a fill; chain clock fitted per hour; models retrained on BUILD block seconds", "validate_metrics": {"auc_full": 0.8747, "auc_pure": 0.8193, "gain": 0.0554, "ci95": [0.0524, 0.0582], "halves_gain": [0.0546, 0.055], "positives_outside": 0}, "verdict": "supported: presence condition (AUC >= 0.85, gain >= 0.05, CI > 0) holds on VALIDATE with my baseline"},
    {"id": "H52", "family": "live trigger at ms resolution (A1/A3/A7/X8/X11)", "description": "Event study at 265 recorded matches (10-31 13:00-13:22)", "validate_metrics": {"bnf_trades_1s": [0.857, 42], "eth_trades_1s": [0.866, 67], "bnf_quotes_1s": [0.842, 19], "eth_quotes_1s": [0.778, 27], "chainlink_1s": [0.505, 212], "ask_rose_1s": [0.596, 0.249], "ask_rise_with_trade_vs_no_trade": [101, 14], "within_0.5s_after_other_trade": [0.853, 0.664], "btc15m_mid_1s": [0.659, 88]}, "verdict": "supported: futures/ETH moves in the last second drive the side when present; Chainlink 1-s price carries nothing; most orders sit in bursts of other takers lifting the same asks"},
]
NEW_DS = ["Iteration 5: V2 matchOrders calldata (batched eth_getTransactionByHash) for 17,709 cluster txs in 11 sampled hours (decoded orders only: .cache/re/btc5m-bot/calldata_sample.parquet) + the development blocks after T0",
          "Iteration 5: cluster OrderFilled logs for development blocks after T0 (10-31 00:00-06:00: 9,420 fills; 12:00-13:00) (.cache/re/btc5m-bot/post/)",
          "Iteration 5: live lab (tools/live.py iter_live, dev blocks only): clob_crypto books/trades and RTDS Chainlink from 10-31 12:14 UTC",
          "Iteration 5: Binance USD-M BTCUSDT / ETHUSDT aggTrades REST for the 10-31 12:00-13:00 development block",
          "Iteration 5: data-api activity (types REWARD, MAKER_REBATE, MERGE, REDEEM, SPLIT, CONVERSION, YIELD), VALIDATE week",
          "Iteration 5: Bybit BTCUSDT perp orderbook.200 daily archives (quote-saver.bycsi.com) 10-09..10-22, reduced to 100-ms buckets"]
S["brief_version"] = "2026-10-31"
S["sealed_from"] = {"H": 1792713600, "T0": 1793404800, "released_lots": [], "future_sealed_examined_until": "2026-10-31T00:00:00Z",
                    "calendar": "research/reverse_engineering/tools/sealed.py (key btc5m-bot)",
                    "development_after_H_used": [[1793404800, 1793426400], [1793448000, now_ts or 1793454000]]}
S["live_lab"] = [{"what": "Binance USD-M futures BTCUSDT + ETHUSDT bookTicker (price changes only) via tools/live.py Writer, feed btc5m_bnfut (code/rec_binance_fut.py; status file .cache/re/btc5m-bot/rec_binance_fut.status)", "start": 1793452284, "end": 1793488284}]
S["status"] = "continue"; S["wall_reason"] = ""
S["primary_metric"] = "presence_auc"
S["catalog"] = CATALOG
S["components"] = COMP
S["strategy_statement"] = STATEMENT
S["target_metrics"] = TM
S["target_metrics_notes"] = {"presence_unit": "BLOCK SECONDS (iteration 5): seconds without a Polygon block (1 in 3) cannot hold a fill; chain clock fitted per hour; 100% of VALIDATE fills inside; models retrained on BUILD block seconds (model_it5_blk_*). Gain +0.0554, 2-h block bootstrap 95% CI [0.0524, 0.0582], p < 0.0005; halves +0.055 / +0.055; wallets GF 0.8745/0.8098, XM 0.8927/0.825, DS 0.8571/0.8047. All-seconds unit (pre-registered in iteration 1): 0.9132 vs pure 0.8781 (+0.035, CI [0.0337, 0.0364]).",
                             "presence_baseline": "PURE market-activity model (iteration 5); the iteration 2-4 baseline 0.8889 contained Binance fair-value gaps",
                             "side": "window-level one-sided share 0.2% pooled (DS 0.2%, GF 3.1%, XM 24.3%): the side condition does not apply pooled; per-second side reported",
                             "price_within_tick": "taker fills vs the last implied ask from others' prints (last 2 VALIDATE hours); no public book history before 10-31",
                             "pnl_corr": "executable strict-fill replay (latency >= 2 s, observed liquidity); the volume proxy gives 0.439 / 0.414",
                             "selection": "size classes + cell score; baseline = size classes + pure market cell score"}
S["best"] = {"rule_id": "it5: block-second presence (model_it5_blk_full) + it5 side (Bybit book) + live-book price + B1 ladder check (code/final_rule.py)",
             "validate_metrics": dict(TM, presence_gain_over_pure_baseline=0.0554, presence_all_seconds=0.9132, presence_all_seconds_pure=0.8781, decision_aligned_presence=dp.get("k1"), b1_share_in_bursts=0.999, price_live_within_tick_n277=0.9321)}
S["hypotheses"] = [h for h in S.get("hypotheses", []) if h.get("id") not in {x["id"] for x in NEW_H}] + NEW_H
S["data_sources"] = [d for d in S.get("data_sources", []) if d not in NEW_DS] + NEW_DS
S["iterations"] = [it for it in S.get("iterations", []) if it.get("n") != 5] + [{
    "n": 5, "minutes": minutes, "best_validate_score": 0.9132, "pure_baseline": 0.8781, "gain": 0.0351, "block_seconds_presence": 0.8747, "block_seconds_pure_baseline": 0.8193, "block_seconds_gain": 0.0554, "side_accuracy": 0.7666, "price_live_within_tick": 0.9321,
    "families": ["presence unit = Polygon block seconds (chain clock)", "B1 calldata order reconstruction (pre-signed ladder)", "C2 copy trading strong form", "A8 outages", "live Binance futures quote recorder", "C1 wallet coordination + fourth wallet", "baseline correction (pure market)",
                 "D1 decision-aligned presence", "A3 perp order book (Bybit) in side and presence", "B3b time stop vs price range",
                 "B4/B7/B8 activity types", "A7 live lab books + RTDS + Binance REST"]}]
S["frozen_rule"] = "code/final_rule.py (iteration 5: it4b presence models, side model_it5_side_book.txt, decision-aligned presence model_it5_dp_k1_*.txt with the pure baseline, live-book price when recordings exist, B1 ladder check)"
S["target_reached"] = False
json.dump(S, open(f"{R}/state.json", "w"), indent=1, default=str)
print("state.json updated", len(S["catalog"]), "catalog items;", sum(1 for v in CATALOG.values() if v["status"] == "open"), "open")
