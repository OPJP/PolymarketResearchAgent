"""Examiner: write results/exam.json (verdict + key metrics) from results/exam_details.json."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "results"
d = json.loads((R / "exam_details.json").read_text())
ev, ind, lk = d["evaluate_official"], d["independent"], d["leakage"]
pr, sd, pc, wl, se = ind["presence"], ind["side"], ind["pnl_correlation"], ind["wallet_btc5m"], ind["selection_2h_rotation_200"]
P, F = ind["backtest_holdout"]["P_primary"], ind["backtest_forward_day"]
metrics = {
 "selection_auc": se["all"]["auc"], "selection_auc_strat_global": se["all"]["auc_strat_global"], "selection_auc_strat_window": se["all"]["auc_strat_window"],
 "selection_null_global_mean_sd": [se["all"]["rotation_null_2h_blocks"]["global_mean"], se["all"]["rotation_null_2h_blocks"]["global_sd"]],
 "selection_null_window_mean_sd": [se["all"]["rotation_null_2h_blocks"]["window_mean"], se["all"]["rotation_null_2h_blocks"]["window_sd"]],
 "selection_p": se["all"]["p"], "selection_z_global": se["all"]["z_global"], "selection_z_window": se["all"]["z_window"],
 "recall": se["all"]["recall_at_theta"], "lift": se["all"]["lift_at_theta"],
 "selection_activity_baseline_auc": se["activity"]["auc"], "selection_activity_baseline_strat_window": se["activity"]["auc_strat_window"],
 "selection_activity_baseline_recall_lift": [se["activity"]["recall_at_theta"], se["activity"]["lift_at_theta"]],
 "presence_auc": pr["auc_R2"], "co_occurrence_baseline": pr["auc_activity_baseline"], "presence_gain": pr["gain_over_baseline"],
 "presence_gain_ci95": pr["bootstrap_windows"]["gain_ci95"], "presence_auc_ci95": pr["bootstrap_windows"]["R2_ci95"],
 "presence_auc_with_own_inventory": pr["auc_R2_with_own_inventory"], "presence_auc_within_active_windows": pr["auc_R2_within_active_windows"],
 "presence_auc_window_oracle_ceiling": pr["auc_R2_with_window_oracle_ceiling"], "presence_auc_inputs_delayed_2s": ind["presence_inputs_delayed_2s"]["p_all_path_xwin"]["lag2"],
 "presence_auc_forward_day": pr["forward_days"]["auc_R2"], "presence_baseline_forward_day": pr["forward_days"]["auc_activity_baseline"],
 "side_accuracy": sd["accuracy"]["R2_higher_p"], "side_baseline": sd["accuracy"][sd["best_market_only"]], "side_baseline_name": sd["best_market_only"],
 "side_mcnemar_p": sd["mcnemar_vs_best"]["p_one_sided"], "side_n": sd["n_one_sided_bins"], "side_first_30s": sd["by_time"]["0-30s"],
 "price_within_tick": ind["price"]["within_1tick"], "price_exact": ind["price"]["exact"], "price_baseline_last_print_within_tick": ind["price"]["base_last_print_within_1tick"],
 "pnl_correlation": pc["expected_rule_pnl_vs_wallet_on_wallet_windows"]["pearson"], "pnl_correlation_spearman": pc["expected_rule_pnl_vs_wallet_on_wallet_windows"]["spearman"],
 "pnl_correlation_strict_backtest_vs_wallet": pc["strict_backtest_vs_wallet_all_windows"]["pearson"],
 "rule_return_strict": P["return_on_bought"], "rule_pnl_strict_usd": P["pnl"], "rule_usd_bought": P["usd_bought"], "rule_fills": P["fills"],
 "rule_return_t": P["per_window_t"], "rule_return_p": P["per_window_p_one_sided"], "rule_return_bootstrap_p": P["per_window_bootstrap_p"],
 "rule_forward_day_return": F["return_on_bought"], "rule_forward_day_p": F["per_window_p_one_sided"],
 "rule_return_optimistic_slack0": ind["backtest_holdout"]["slack_0_optimistic"]["return_on_bought"], "rule_return_at_touch": ind["backtest_holdout"]["at_touch_optimistic"]["return_on_bought"],
 "wallet_return": wl["maker_return"], "wallet_pnl_usd": wl["maker_pnl"], "wallet_usd": wl["maker_usd"], "wallet_return_p": wl["per_window_p_one_sided"],
 "wallet_forward_day_return": wl["forward_days"]["maker_return"],
 "cluster_total_pnl_holdout_8d": d["persistence"]["holdout_daily_tests"]["cluster"]["holdout_pnl"], "cluster_total_pnl_holdout_p": d["persistence"]["holdout_daily_tests"]["cluster"]["p"],
 "wallet_30d_p": {n: d["persistence"][n]["persistence"]["d_economic_pnl"]["recent"]["p_value"] for n in ("momoney", "almach", "bosona")},
 "wallet_late15_decline_p": {n: d["persistence"][n]["persistence"]["d_economic_pnl"]["late_decline"]["p_value"] for n in ("momoney", "almach", "bosona")},
}
(R / "exam.json").write_text(json.dumps({"metrics": metrics, "details_file": "results/exam_details.json"}, indent=1))
print(json.dumps(metrics, indent=0))
