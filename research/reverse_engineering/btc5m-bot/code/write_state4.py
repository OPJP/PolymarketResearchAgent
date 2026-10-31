"""Iteration 4: update state.json (best rule, new hypotheses, data sources, iteration entry).
Usage: python write_state4.py <minutes> <status>"""
import json, os, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
R = _ROOT + "/research/reverse_engineering/btc5m-bot"
st = json.load(open(f"{R}/state.json"))
minutes = float(sys.argv[1]); status = sys.argv[2]
L = lambda n: json.load(open(f"{R}/{n}"))
m4, m4b = L("results_iter4_models.json"), L("results_iter4_models_four.json")
sel = L("results_selection_iter4_it4b.json"); outc = L("results_outcome_iter4_it4b.json"); osh = L("results_outcome_iter4_shares.json")
nd = L("results_net_diag_iter4.json"); eth = L("results_eth_iter4.json"); alts = L("results_alts_iter4.json")
ll = L("results_eth_leadlag_iter4.json"); cb = L("results_coinbase_deribit_iter4.json"); wall = L("results_wall_test_iter4_val_side_it4b.json")
ev = L("results_eth_venues_iter4.json")
lag = L("results_side_lag_iter4.json") if os.path.exists(f"{R}/results_side_lag_iter4.json") else None
P = m4b["presence"]; S = m4b["side"]
best = {"rule_id": "H30+H36 crossasset-it4b with lagged side segments (code/final_rule.py, USE_ALTS=True, ALT_SET='four', models code/model_it4b_*.txt, side model_it4b_side_lag.txt)",
        "validate_metrics": {
            "presence_auc": P["auc_any"], "presence_auc_taker": P["auc_taker"], "presence_auc_maker": P["auc_maker"], "presence_by_wallet": P["by_wallet"],
            "at_p0.30": P["at_0.30"], "co_occurrence_baseline_auc": P["auc_market_only_baseline"],
            "gain_over_baseline": round(P["auc_any"] - P["auc_market_only_baseline"], 4), "with_own_state_auc": P["auc_with_own"],
            "iteration3_rule_auc_same_rows": P["auc_it3s_same_rows"], "eth_only_rule_auc": P["auc_it4_same_rows"],
            "side_accuracy_any": lag["side_lag"] if lag else S["side_it4b"]["acc"], "side_accuracy_taker": lag["taker_lag"] if lag else S["side_it4b"]["taker"],
            "side_accuracy_without_lag_segments": S["side_it4b"]["acc"], "side_lag_mcnemar": lag["mcnemar"] if lag else None,
            "side_accuracy_six_series_flat": S["side_it4b"]["nomove"], "side_accuracy_moving": S["side_it4b"]["moving"],
            "side_share_six_series_flat": S["share_nomove"], "side_it3s_same_rows": S["side_it3s"]["acc"], "side_eth_only": S["side_it4"]["acc"],
            "side_mcnemar_vs_it3s": S["mcnemar_it4_vs_it3s"], "side_market_only_baseline": 0.6323, "side_favourite_baseline": 0.459,
            "outcome": {"primary": "shares", "shares": osh["shares_per_outcome"], "netflow": outc["netflow"], "soft_side": outc["soft_side"],
                        "soft_side_it3s_same_pipeline": outc["soft_side_it3s_same_pipeline"], "window_total_shares_corr": osh["window_total_shares_corr"],
                        "wallet_return_before_rebates": outc["wallet_return_before_rebates"], "net_position_diagnostic": nd,
                        "strict_fill_backtest": L("results_strict_backtest_iter4.json")},
            "selection": sel}}
