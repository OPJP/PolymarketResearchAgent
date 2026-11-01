"""Examiner: assemble results/exam.json from the individual result files (no new computation)."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "results"
L = lambda n: json.loads((R / n).read_text())
ev, me, se, bt, bv = L("exam_evaluate_holdout.json"), L("exam_metrics_holdout.json"), L("exam_selection_holdout.json"), L("exam_backtest_holdout.json"), L("exam_backtest_validate.json")
tr, lag, oc, rf, rs, pe, mech, eq = L("exam_truncation.json"), L("exam_lag2.json"), L("exam_onchain_roles.json"), L("exam_refit_check.json"), L("exam_refit_sel.json"), L("exam_persistence_raw.json"), L("exam_mechanism.json"), L("exam_evaluate_equivalence.json")
P = bt["results"]["P_primary"]
out = {
 "strategy": "directional-maker", "wallets": ["0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed"],
 "rule": "R2-presence-lgbm-clean-path-xwin (code/final_rule.py, unchanged)",
 "holdout": {"start": 1792713600, "end": 1793404800, "days": me["days"], "windows": me["windows"], "bins": me["bins"],
             "cluster_maker_fills": ev["cluster_maker_fills"], "forward_day": "2026-10-30 (after as_of)",
             "note": "12 windows 2026-10-29 18:00-19:00 UTC had no in-window trades (market pause); included with no prints"},
 "evaluate_official": ev,
 "evaluate_equivalence_local_vs_adapter_2h": {k: {"presence_auc": v["presence"]["auc"], "price": v["price"], "tape_rows": v["tape_rows"]} for k, v in eq.items()},
 "independent": {"presence": me["presence"], "side": me["side"], "price": me["price"], "pnl_correlation": me["pnl_correlation"],
                 "wallet_btc5m": me["wallet"], "selection_2h_rotation_200": se, "presence_inputs_delayed_2s": lag,
                 "backtest_holdout": bt["results"], "backtest_forward_day": bt["forward_days_P_primary"], "backtest_theta": bt["theta"],
                 "backtest_validate_sanity": {k: {kk: v[kk] for kk in ("fills", "usd_bought", "pnl", "return_on_bought", "per_window_t", "per_window_p_one_sided")} for k, v in bv["results"].items()},
                 "mechanism_holdout": mech},
 "leakage": {"truncation_corruption": tr, "refit_presence_build_only": rf, "refit_selection_build_only": rs, "onchain_role_check": oc},
 "persistence": {k: pe[k] for k in ("momoney", "almach", "bosona") } | {"holdout_daily_tests": pe["holdout_daily_tests"], "as_of": pe["as_of"]},
}
(R / "exam_details.json").write_text(json.dumps(out, indent=1, default=str))
print("ok", len(json.dumps(out)))
