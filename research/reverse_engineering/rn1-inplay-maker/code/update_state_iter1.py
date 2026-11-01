"""End of iteration 1: fills state.json from the result files (metrics, components, catalog, dimensions, ledger).
Usage: python update_state_iter1.py <presence_tag> <minutes>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_lib import R, load, save, set_catalog, set_dim  # noqa: E402

tag = sys.argv[1]
minutes = float(sys.argv[2])
s = load()
res = R / "results"
pres = json.load(open(res / f"presence_iter1_{tag}.json"))
evf = res / "final_rule_validate_iter1.json"
ev = json.load(open(evf)) if evf.exists() else {}
pm = ev.get("pooled", {})

s["target_metrics"] = {
    "presence_auc": round(pres["auc_FULL2"], 4),
    "selection_auc": None, "selection_recall": None, "selection_lift": None,
    "presence_baseline": round(max(pres["auc_ACT"], pres["auc_ACT2"]), 4),
    "selection_baseline": None,
    "side_accuracy": pm.get("side_accuracy"),
    "side_baseline": pm.get("side_baseline"),
    "price_within_tick": pm.get("price_within_tick"),
    "pnl_corr_pearson": None, "pnl_corr_spearman": None,
    "coverage_fills": pm.get("coverage_fills"),
    "coverage_abs_pnl": None,
}
s["best"] = {"rule_id": "v1_presence_FULL2_lgbm", "validate_metrics": {
    k: pres[k] for k in ("auc_ACT", "auc_ACT2", "auc_LIST", "auc_FULL", "auc_FULL2", "gain_FULL2_vs_ACT", "boot_FULL2_vs_ACT",
                         "gain_FULL2_vs_ACT2", "boot_FULL2_vs_ACT2", "n_validate", "events_validate", "n_build", "events_build",
                         "oof_auc_build_FULL")} | {"final_rule_evaluate_pooled": pm}}
s["status"] = "continue"
s["wall_reason"] = None
s["live_lab"] = []
s["strategy_statement"] = (
    "RN1 is a BUY-only two-sided in-play maker. In the in-play markets it makes (soccer, tennis, CS2, US football; "
    "moneyline, totals, spreads, exact score, half markets) it rests bids on both outcomes that form a 1-tick market "
    "(bid p on one outcome, 0.99 - p on the other) [price: VALIDATE-only for the pair sum, hypothesis (live BUILD "
    "blocks) for the placement], joining a 1-tick inside spread and improving a wider one by one tick, with orders "
    "of ~1,500 shares (tiers ~700/1,500/3,000) independent of price [size: VALIDATE-only], re-signed every few "
    "seconds to tens of seconds (filled orders median 12.8 s old) [timing: VALIDATE-only]. It is almost never filled "
    "before kick-off and is off the book around game events [timing: legacy + VALIDATE-only], holds everything to "
    "resolution with no sells or merges [exit: VALIDATE-only], and does not skew toward completing pairs [side: "
    "VALIDATE-only]. Complete pairs lock the tick; the unpaired residual carries the adverse selection; rebates and "
    "rewards add ~$8k a day. When and where its quote rests (presence) is not decoded: presence AUC "
    f"{pres['auc_FULL2']:.3f} vs activity-only {pres['auc_ACT']:.3f} [hypothesis].")
s["components"] = {
    "selection": {"confidence": 0.3, "tag": "VALIDATE-only",
                  "description": "in-play markets of soccer/tennis/CS2/US football; main market types; skips props and team totals; filled in ~15-18% of in-play taker minutes of its markets"},
    "timing": {"confidence": 0.25, "tag": "VALIDATE-only",
               "description": "in play only (pre-game fills ~1%); filled orders are a median 12.8 s old (requotes every few s); off the book around game events (legacy ESPN); trigger of withdrawals unknown (sports ws p_link 0.20)"},
    "side": {"confidence": 0.4, "tag": "VALIDATE-only",
             "description": "BUY both outcomes; filled side = complement of the taker's direction; tape rule = underdog (0.54, equals the market baseline); no skew toward completing pairs (P(deficit) 0.41)"},
    "price": {"confidence": 0.6, "tag": "hypothesis",
              "description": "1-tick two-sided market: pair sum 0.990 (VALIDATE); joins a 1-tick spread, improves a wider one by a tick (live books: exact 55.5% vs touch 39.9%; within a tick 87.9% vs 90.7%)"},
    "size": {"confidence": 0.5, "tag": "VALIDATE-only",
             "description": "~1,500 shares per order (modes 700/1,500/3,000), independent of price; daily median alternates 1.5k/2.9k; driver of the tier unknown"},
    "exit": {"confidence": 0.8, "tag": "VALIDATE-only",
             "description": "no SELL/MERGE/SPLIT in 21 days; holds to resolution and redeems; pairs lock 1 tick, residual takes the adverse selection"},
}
C = {
    "A1": ("not_applicable", "sports markets settle by UMA on the official result; there is no price feed to settle on; the result-side state is covered by A5"),
    "A2": ("not_applicable", "no spot underlying for sports or esports markets"),
    "A3": ("not_applicable", "no derivatives underlying for sports or esports markets"),
    "A4": ("tried", "sibling markets of the same event in the presence model (ev_tk_5/15, ev_jmp_5): FULL vs LIST gain ~0.002 AUC on VALIDATE; legacy sibling-jump AUC 0.563 (p 0.12)"),
    "A4b": ("open", "Kalshi sports markets not yet fetched"),
    "A5": ("open", "ESPN play-by-play not yet re-fetched this iteration (legacy results only); MLB/NHL/NBA feeds marginal for its families; bo3.gg/liquipedia for CS2 untried"),
    "A5a": ("tried", "sports ws (live block 10-31 12-18): 112 games, 842 score changes; event study of its filled-order signing times p_link 0.20 (max_lag 120) and 0.41 (max_lag 20); ws vs book nearest >=3-tick move median -11.7 s, inconclusive; to deepen (per-goal moves, withdrawals)"),
    "A6": ("open", "news/social/team news not tried"),
    "A6b": ("not_applicable", "FedWatch is for FOMC markets"),
    "A7": ("tried", "tape features (prints, ranges, jumps, effective spread proxy) in the presence model; recorded books used for quote placement (live blocks)"),
    "A8": ("open", "operational events not tried"),
    "B1": ("tried", "V2 matchOrders calldata decoded for 21,000 sampled RN1 tx (21 days) and every tx of the live blocks: one EOA signer, sigType 1, salt = U*Date.now(), sign->fill median 12.8 s, sizes ~1,500 shares, 15.8% signed after the taker order"),
    "B2": ("open", "orderHash grouping done for live blocks (fills per order median 1, fill fraction median 8.7%); cancellations from the books not yet inferred"),
    "B3": ("tried", "quote vs book at signing (604 orders): join a 1-tick spread, improve a wider one by a tick; fair-value inverse fit not yet done"),
    "B4": ("tried", "no MERGE/SPLIT/CONVERSION rows; pair sums 0.990; pair-locked PnL +$372k BUILD / +$184k VALIDATE"),
    "B5": ("tried", "inventory: P(next fill on deficit side) 0.42 BUILD / 0.41 VALIDATE (no rebalancing skew); caps and drawdown rules not yet tested"),
    "B6": ("tried", "MAKER_REBATE $93.3k and TAKER_REBATE $48.8k in 21 days (~20% of trading PnL); rebate-pool targeting not yet tested"),
    "B7": ("tried", "rewardsMinSize 50 / rewardsMaxSpread 4.5c on 934 of 989 live markets; its ~1,500-share inside quotes always qualify; REWARD $24.8k in 21 days"),
    "B8": ("open", "holdingRewardsEnabled not checked"),
    "B9": ("open", "rebate pool share by market not computed"),
    "C1": ("tried", "its EOA 0x5d4f...2edc signs for no other proxy in 21,000 sampled tx; Safe/proxy owner search of other wallets not done"),
    "C2": ("open", "copy/follow lead-lag not tried"),
    "C3": ("tried", "2,669 distinct takers in a VALIDATE week, top 6.8%, top 10 18.6%; 86% of its maker fills are mints against complement buyers; PnL by counterparty not yet computed"),
    "C4": ("tried", "per-day calldata sample: median order size alternates ~1.5k / ~2.9k shares; maker share 84-96% (lower 10-02..04); no formal change-point test yet"),
    "C4b": ("open", "change points not matched to announcements"),
    "C5": ("tried", "fills peak 17-21 UTC with a sharp drop at 21 UTC (10.6% -> 1.9%); signing ms uniform within the second; no human cadence"),
    "C6": ("ruled_out", "rfqEnabled is false on every market of its BUILD/VALIDATE cells (26,459 cells) and on 989 of 989 live dev-unit markets"),
    "C7": ("ruled_out", "0 of 21,000 sampled tx have RN1 as both taker and maker"),
    "C8": ("tried", "salt/sign_ms uniform (TypeScript clob-client), builder and metadata zero, single EOA, signatureType 1; GitHub default-rule search not done"),
    "D1": ("tried", "units used: (market, 60-s bin) presence; per-order quote placement (live)"),
    "D2": ("open", "only gradient boosting on bins so far"),
    "D3": ("open", "replay not done"),
    "D4": ("tried", "PnL split: pairs +$372k / residual +$93k BUILD; +$184k / -$125k VALIDATE; rebates+rewards $167k in 21 days; return by price bucket"),
    "E1": ("tried", "31 dimensions across all families in state.json dimensions"),
    "E2": ("tried", "OOF BUILD residual (GroupKFold by game) characterized in NOTES.md Missing dimensions"),
    "E3": ("open", "first screen (event-state family, sports ws, live BUILD block 10-31 12-18, decisions = filled-order signing times) run: 15 rows, one BUILD survivor score_soccer@1200 (shape peak +57.5 s, lift 2.2, p_link 0.004, q 0.06); VALIDATE confirmation pending (live VALIDATE days); withdrawal series and ESPN part not run"),
    "E4": ("open", "no discrepancy indicator yet"),
    "E5": ("open", "information dimensions not screened"),
    "E6": ("open", "no latent fit yet"),
    "E7": ("tried", "residual_clustering on OOF misses (BUILD sample too sparse: 332 fills, 0 near pairs) and on 9,717 B1 signing times across 1,976 games: ratio 1.30 at 0.25 s (p 0.044), 1.01 at 1 s; no synchrony at the bar"),
    "X1": ("ruled_out", "reviewer lead (Combos/RFQ): rfqEnabled false on all its markets (26,459 BUILD/VALIDATE cells, 989/989 live markets)"),
    "X2": ("tried", "reviewer lead (sports ws latency): mapped via Gamma gameId; event study p_link 0.20/0.41; ws vs book nearest move inconclusive; ESPN comparison not yet done"),
}
for k, (st, evd) in C.items():
    src = s.get("catalog", {}).get(k, {}).get("source")
    set_catalog(s, k, st, evd)
    if src:
        s["catalog"][k]["source"] = src
dims = {
    "taker_delay": ("drives", "1-s delay on all its markets; 15.8% of its filled orders signed after the taker order"),
    "own_inventory": ("no_effect", "side does not follow the deficit (P 0.41-0.42); conditioning test only"),
    "polymarket_sports_ws": ("untested", "event study p_link 0.20 on filled-order signing times only; needs withdrawals (B2) and more blocks"),
    "clob_book_levels": ("drives", "quote placement relative to the inside (live)"),
    "bot_loop_cadence": ("no_effect", "signing ms uniform within the second"),
    "fees_rebates_rewards": ("drives", "rebates+rewards ~20-25% of PnL; quotes always qualify for rewards"),
}
for k, (v, note) in dims.items():
    set_dim(s, k, verdict=v, best_indicator=note)
set_dim(s, "own_inventory", min_detectable_share=None)
new_ind = [
    {"name": "sports_ws_score_change", "dimension": "polymarket_sports_ws", "definition": "score field change per gameId",
     "event": "score change (receive time + recorder clock offset)", "period": "BUILD",
     "result": json.load(open(res / "live_sports_1793448000.json")).get("event_study_maxlag120", {}), "verdict": "untested"},
    {"name": "sports_ws_score_change_20s", "dimension": "polymarket_sports_ws", "definition": "same, max_lag 20 s",
     "event": "score change", "period": "BUILD",
     "result": json.load(open(res / "live_sports_1793448000.json")).get("event_study_maxlag20", {}), "verdict": "untested"},
    {"name": "presence_tape_features", "dimension": "public_tape", "definition": "LightGBM ACT set (prints, ranges, jumps, time in game, price)",
     "event": "level", "period": "VALIDATE", "result": {"auc": pres["auc_ACT"]}, "verdict": "baseline"},
    {"name": "listing_features", "dimension": "listings_metadata", "definition": "sportsMarketType, family, line, event size",
     "event": "level", "period": "VALIDATE", "result": {"auc_LIST": pres["auc_LIST"], "gain_vs_ACT": pres["auc_LIST"] - pres["auc_ACT"]}, "verdict": "small_gain"},
    {"name": "sibling_and_pair_features", "dimension": "sibling_markets", "definition": "sibling taker counts and max 5-min jump, pair price sum",
     "event": "level", "period": "VALIDATE", "result": {"auc_FULL": pres["auc_FULL"], "gain_vs_LIST": pres["gain_FULL_vs_LIST"]}, "verdict": "no_gain"},
    {"name": "tape_spread_proxy", "dimension": "clob_book_levels", "definition": "last taker-buy minus last taker-sell price (5 min), levels, last direction",
     "event": "level", "period": "VALIDATE", "result": {"auc_ACT2": pres["auc_ACT2"], "auc_FULL2": pres["auc_FULL2"]}, "verdict": "see best"},
    {"name": "e7_signing_sync", "dimension": "bot_loop_cadence", "definition": "residual_clustering of B1 signing times across games",
     "event": "coincidence within 0.25/1/2 s", "period": "BUILD", "result": json.load(open(res / "e7_signing_sync_build.json")), "verdict": "no_effect"},
]
e3 = json.load(open(res / "e3_screen_live_1793448000.json"))
for r in e3["rows"]:
    new_ind.append({"name": "e3_" + r["name"], "dimension": "polymarket_sports_ws",
                    "definition": "sports websocket per-game event (" + r["name"].split("@")[0] + "), receive time + clock offset",
                    "event": r["name"], "period": "BUILD",
                    "result": {k: r.get(k) for k in ("null", "units_in_null", "n_events", "shape_peak_lag_s", "shape_width_s", "shape_lift",
                                                     "peak_lag_s", "peak_lift", "median_lift", "p_level", "p_shape", "p_link", "q_bh",
                                                     "level_peak_in_flank")} | {"q_family": r.get("q_family")},
                    "verdict": ("BUILD survivor (q<=0.10), VALIDATE confirmation pending (live VALIDATE days 11-02/03)"
                                if r.get("q_family", 1) <= 0.10 else ("untested (level peak in flank)" if r.get("level_peak_in_flank") else "not significant on BUILD"))})
names = {r["name"] for r in s.get("indicators", [])}
s["indicators"] += [r for r in new_ind if r["name"] not in names]
s["hypotheses"] = [
    {"id": "H1", "family": "event feed", "description": "fast-feed protected pair maker", "validate_metrics": {"sports_ws_p_link": 0.20}, "verdict": "open"},
    {"id": "H2", "family": "public book follower", "description": "pulls on public book changes behind the taker delay", "validate_metrics": {}, "verdict": "open"},
    {"id": "H3", "family": "sharp line", "description": "quotes around a sportsbook fair value", "validate_metrics": {}, "verdict": "open (blocked data)"},
    {"id": "H4", "family": "own state", "description": "inventory-driven pair completion", "validate_metrics": {"p_next_fill_deficit_side": 0.411}, "verdict": "rejected in this form"},
    {"id": "H5", "family": "rebates/rewards", "description": "rebate and reward farming", "validate_metrics": {"rebates_rewards_share_of_pnl": 0.24}, "verdict": "partial: real income, not the main edge"},
    {"id": "H6", "family": "late favourites", "description": "high-price residual harvesting", "validate_metrics": {"ret_0.9_1": 0.031}, "verdict": "not supported (returns flat across buckets)"},
    {"id": "H7", "family": "combos/RFQ", "description": "fills hedge combo flow", "validate_metrics": {"rfq_enabled_share": 0.0}, "verdict": "rejected"},
    {"id": "H8", "family": "counterparties", "description": "few predictable takers", "validate_metrics": {"top10_taker_share": 0.186}, "verdict": "open (not concentrated)"},
    {"id": "v1", "family": "presence model", "description": "LightGBM FULL2 on BUILD cells", "validate_metrics": {"presence_auc": pres["auc_FULL2"], "baseline": pres["auc_ACT"]}, "verdict": "best so far, far from target"},
]
s["data_sources"] = ["data-api activity 10-02..10-22 (162,984 trades)", "Gamma markets of 19,599 traded markets",
                     "OrderFilled logs (V2, topic2 = RN1) per day", "V2 calldata: 21,000 sampled tx + all live-block tx",
                     "data-api /trades tapes of 120+ sampled events (BUILD/VALIDATE)", "live lab clob_wallets and sports (dev blocks 10-31 12-18, 11-01 06-12)"]
its = [i for i in s.get("iterations", []) if i.get("n") != 1]
its.append({"n": 1, "minutes": minutes, "best_validate_score": round(pres["auc_FULL2"], 4),
            "families": ["B1 calldata", "B3 quote vs book (live)", "B4 pairs", "B5 inventory", "presence LightGBM", "A5a sports ws", "E2", "E7", "D4", "C1/C3/C4/C5/C6/C7/C8 checks"]})
s["iterations"] = its
save(s)
print(json.dumps(s["target_metrics"], indent=1))