st["best"] = best
st["hypotheses"] += [
    {"id": "H27", "family": "Coinbase BTC-USD and Deribit BTC-PERPETUAL (time-bounded REST) for the no-move residual",
     "description": "Coinbase Advanced Trade public market trades (start/end) and history.deribit.com trades for 12 sampled VALIDATE hours; agreement with the side in seconds where none of the six archived BTC series moved, and vs the it3s side model",
     "validate_metrics": cb, "verdict": "rejected: no-move agreement 56.6% (Coinbase) / 62.0% (Deribit), but right only 51.3% / 51.1% where they disagree with the model"},
    {"id": "H28", "family": "cross-asset lead: Binance ETHUSDT perpetual", "description": "Does the ETH perp move explain the side when no BTC feed moved?",
     "validate_metrics": {k: eth[k] for k in ("share_nomove", "E3000", "Erel3000", "E3000_ge1bp_nomove_vs_model", "beta_eth_on_btcfut_3s")},
     "verdict": "supported: 63.2% in no-move seconds (n=16,333), 79.1% when |ETH| >= 1 bp; right 69.5% where it disagrees with the it3s model"},
    {"id": "H29", "family": "other alt perpetuals (SOL, XRP, DOGE)", "description": "Agreement in seconds where neither the six BTC series nor ETH moved (3 sampled VALIDATE days)",
     "validate_metrics": alts, "verdict": "supported (small): 53.7-55.5% (z 5-7), 64-71% at >= 2 bp"},
    {"id": "H30", "family": "cross-asset features in the frozen rule (behaviour cloning)", "description": "it4 = + ETH perp PIT features; it4b = + SOL, XRP, DOGE and BTC-equivalent alt composites (BETA from BUILD)",
     "validate_metrics": {"it4": {"presence": m4["presence"]["auc_any"], "side": m4["side"]["side_it4"]["acc"]}, "it4b": {"presence": P["auc_any"], "side": S["side_it4b"]["acc"]},
                          "top_side_features": m4b["side_top_gain"][:8]},
     "verdict": "supported: presence 0.9095 -> 0.9132, side 73.2% -> 75.3% (McNemar p ~ 2e-82); best rule"},
    {"id": "H31", "family": "ETH lead-lag at 0.5-s resolution", "description": "Lead-lag of 0.5-s returns ETH vs BTC perp; side agreement with the ETH move in half-second windows",
     "validate_metrics": ll, "verdict": "supported: ETH leads BTC (corr ETH->BTC 0.218 vs BTC->ETH 0.120); the bot's side peaks on the ETH move in [s-3, s-2), same lag as BTC venues"},
    {"id": "H32", "family": "side model capacity", "description": "900 rounds, learning rate 0.03, 63 leaves vs 300 rounds / 31 leaves",
     "validate_metrics": {"big": S["side_it4b_big"]["acc"], "standard": S["side_it4b"]["acc"]}, "verdict": "rejected: no gain (75.3% both)"},
    {"id": "H33", "family": "information-wall test with the cross-asset model", "description": "Bot side vs our it4b PIT model at predicting future Binance futures moves, all seconds and seconds flat on six BTC series and ETH",
     "validate_metrics": {k: wall[k] for k in ("all", "flat_six_series_and_eth_PIT")},
     "verdict": "no wall: overall our model predicts the future better than the bot's side; in the 18.7% flat seconds a small residual remains (bot 53.0% vs ours 51.3% for the next 0-2 s; z 5.7 vs 1.2)"},
    {"id": "H34", "family": "outcome proxies: net-flow and volume regressions", "description": "LightGBM regressions (BUILD) of the signed net share flow per second and of shares per cell; buy them at the last implied ask",
     "validate_metrics": {"netflow": outc["netflow"], "shares": osh["shares_per_outcome"], "diagnostic": nd},
     "verdict": "PnL corr 0.434 / 0.439 (< 0.5); volume and side errors limit the net position about equally (oracle volume x model side 0.555)"},
    {"id": "H37", "family": "strict-fill backtest (observed liquidity, latency >= 2 s)", "description": "30-share BUY limits at the last implied ask of the side-model outcome when p >= 0.30; fills only against other traders' taker BUY prints in [s+1, s+3] at price <= limit (capture 1.0)",
     "validate_metrics": L("results_strict_backtest_iter4.json"), "verdict": "rule loses 1.6% before rebates (+0.1% with a 50% fee rebate); per-window PnL corr 0.18 (wallet +0.17% before rebates)"},
    {"id": "H35", "family": "ETH on other venues (OKX swap, Binance spot, Bybit spot)", "description": "Do other ETH venues add to the it4b side model (2 sampled VALIDATE days)?",
     "validate_metrics": ev, "verdict": "rejected: right 33-50% where they disagree with the model"},
]
if lag:
    st["hypotheses"].append({"id": "H36", "family": "decision-time alignment (explicit lagged segments)", "description": "Side model + [s-3, s-2) and [s-4, s-3) segments for ten series and composites (derived from the PIT windows)",
                             "validate_metrics": lag, "verdict": ("supported (small)" if lag["side_lag"] > lag["side_it4b"] + 0.002 else "rejected: no material gain") + f": {lag['side_lag']} vs {lag['side_it4b']}"})
st["data_sources"] += [
    "Iteration 4: Binance USD-M ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT perpetual aggTrades daily archives (checksummed) 2026-10-09..10-22 (.cache/re/btc5m-bot/venues/{eth,sol,xrp,doge}fut)",
    "Iteration 4: Coinbase BTC-USD trades (Advanced Trade public market-trades, time-bounded start/end) and Deribit BTC-PERPETUAL trades (history.deribit.com, time-bounded), 12 sampled VALIDATE hours",
    "Iteration 4: OKX ETH-USDT-SWAP, Binance ETHUSDT spot aggTrades, Bybit ETHUSDT spot daily archives for 2026-10-19 and 10-21 (OKX files are UTC+8 days)",
]
fams = ["Coinbase + Deribit BTC trades (time-bounded REST) for the no-move residual", "cross-asset lead: ETH perpetual",
        "other alt perpetuals (SOL, XRP, DOGE) and alt composites", "cross-asset features in the frozen rule", "ETH lead-lag at 0.5 s",
        "side model capacity", "information-wall test with the cross-asset model", "outcome: net-flow and volume regressions",
        "ETH on other venues", "decision-time alignment (lagged segments)", "strict-fill backtest"]
st["iterations"].append({"n": 4, "minutes": minutes, "best_validate_score": P["auc_any"], "co_occurrence_baseline": P["auc_market_only_baseline"],
                         "side_accuracy": lag["side_lag"] if lag else S["side_it4b"]["acc"], "pnl_corr": osh["shares_per_outcome"]["pnl_corr_pearson"], "families": fams})
st["frozen_rule"] = "code/final_rule.py (iteration 4: USE_VENUES=True, SIX_SERIES=True, USE_ALTS=True, ALT_SET='four'; models model_it4b_*.txt; side model_it4b_side_lag.txt; outcome primary = shares)"
st["status"] = status; st["target_reached"] = False
st["wall_reason"] = "" if status != "wall" else st.get("wall_reason", "")
json.dump(st, open(f"{R}/state.json", "w"), indent=1)
print("state.json updated", len(st["hypotheses"]), "hypotheses", len(st["iterations"]), "iterations")
