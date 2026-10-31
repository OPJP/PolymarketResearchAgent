"""Writes state.json from the iteration results files."""
import os as _os; _ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))  # repo root
import json, os
R = _ROOT + "/research/reverse_engineering/btc5m-bot"
ld = lambda n: json.load(open(f"{R}/{n}")) if os.path.exists(f"{R}/{n}") else {}
spot = ld("results_spot_model.json"); tape = ld("results_tape_model.json"); vm = ld("results_validate_metrics.json")
st = json.load(open(f"{R}/state.json"))
best_auc_spot = spot.get("y", {}).get("auc")
best_auc_tape = tape.get("spot_tape:y", {}).get("auc")
blend = tape.get("blend_rank_spot14d_spot_tape:y")
hyps = [
    {"id": "H1", "family": "execution/order-structure", "description": "Fixed-size BUY limit orders priced at the current best ask; unfilled remainder rests at that price", "validate_metrics": {"MT_orders_limit_eq_taker_price": 0.934, "order_kinds_T_MT_M": [0.73, 0.13, 0.14]}, "verdict": "supported"},
    {"id": "H2", "family": "maker/two-sided quoting", "description": "Independent resting bids (inventory-balanced MM around a fair value)", "validate_metrics": {"maker_fill_events_from_remainders": 0.385, "pure_resting_order_fill_span_median_s": 0}, "verdict": "open: 62% of maker fill events come from pure resting orders whose placement time is unobserved"},
    {"id": "H3", "family": "spot-reactive taker (latency)", "description": "Buys outcome o right after a Binance move toward o (1-3 s)", "validate_metrics": {"leadlag_peak_k": -3, "corr_peak": 0.0995, "univariate_auc_mxf3": 0.58, "univariate_auc_r2": 0.5726}, "verdict": "supported as the main timing signal; weak alone"},
    {"id": "H4", "family": "absolute fair-value edge", "description": "Buy when Binance FV - ask > theta", "validate_metrics": {"taker_price_minus_FV_median": -0.002, "gap_ask_univariate_auc_yT": 0.5134}, "verdict": "rejected as trigger"},
    {"id": "H5", "family": "strike definition", "description": "Strike = 60-s TWAP before the open (vs open price)", "validate_metrics": {"corr_limit_vs_FV_twap": 0.908, "corr_limit_vs_FV_open": 0.691}, "verdict": "TWAP strike supported"},
    {"id": "H6", "family": "multi-wallet coordination", "description": "Three wallets are parallel instances on the same signal", "validate_metrics": {"GF_orders_with_DS_order_same_token_2s": 0.818, "XM_with_DS": 0.828, "shared_tx_share": 0.0074}, "verdict": "supported"},
    {"id": "H7", "family": "behaviour cloning, spot-only PIT", "description": "LightGBM on Binance-only PIT features, BUILD 14 days", "validate_metrics": {k: spot.get(k, {}).get("auc") for k in ("y", "yT", "yM", "yGF")}, "verdict": "presence AUC %.3f" % (best_auc_spot or 0)},
    {"id": "H8", "family": "behaviour cloning, spot + others' tape PIT", "description": "LightGBM on Binance + other traders' tape PIT features (cluster prints and prints against the cluster removed), BUILD = windows with tapes 10-09..16", "validate_metrics": {k: (v.get("auc") if isinstance(v, dict) else v) for k, v in tape.items() if k.startswith("spot_tape") or k.startswith("blend") or k.startswith("spot14d")}, "verdict": "see NOTES"},
    {"id": "H9", "family": "information source / lead-lag", "description": "Does the bot act before public signals?", "validate_metrics": {"binance_corr_k_minus3": 0.0995, "binance_corr_k_plus1": 0.0239}, "verdict": "acts after Binance moves (2-3 s before block ts); faster feeds (Binance futures, Coinbase) untested"},
]
st["hypotheses"] = hyps
cands = [("H7-spot-only-14d", best_auc_spot), ("H8-spot+tape", best_auc_tape)]
cands = [c for c in cands if c[1] is not None]
best = max(cands, key=lambda c: c[1]) if cands else (None, None)
st["best"] = {"rule_id": best[0], "validate_metrics": {"presence_auc": best[1], "validate_metrics_file": "results_validate_metrics.json", **({"secondary": vm} if vm else {})}}
st["frozen_rule"] = "code/final_rule.py uses model_spot_tape_*.txt (H8)"
st["data_sources"] = [
    "Polygon V2 OrderFilled logs, topic2=cluster (own orders), 2026-10-02..H, 719,604 logs (.cache/re/btc5m-bot/chain/own)",
    "Polygon V2 OrderFilled logs, topic3=cluster (makers hit by cluster taker orders), VALIDATE (.cache/re/btc5m-bot/chain/hit)",
    "Gamma metadata 6,048 BTC 5m windows 2026-10-02..H",
    "Binance BTCUSDT 1-s klines 2026-10-01..H-1 (data.binance.vision, checksummed)",
    "data-api taker tapes: all 2,016 VALIDATE windows + BUILD windows 2026-10-09..16 (partial)",
]
st["iterations"] = [{"n": 1, "minutes": 60, "best_validate_score": best[1], "families": ["execution/order-structure", "maker quoting", "spot-reactive taker", "absolute FV edge", "strike definition", "multi-wallet", "behaviour cloning spot-only", "behaviour cloning spot+tape", "lead-lag"]}]
json.dump(st, open(f"{R}/state.json", "w"), indent=1)
print("best", best)
