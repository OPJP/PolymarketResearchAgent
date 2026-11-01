"""Examiner r1: assemble results/exam_r1.json from the component result files (no new computation)."""
import json, os, time
R = "research/reverse_engineering/btc5m-bot/results"
L = lambda n: json.load(open(f"{R}/{n}"))
s0, pres, sel, side, price, pnl, econ, agg, trc, tdc, act, per, dg = (L(x) for x in (
    "exam_r1_step0.json", "exam_r1_presence.json", "exam_r1_selection.json", "exam_r1_side.json", "exam_r1_price.json", "exam_r1_pnl.json",
    "exam_r1_econ.json", "exam_r1_evaluate_agg.json", "exam_r1_truncation.json", "exam_r1_trunc_dc.json", "exam_r1_activity.json",
    "exam_r1_persistence.json", "exam_r1_diagnosis.json"))
P = pres["block_second_unit"]; MSB = "RE_MSB(pres14 capture-aware, refit 10-17..19)"
tk = pnl["a_c1.0"]; tks = pnl["slack_c1.0"]
out = {
    "strategy": "btc5m-bot", "round": 1, "lot": "h1", "now_ts": int(time.time()),
    "lot_intervals": s0["intervals"], "windows_listed": s0["windows_listed"], "halves": s0["halves"], "power": s0["power"],
    "frozen_files_sha256_16": {"final_rule.py": "0523a66c6301e208", "dc_exam14.py": "70dd95647f78a02d", "dc_hazard14.py": "139e80a9af014dec",
                               "model_it5_blk_full.txt": "fa6925400582f737", "model_it14_dcside_spot.txt": "d366836254827a55"},
    "evaluate_run": {"chunks": agg["chunks"], "errors": agg["errors"], "windows": agg["windows"], "cluster_fills": agg["cluster_fills"],
                     "elapsed_s_total": agg["elapsed_s_total"], "peak_working_set_mb": agg["peak_mb_max"],
                     "per_chunk_target_metrics": agg["per_chunk_target_metrics"]},
    "metrics": {
        "coverage_fills": 1.0, "coverage_abs_pnl": 1.0, "windows_traded_share": round(econ["pool"]["windows"] / 1152, 4),
        "presence_block_seconds": {"auc_full": P["pooled"]["auc_full"], "baselines": {k: v for k, v in P["pooled"].items() if k not in ("auc_full", "by_wallet")},
                                   "strongest_baseline": pres["strongest_baseline_block_unit"], "gain_vs_strongest": pres["gain_bootstrap_block_unit"][MSB],
                                   "gain_vs_RE_pure": pres["gain_bootstrap_block_unit"]["RE_pure(model_it5_blk_pure)"],
                                   "gain_vs_own_MKTX": pres["gain_bootstrap_block_unit"]["own_MKTX"],
                                   "halves": {h: {"full": P[h]["auc_full"], "msb": P[h][MSB], "re_pure": P[h]["RE_pure(model_it5_blk_pure)"]} for h in ("first_half", "second_half")},
                                   "by_wallet": {w: {"full": P["pooled"]["by_wallet"][w]["full"], "msb": P["pooled"]["by_wallet"][w][MSB],
                                                     "re_pure": P["pooled"]["by_wallet"][w]["RE_pure(model_it5_blk_pure)"]} for w in ("GF", "XM", "DS")},
                                   "gain_vs_strongest_by_half_wallet": pres["gain_vs_strongest_by_half_wallet"],
                                   "recall_lift_at_0.30": pres["at_threshold_0.30_block_unit"], "window_permutation_null": pres["perm_null_full_block_unit"],
                                   "w4_w5_check": pres["w45_check"]},
        "presence_decision_aligned_slack_clean": pres["decision_aligned_unit_label_s_plus_1"],
        "presence_all_seconds": pres["all_seconds_unit"],
        "presence_decision_clock_reported": {k[-6:]: [v["presence_decision_clock_auc"], v["presence_decision_clock_baseline"]] for k, v in agg["per_chunk_target_metrics"].items()},
        "selection": sel,
        "side_decision_clock": {k: side[k] for k in ("orders_taker_unique", "orders_matched_to_capture", "accuracy_per_order", "halves", "by_wallet", "baselines",
                                                       "best_market_only", "best_own_inventory_only", "mcnemar_vs_best_market_only_p", "within_window_permutation_null",
                                                       "side_applicability", "one_sided_windows_side_acc")},
        "side_decision_clock_evaluate_agg": agg["side_decision_clock"], "side_block_clock_evaluate_agg": agg["side_block_clock"],
        "price": price,
        "pnl_tracker_frozen_conv_a_capture1": {k: tk[k] for k in ("fills", "pooled", "halves", "by_wallet", "by_wallet_halves", "rotation_null", "block_bootstrap",
                                                                   "rotation_null_by_wallet", "return_before_rebates", "return_with_50pct_fee_rebate", "return_halves_before_rebates")},
        "pnl_tracker_slack2_conv_capture1": {k: tks[k] for k in ("fills", "pooled", "halves", "by_wallet", "return_before_rebates", "return_with_50pct_fee_rebate")},
        "pnl_tracker_capture_0.5": {"a": pnl["a_c0.5"]["pooled"], "a_return": pnl["a_c0.5"]["return_before_rebates"]["return"],
                                    "slack": pnl["slack_c0.5"]["pooled"], "slack_return": pnl["slack_c0.5"]["return_before_rebates"]["return"]},
        "rule_by_day_conv_a": pnl["rule_by_day_a_c1.0"],
        "strict_30_share_replica_evaluate_agg": agg["strict30"],
        "wallet_own": pnl["wallet_own"], "wallet_economics": econ,
        "exit_activity": {"by_type": {w: v.get("by_type") for w, v in act["activity"].items()}, "sell_fills": sum(x["sell_rows"] for x in act["sell_fills"].values()),
                          "buy_fills": sum(x["buy_rows"] for x in act["sell_fills"].values())},
        "b1_share_signed_in_predicted_batches": agg["b1_share_signed_in_predicted_batches"],
        "persistence_wallets": {w: {sr: {k: (per[w]["derived"][sr][k].get("p_value") if isinstance(per[w]["derived"][sr][k], dict) else per[w]["derived"][sr][k])
                                         for k in ("recent", "decline", "late_decline", "trend", "cusum_break")}
                                    for sr in ("d_economic_pnl", "d_trade_pnl") if sr in (per[w]["derived"] or {})} for w in ("GF", "XM", "DS")},
    },
    "truncation": {"historical_pipeline": {k: v for k, v in trc.items() if k != "windows"}, "decision_clock_routes": tdc},
    "diagnosis_first_half": dg,
}
json.dump(out, open(f"{R}/exam_r1_metrics_bundle.json", "w"), indent=1, default=str)
print("ok", len(json.dumps(out, default=str)))
