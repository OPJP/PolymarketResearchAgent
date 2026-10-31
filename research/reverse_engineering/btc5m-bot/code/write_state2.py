"""Iteration 2: update state.json (append hypotheses, data sources and the iteration entry; set best)."""
import json, os, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
R = _ROOT + "/research/reverse_engineering/btc5m-bot"
st = json.load(open(f"{R}/state.json"))
pres = json.load(open(f"{R}/results_presence_iter2.json"))
side = json.load(open(f"{R}/results_side_iter2.json"))
outc = json.load(open(f"{R}/results_outcome_iter2.json"))
minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 58
p = pres["spot_tape:y"]
best = {"rule_id": "H8b-spot+tape-it2 (retrained locally)", "validate_metrics": {
    "presence_auc": p["auc"], "presence_auc_taker": pres["spot_tape:yT"]["auc"], "presence_auc_maker": pres["spot_tape:yM"]["auc"],
    "presence_by_wallet": p["by_wallet"], "at_p0.30": p["at_0.30"],
    "co_occurrence_baseline_auc": pres["market_only:y"]["auc"], "gain_over_baseline": round(p["auc"] - pres["market_only:y"]["auc"], 4),
    "spot_only_auc": pres["spot_only:y"]["auc"], "with_own_state_auc": pres["spot_tape_own:y"]["auc"],
    "side_accuracy_any": side["y"]["models"]["spot_tape"]["acc"], "side_accuracy_taker": side["yT"]["models"]["spot_tape"]["acc"],
    "side_market_only_baseline": side["y"]["models"]["market_only"]["acc"], "side_favourite_baseline": side["y"]["rules"]["favourite"][0],
    "side_with_own_state": side["y"]["models"]["spot_tape_own"]["acc"], "outcome": outc}}
st["best"] = best
st["hypotheses"] += [
    {"id": "H12", "family": "inventory balancing (own state)", "description": "Side = the outcome the cluster holds less of in the window",
     "validate_metrics": {"taker_quiet_buys_less_held": 0.542, "taker_moving": 0.52, "side_model_own_only": side["y"]["models"]["own_only"]["acc"]}, "verdict": "rejected"},
    {"id": "H13", "family": "regime decomposition (quiet vs moving Binance)", "description": "Taker orders split by the visible 3-s Binance move (<0.5 bp = quiet)",
     "validate_metrics": {"quiet_share_taker_orders": 0.67, "net_c_per_share_quiet": -0.86, "net_c_per_share_moving": 1.63, "gross_c_quiet": 0.63, "gross_c_moving": 3.12},
     "verdict": "supported: two regimes, one order type; quiet volume is rebate-driven with a weak side signal"},
    {"id": "H14", "family": "anticipation / information source", "description": "Side vs FUTURE Binance moves when the past (incl. non-PIT seconds) is flat",
     "validate_metrics": {"agree_future_3s_flat_past": 0.537, "agree_future_10s": 0.542, "exactly_flat_past_3s": 0.531, "placebo": 0.5},
     "verdict": "supported: the bot has a weak signal that leads Binance spot"},
    {"id": "H15", "family": "sub-second Binance spot (aggTrades, OFI)", "description": "ms price moves and aggressor-signed volume before the order",
     "validate_metrics": {"pm_[s-2,s-1)": 0.636, "pm_[s-1,s)_nonPIT": 0.568, "quiet_pm_[s-1,s)": 0.516, "ofi_2s": 0.59},
     "verdict": "rejected as the missing signal: information horizon ends ~1 s before the block; OFI weaker than price"},
    {"id": "H16", "family": "alternative reference feed: Binance USD-M futures", "description": "Futures aggTrades (2026-10-15, BUILD) moves before the order",
     "validate_metrics": {"BUILD_day_agree_[s-3,s-2)": 0.648, "quiet_spot_subset": 0.596, "spot_klines_quiet_subset": 0.5825},
     "verdict": "small gain in quiet-spot periods; not the missing signal (only one BUILD day tested)"},
    {"id": "H17", "family": "dedicated side model", "description": "LightGBM side classifier on one-sided seconds (spot, tape, own state)",
     "validate_metrics": {k: v["acc"] for k, v in side["y"]["models"].items()}, "verdict": "66.8%; +own state 67.3%; ceiling with non-PIT klines 68.0%"},
    {"id": "H18", "family": "Up/Down pairing", "description": "Quiet orders are halves of simultaneous Up+Down pairs",
     "validate_metrics": {"opp_order_same_second": 0.30, "uniform_expectation": 0.16, "within_2s": 0.634, "uniform_2s": 0.57}, "verdict": "rejected (bursty both-sided activity, not pairs)"},
]
st["data_sources"] += [
    "Iteration 2 (local): chain own fills 2026-10-09..H re-fetched (483,048 logs), Gamma 4,032 windows, Binance 1-s 10-08..H-1, data-api taker tapes for all 4,032 windows",
    "Binance spot BTCUSDT aggTrades REST, 32 sampled hours (16 BUILD, 16 VALIDATE)",
    "Binance USD-M futures BTCUSDT aggTrades archive 2026-10-15 (BUILD)",
]
st["iterations"].append({"n": 2, "minutes": minutes, "best_validate_score": p["auc"],
    "families": ["inventory balancing", "regime decomposition / edge by regime", "anticipation lead-lag", "sub-second spot + order flow", "futures reference feed", "dedicated side model", "pairing", "wallet division", "time of day"]})
st["status"] = "continue"; st["wall_reason"] = ""
st["frozen_rule"] = "code/final_rule.py uses model_it2_spot_tape_{y,yT,yM}.txt, model_it2_market_only_y.txt, model_it2_spot_tape_own_y.txt"
st["target_reached"] = False
json.dump(st, open(f"{R}/state.json", "w"), indent=1)
print("state updated; best presence", p["auc"])
