"""Iteration 3: update state.json (best rule, new hypotheses, data sources, iteration entry).
Usage: python write_state3.py <minutes> <best_kind: six|venues> <status>"""
import json, os, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
R = _ROOT + "/research/reverse_engineering/btc5m-bot"
st = json.load(open(f"{R}/state.json"))
minutes = float(sys.argv[1]); kind = sys.argv[2]; status = sys.argv[3]
fut = json.load(open(f"{R}/results_iter3_models.json"))
ven = json.load(open(f"{R}/results_iter3_venues.json"))
best_r = json.load(open(f"{R}/results_iter3_{kind}.json"))
sel = json.load(open(f"{R}/results_selection_iter3.json"))
outc = json.load(open(f"{R}/results_outcome_iter3_{'six' if kind == 'six' else 'ven'}.json"))
wall1 = json.load(open(f"{R}/results_wall_test_iter3.json")); wall2 = json.load(open(f"{R}/results_wall_test_iter3_val_side_it3v.json"))
venues = json.load(open(f"{R}/results_venues_iter3.json"))
P = best_r["presence"]; S = best_r["side"]
best = {"rule_id": f"H23-multivenue-{kind}-it3 (code/final_rule.py, models code/model_{'it3s' if kind == 'six' else 'it3v'}_*.txt)",
        "validate_metrics": {
            "presence_auc": P["auc_any"], "presence_auc_taker": P["auc_taker"], "presence_auc_maker": P["auc_maker"], "presence_by_wallet": P["by_wallet"],
            "at_p0.30": P["at_0.30"], "co_occurrence_baseline_auc": fut["presence"]["co_occurrence_baseline"],
            "gain_over_baseline": round(P["auc_any"] - fut["presence"]["co_occurrence_baseline"], 4), "with_own_state_auc": P["auc_with_own"],
            "iteration2_rule_auc": fut["presence"]["auc_any_it2"], "futures_only_rule_auc": fut["presence"]["auc_any_fut"], "three_venue_rule_auc": ven["presence"]["auc_any"],
            "side_accuracy_any": S["side_model_venues"]["acc"], "side_accuracy_taker": S["taker_side_model_venues"],
            "side_accuracy_spot_3s_zero": S["side_model_venues"]["acc_spot_r3_zero"], "side_accuracy_binance_flat": S["side_model_venues"]["acc_binance_flat"],
            "side_accuracy_moving": S["side_model_venues"]["acc_moving"], "side_market_only_baseline": fut["side"]["market_only"]["acc"],
            "side_favourite_baseline": fut["side"]["favourite"]["acc"], "side_futures_only_model": fut["side"]["side_model_fut"]["acc"],
            "outcome": outc, "selection": sel}}
