"""Examiner round 2: assemble results/exam_r2.json from the per-test result files (no number typed by hand)."""
from __future__ import annotations

import json
import time

from r2_common import RES

L = lambda n: json.loads((RES / n).read_text())


def r(x, k=4):
    return round(float(x), k) if isinstance(x, (int, float)) and x is not None else x


def main():
    s0, sc, ev, mt = L("exam_r2_step0.json"), L("exam_r2_scope.json"), L("exam_r2_evaluate.json"), L("exam_r2_metrics.json")
    sel, rp, tr, per = L("exam_r2_selection.json"), L("exam_r2_replay.json"), L("exam_r2_truncation.json"), L("exam_r2_persistence.json")
    r7, oc, sn, dg, rf = L("exam_r2_price_r7.json"), L("exam_r2_onchain.json"), L("exam_r2_side_null.json"), L("exam_r2_diagnosis.json"), L("exam_r2_refit_check.json")
    ds = L("exam_r2_diag_sizes.json")
    P, S, Pr = mt["presence"], mt["side"], mt["price"]
    x5 = rp["5m"]["r8c_full_L2_Q62"]
    out = {
        "exam_round": 2, "lot": "f1", "strategy": "directional-maker", "rule": "R8c (code/final_rule.py, frozen; iteration 17-18)",
        "now_ts": int(time.time()),
        "intervals": s0["lot"], "half_cut_ts": s0["cut_ts"], "half_cut_utc": s0["cut_utc"],
        "sample": {"btc5m_windows": s0["btc5m_windows"], "btc15m_windows": s0["btc15m_windows"],
                   "btc_5m_15m_scheduled_not_listed": len(s0["btc_5m_15m_not_listed"]),
                   "cluster_trades_in_lot_units": sc["pooled"]["trades"], "cluster_usd": sc["pooled"]["usd"],
                   "btc5m_maker_fills": ev["cluster_maker_fills"], "btc5m_taker_fills": ev["cluster_taker_fills"],
                   "btc15m_maker_fills": ev["btc15m"]["cluster_maker_fills"]},
        "target_met": False,
        "criteria": {"match": "fail", "backtest": "fail", "replicable": "fail", "persists": "fail"},
        "components": {"selection": "fail", "timing": "fail", "side": "partial", "price": "partial", "size": "fail", "exit": "partial"},
        "metrics": {
            "scope": {"coverage_fills": r(sc["pooled"]["share_trades_universe"]), "coverage_usd": r(sc["pooled"]["share_usd_universe"]),
                      "coverage_abs_pnl": r(sc["pooled"]["share_abs_pnl_universe"]),
                      "halves": {h: [r(sc["halves"][h]["share_trades_universe"]), r(sc["halves"][h]["share_abs_pnl_universe"])] for h in ("early", "late")},
                      "per_wallet": {n: [r(v["share_trades_universe"]), r(v["share_abs_pnl_universe"])] for n, v in sc["per_wallet"].items()}},
            "presence_btc5m": {"auc": r(P["pooled"]["p_rule"]), "re_activity_baseline": r(P["pooled"]["p_activity"]),
                               "examiner_activity_baseline": r(P["pooled"]["x_act_ext"]), "examiner_activity_plus_clock": r(P["pooled"]["x_act_clock"]),
                               "gain_over_stronger": r(P["pooled"]["gain"]), "gain_ci95_2h_blocks": [r(x) for x in P["pooled"]["gain_ci95"]],
                               "gain_p_one_sided": r(P["pooled"]["gain_p_le0"]), "with_own_inventory": r(P["pooled"]["p_own"]),
                               "halves": {h: {"auc": r(P[h]["p_rule"]), "baseline": r(P[h]["p_activity"]), "gain": r(P[h]["gain"])} for h in ("early", "late")},
                               "per_wallet": {n: {"auc": r(v["all"]["p_rule"]), "baseline": r(v["all"]["p_activity"]), "early": r(v["early"]["p_rule"]),
                                                  "late": r(v["late"]["p_rule"])} for n, v in P["per_wallet"].items()}},
            "presence_btc15m": {"auc": r(ev["btc15m"]["presence"]["auc"]), "baseline": r(ev["btc15m"]["presence"]["auc_activity_baseline"])},
            "presence_union_5m_15m": {"auc": r(ev["union_btc5m_15m"]["presence_auc"]), "baseline": r(ev["union_btc5m_15m"]["presence_auc_activity_baseline"])},
            "selection_btc5m": {"auc": r(sel["rule"]["auc"]), "auc_strat_global": r(sel["rule"]["auc_strat_global"]),
                                "auc_strat_window": r(sel["rule"]["auc_strat_window"]), "recall": r(sel["rule"]["recall_at_theta"]),
                                "lift": r(sel["rule"]["lift_at_theta"]), "re_activity_baseline": r(sel["re_activity"]["auc"]),
                                "examiner_activity_baseline": r(sel["examiner_activity"]["auc"]),
                                "gain_over_stronger": r(sel["gain_over_examiner_activity"]["gain"]), "gain_ci95": [r(x) for x in sel["gain_over_examiner_activity"]["ci95"]],
                                "gain_p_one_sided": r(sel["gain_over_examiner_activity"]["p_le0"]),
                                "rotation_null_2h_2000": {k: r(v) for k, v in sel["rotation_null_2h"].items()},
                                "halves": {h: {k: r(v) for k, v in sel["rule"][h].items()} for h in ("early", "late")}},
            "side_btc5m_r8c": {"accuracy": r(S["pooled"]["r8c"]), "market_only_best": [S["pooled"]["best_market_only"][0], r(S["pooled"]["best_market_only"][1])],
                               "own_inventory_only_best": [S["pooled"]["best_own_inventory_only"][0], r(S["pooled"]["best_own_inventory_only"][1])],
                               "held_outcome_baseline": r(S["pooled"]["held"]), "mcnemar_vs_market_p": S["pooled"]["mcnemar_vs_market"]["p_one_sided"],
                               "rotation_null_2000": {"null_mean": r(sn["null_mean"]), "p": r(sn["p"]), "p_early": r(sn["early"]["p"]), "p_late": r(sn["late"]["p"])},
                               "halves": {h: r(S[h]["r8c"]) for h in ("early", "late")}, "per_wallet": {n: r(v["r8c"]) for n, v in S["per_wallet"].items()},
                               "per_wallet_half": {n: r(v["r8c"]) for n, v in S["per_wallet_half"].items()},
                               "one_sided_windows_share": r(S["one_sided_windows_share_95"]), "evaluate_r8c": r(ev["side_state_machine"]["r8c_no_own_state"])},
            "side_btc15m_r8c": {"accuracy": r(ev["btc15m"]["side_state_machine"]["r8c_no_own_state"]),
                                "cheaper": r(ev["btc15m"]["side_state_machine"]["cheaper"]), "favourite": r(ev["btc15m"]["side_state_machine"]["favourite"])},
            "price_btc5m": {"r7_frozen_clock": r(r7["5m"]["r7"]["pooled"]), "r7_halves": {k: r(v) for k, v in r7["5m"]["r7"]["halves"].items()},
                            "r7_per_wallet": {k: r(v) for k, v in r7["5m"]["r7"]["per_wallet"].items()},
                            "r7_per_wallet_half": {k: r(v) for k, v in r7["5m"]["r7"]["per_wallet_half"].items()},
                            "block_clock": r(Pr["pooled"]["rule_block_clock"]), "inblock_all": r(r7["5m"]["pooled_inblock"]),
                            "match_clock": {k: r(v) for k, v in Pr["pooled"]["on_match_clock"].items()},
                            "union_r7": r(ev["union_btc5m_15m"]["price_within_0.01_r7"]), "btc15m_inblock": r(r7["15m"]["pooled_inblock"]),
                            "inblock_independent_sample_0612": oc["inblock_check_0612"]},
            "outcome_btc5m": {"pearson": r(x5["corr_cluster_windows"][0]), "spearman": r(x5["corr_cluster_windows"][1]),
                              "perm_p_2000": [r(x) for x in x5["corr_perm_p_cluster_windows"]],
                              "halves": {"early": [r(x) for x in x5["corr_early"]], "late": [r(x) for x in x5["corr_late"]]},
                              "per_wallet": {n: [r(x) for x in v["all"]] for n, v in x5["per_wallet_corr"].items()},
                              "re_executable_variant": [r(x) for x in rp["5m"]["re_exec_full_L2_Q62"]["corr_cluster_windows"]],
                              "btc15m": [r(x) for x in rp["15m"]["r8c_clean_L2_Q62"]["corr_cluster_windows"]]},
            "backtest_btc5m_strict_L2_slack2_Q62": {"pnl": x5["pnl"], "usd": x5["usd"], "return": r(x5["return"]), "t": r(x5["t_per_window"]),
                                                    "p_profit_one_sided": r(x5["p_profit_t_one_sided"]), "block_boot_p_le0": r(x5["p_le0_block_boot"]),
                                                    "return_ci95": [r(x) for x in x5["return_ci95"]], "early": r(x5["return_early"]), "late": r(x5["return_late"]),
                                                    "latency5": r(rp["5m"]["r8c_full_L5_Q62"]["return"]), "q500": r(rp["5m"]["r8c_full_L2_Q500"]["return"]),
                                                    "clean_flow": r(rp["5m"]["r8c_clean_L2_Q62"]["return"]), "re_executable": r(rp["5m"]["re_exec_full_L2_Q62"]["return"])},
            "backtest_btc15m": {"return": r(rp["15m"]["r8c_clean_L2_Q62"]["return"]), "p_profit_one_sided": r(rp["15m"]["r8c_clean_L2_Q62"]["p_profit_t_one_sided"])},
            "wallet_return_same_markets": {"btc5m_maker_pnl": rp["5m"]["wallet_maker_pnl"], "btc5m_maker_usd": rp["5m"]["wallet_maker_usd"],
                                           "btc5m_maker_return": r(rp["5m"]["wallet_maker_return"]), "block_boot_p_le0": r(rp["5m"]["wallet_maker_return_p_le0"]),
                                           "by_half": rp["5m"]["wallet_maker_pnl_by_half"], "btc15m_return": r(rp["15m"]["wallet_maker_return"]),
                                           "all_lot_trades_pnl": sc["pooled"]["pnl"], "all_lot_trades_pnl_halves": {h: sc["halves"][h]["pnl"] for h in ("early", "late")}},
            "persistence": {n: {k: r(per[n]["persistence"]["d_economic_pnl"][k]["p_value"]) for k in ("recent", "decline", "late_decline", "trend")}
                            for n in ("momoney", "almach", "bosona")},
            "persistence_cluster_last_14_days": per["cluster_last_14_days"],
        },
        "leakage": {"truncation": tr, "onchain_role": oc["role_check"], "refit_reproduces_frozen_models": rf},
        "diagnosis_first_half": dg, "diagnosis_sizes_first_half": ds,
        "evaluate_frozen_output_file": "results/exam_r2_evaluate.json",
    }
    (RES / "exam_r2.json").write_text(json.dumps(out, indent=1, default=str))
    print("ok", len(json.dumps(out)))


if __name__ == "__main__":
    main()