st["best"] = best
st["hypotheses"] += [
    {"id": "H20", "family": "alternative reference feed: Binance USD-M futures in the frozen rule", "description": "PIT futures aggTrades features (moves 0.25-10 s, OFI, since-last-print move, basis-adjusted futures fair value) in presence and side models",
     "validate_metrics": {"presence_auc": fut["presence"]["auc_any_fut"], "side_model": fut["side"]["side_model_fut"]["acc"], "side_spot_r3_zero": fut["side"]["side_model_fut"]["acc_spot_r3_zero"]},
     "verdict": "supported: presence 0.896 -> 0.904, side 67.1% -> 70.3%"},
    {"id": "H21", "family": "information wall test (anticipation beyond public PIT data)", "description": "Bot side vs our best PIT side model in predicting FUTURE Binance futures moves when Binance futures and spot were flat up to the horizon",
     "validate_metrics": {"futures_only_model": wall1["flat_PIT_futures_and_spot"], "three_venue_model": wall2["flat_PIT_futures_and_spot"]},
     "verdict": "with Binance-only features the bot anticipates futures (z=17.6 vs our 2.3); with OKX+Bybit features most of it is explained (z 12.5 vs ours 12.6): cross-venue information, not a private feed; small residual remains"},
    {"id": "H22", "family": "other perpetual venues (OKX swap, Bybit perp)", "description": "Bot side vs OKX / Bybit moves when Binance is flat",
     "validate_metrics": venues, "verdict": "supported: Binance-flat side agreement 56% (OKX) / 60% (Bybit); 75-82% when the venue moved >= 0.5 bp"},
    {"id": "H23", "family": "multi-venue composite trigger (behaviour cloning)", "description": "Presence + side models with Binance futures, OKX swap, Bybit perp (and in 'six': Binance spot aggTrades, Bybit spot, OKX spot) and composites (mean / largest venue move)",
     "validate_metrics": {"three_venues": {"presence": ven["presence"]["auc_any"], "side": ven["side"]["side_model_venues"]["acc"]}, "six_series": {"presence": best_r["presence"]["auc_any"], "side": best_r["side"]["side_model_venues"]["acc"]} if kind == "six" else None,
                          "top_side_features": best_r["side_top_gain"][:5]},
     "verdict": "supported: the bot fires on whichever venue moves first; best rule"},
    {"id": "H25", "family": "Kraken XBT/USD (Chainlink input; REST paged by time)", "description": "Does Kraken explain the side in seconds when none of the six archived series moved (<= 0.1 bp over the PIT 3 s)?",
     "validate_metrics": json.load(open(f"{R}/results_kraken_iter3.json")), "verdict": "rejected: 49.9% agreement in no-move seconds (6 sampled VALIDATE hours)"},
    {"id": "H24", "family": "sizing rule v3 (full orders + partial fills)", "description": "Size classes decoded on BUILD: full orders {30,50,60,100}, partial taker fills {5,...,25}; flag = full OR (partial AND p >= 0.30)",
     "validate_metrics": sel, "verdict": "selection target met on VALIDATE (AUC 0.865, recall 67.6% at lift 4.6); co-occurrence baseline 0.852"},
]
st["data_sources"] += [
    "Iteration 3: Binance USD-M futures aggTrades archives 2026-10-09..11 (all 14 BUILD+VALIDATE days now)",
    "Iteration 3: OKX BTC-USDT-SWAP and BTC-USDT spot daily trade archives (static.okx.com, UTC+8 files) 2026-10-09..10-22 files; the 10-23 file extends past H and is never loaded (last 8 h of VALIDATE without OKX)",
    "Iteration 3: Bybit BTCUSDT linear perp and spot daily trade archives (public.bybit.com) 2026-10-09..10-22",
    "Iteration 3: Binance spot BTCUSDT aggTrades daily archives (checksummed) 2026-10-09..10-22",
    "Iteration 3: Kraken XBTUSD REST trades (paged by time) for 6 sampled VALIDATE hours (.cache/re/btc5m-bot/venues/kraken)",
]
st["iterations"].append({"n": 3, "minutes": minutes, "best_validate_score": P["auc_any"], "co_occurrence_baseline": fut["presence"]["co_occurrence_baseline"],
                         "families": ["Binance futures in the frozen rule", "information-wall test vs best PIT model", "other perpetual venues (OKX, Bybit)",
                                      "spot venues (Binance aggTrades, Bybit, OKX)", "multi-venue composite trigger", "sizing rule v3 (full + partial size classes)", "outcome proxy variants", "Kraken (time-paged REST) for the no-trigger residual"]})
st["frozen_rule"] = f"code/final_rule.py (USE_VENUES=True, SIX_SERIES={kind == 'six'}) uses model_{'it3s' if kind == 'six' else 'it3v'}_all_{{y,yT,yM}}.txt, model_{'it3s' if kind == 'six' else 'it3v'}_all_own_y.txt, model_{'it3s' if kind == 'six' else 'it3v'}_side.txt, model_it2_market_only_y.txt (baseline), model_it2_spot_tape_y.txt (comparison)"
st["status"] = status; st["target_reached"] = status == "target_reached"
st["wall_reason"] = "" if status != "wall" else st.get("wall_reason", "")
json.dump(st, open(f"{R}/state.json", "w"), indent=1)
print("state updated", best["rule_id"], P["auc_any"])
