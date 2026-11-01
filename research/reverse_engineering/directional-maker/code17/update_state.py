"""iteration 17: bring state.json to the 11-01 brief format (E1-E7 catalog items, the `dimensions` and `indicators`
ledgers), add the iteration-16 panel proposals as X195-X209 and this iteration's items, and record the results."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import indicators as ind  # noqa: E402

SP = HERE.parent / "state.json"
R = HERE.parent / "results"
s = json.loads(SP.read_text(encoding="utf-8"))
e2s = json.loads((R / "iter17_e2_side.json").read_text())
e2p = json.loads((R / "iter17_e2_presence.json").read_text())
tk = json.loads((R / "iter17_taker_class.json").read_text())
ny = json.loads((R / "iter17_nyse_open.json").read_text())


def D(family, status, source, resolution, latency, best, verdict, mds=None, note=""):
    return {"family": family, "status": status, "source": source, "resolution": resolution,
            "publication_latency": latency, "best_indicator": best, "min_detectable_share": mds, "verdict": verdict,
            "note": note}


dims = {
    # Polymarket internal
    "pm_book_levels": D("polymarket_internal", "have", "shared recorder clob_crypto (top-10 books, server ms); own dm_clob_raw full depth (10-31 14-18, 11-01 06-12); dx_clob / dw_clob", "ms (server stamps)", "~0.1 s", "R7 price anchor (last clean print - 0.01) / touch; at-touch post side vs posture (quote unit)", "drives", None, "price component: R7 0.80 (VALIDATE block clock) to 0.93-0.95 (match clock); the quote center moves 0.13-0.30 of the way from the mid to the Chainlink fair (X180)"),
    "pm_tape_other_wallets": D("polymarket_internal", "have", "data-api /trades (taker-only and maker rows, every competitor wallet)", "block second", "~2 s (block)", "clean-tape activity features (co-occurrence baseline)", "drives", None, "co-occurrence: activity baseline 0.684 vs rule 0.716 on the primary unit; presence OOF on BUILD 0.741 vs 0.780"),
    "pm_queue_and_cancels": D("polymarket_internal", "have", "dm_clob_raw (exact-size adds/removes, 20-ms re-adds), dx_clob schedule-size deltas", "ms", "~0.1 s", "walking-bid chains (mechanics panel P1, not yet built)", "untested", None, "X200-X202 open"),
    "pm_listings_metadata": D("polymarket_internal", "have", "Gamma markets/events (listing fields, resolutionSource, cryptoMarketConfig, rewards)", "per market", "at listing", "public correlates of the BTC 5m on/off (legacy)", "untested", None, "legacy studies found no association, without min_detectable_share"),
    "pm_market_comments": D("polymarket_internal", "missing", "Gamma /comments (parent_entity_type + parent_entity_id)", "per post", "seconds", "comment-count burst before the window", "untested", None, "never fetched; E5 open"),
    "pm_fees_rebates": D("polymarket_internal", "have", "Gamma feeSchedule; MAKER_REBATE activity rows", "per market / daily", "daily", "rebate share of PnL (Gold 18%)", "inferred", None, "little rebate dependence (dossier)"),
    "pm_liquidity_rewards": D("polymarket_internal", "have", "Gamma rewardsMinSize / rewardsMaxSpread; REWARD rows", "per market / daily", "daily", "share of fills >= rewardsMinSize within rewardsMaxSpread (X6 / B7)", "inferred", None, "legacy B7: size schedule above min size; rewards are not the profit source"),
    "pm_operational_events": D("polymarket_internal", "proxy", "changelog / status notes; the daily 01:00 restart seen in calldata salts; 10-29 pause; listing gap 11-01 05:00-06:59", "event", "minutes", "salt-counter resets and listing gaps vs activity", "inferred", None, "explains activity gaps, not side"),
    "pm_taker_hold_itode": D("polymarket_internal", "have", "clob-markets/{cid} itode flag; changelog (150 ms crypto taker hold since 09-04 14:00 UTC)", "per market", "static", "taker commit-to-match latency L (calldata sign ms vs recorder match ms)", "inferred", None, "iteration 17: floor of L p5 193 ms (10-31) / 187 ms (11-01), consistent with a ~150 ms hold plus transit (X195 part)"),
    "pm_taker_commit_times": D("polymarket_internal", "have", "V2 matchOrders calldata (taker order timestamp, signer)", "ms (client clock)", "at the match", "taker information class (auto <= 300 ms, mid, slow)", "no_effect", None, "iteration 17 X196: the class mix does not explain the 11-01 side drop (reweighted 0.844 vs actual 0.675); min_detectable_share not computed (descriptive test)"),
    "pm_prices_history": D("polymarket_internal", "have", "CLOB prices-history (fidelity 1 = previous minute's mid)", "1 min", "~30 s effective", "posture vs the minute mid for the long families", "inferred", None, "daily later fills 0.74-0.75 (X185)"),
    "pm_polybolt_socket": D("polymarket_internal", "blocked", "PolyBolt websocket (needs CLOB credentials, which agents must not create)", "?", "?", "-", "untested", None, "blocked by policy"),
    "pm_legacy_rtds": D("polymarket_internal", "have", "RTDS crypto_prices_chainlink (own dy_rtds / dv_rtds recorders); deprecation announced", "per publish (ms)", "1.2-1.8 s", "Chainlink report on the exact publish clock", "drives", None, "the side posture's reference (live 0.83-0.85 on 10-31)"),
    # related markets
    "binance_spot": D("related_markets", "have", "Binance aggTrades archives (ms), 1-s klines, REST", "ms", "archive next morning; live ~0.05 s", "Binance digital fair (stand-in posture)", "drives", None, "pre-T0 posture stand-in; R5 stack gain +0.0075"),
    "binance_usdm_futures": D("related_markets", "have", "archives (1-s), live dm_bnf / dx_bnf bookTicker + aggTrade", "ms", "~0.05 s", "futures move since the Chainlink stamp (nowcast); futures re-peg events", "drives", None, "11-01: a quarter of at-touch posts follow a futures move (0.89-0.96); nowcast +0.06-0.12 on the clean block (X179)"),
    "other_spot_venues": D("related_markets", "have", "Coinbase, OKX, Bybit, Bitstamp (live 10-31), Kraken trades", "ms", "~0.05-0.2 s", "lead-lag of venue moves vs posts", "untested", None, "legacy lead-lag found no venue ahead of Binance; no min_detectable_share"),
    "deribit_options": D("related_markets", "have", "Deribit public API (front-expiry ATM IV, index)", "1 min / 100 ms", "~1 s", "IV vs realised vol as the sigma multiplier (X117a)", "untested", None, "legacy: no association with the per-block k; no power statement"),
    "funding_liquidations": D("related_markets", "missing", "Binance forceOrder stream / funding (not recorded)", "event", "~0.1 s", "liquidation bursts", "untested", None, "recordable live"),
    "kalshi": D("related_markets", "have", "Kalshi KXBTC15M public trades (10-31 12-18)", "trade", "~1 s", "Kalshi vs Polymarket mid divergence", "untested", None, "legacy X? small sample"),
    "polymarket_perps_index": D("related_markets", "missing", "wss://ws.perpetuals.polymarket.com/v1/ws tickers (index = Pyth + Chainlink Data Streams + Hyperliquid, 200 ms)", "200 ms", "~0.2 s", "index change vs dy_rtds publish (X198)", "untested", None, "live-recordable; not yet recorded"),
    "hyperliquid": D("related_markets", "have", "Hyperliquid info API; dm_hl (10-31)", "trade", "~0.1 s", "owner accounts (X118); HL BTC moves", "untested", None, "accounts not registered"),
    "correlated_assets": D("related_markets", "have", "ETH/SOL/XRP Binance, dv_rtds Chainlink", "1 s", "~1 s", "cross-asset jumps", "untested", None, ""),
    "us_equity_market_open": D("related_markets", "have", "NYSE calendar (09:30 America/New_York, weekdays)", "event", "scheduled (known in advance)", "the BTC 5m window starting at the NYSE open", "drives", None, "iteration 17 T5 (VALIDATE-only): in that window the fills are on the cheaper token (STUDY 0.99, VALIDATE 0.90; R8 0.40-0.44); R8c adopted (+0.0084 per fill)"),
    # event state
    "chainlink_data_streams_low_latency": D("event_state", "proxy", "Chainlink Data Streams (credentials); proxy: GMX v2 OraclePriceUpdate on Arbitrum (X156)", "~0.5 s", "?", "on-chain Data Streams values vs public RTDS", "untested", None, "blocked direct access; proxy probe only"),
    "chainlink_twap60_settlement": D("event_state", "have", "RTDS TWAP-60; priceToBeat = mean CL[st - 61, st - 2]", "1 s", "1.2-1.8 s", "TWAP lock-in in the last 60 s (B3b)", "inferred", None, "settlement known; last-minute fills well explained (presence FN 0.26 at 240-300 s)"),
    "uma_proposals": D("event_state", "not_applicable", "crypto windows settle on Chainlink, not UMA", "-", "-", "-", "no_effect", None, "not applicable"),
    # information
    "news_wires_rss": D("information", "missing", "Google News RSS, CoinDesk / Bloomberg RSS, GDELT DOC 2.0", "15 min (GDELT) / per item", "minutes", "headline bursts vs side residual hours", "untested", None, "E5 open; recent items only -> record live"),
    "social_media": D("information", "blocked", "X (blocked); Telegram previews, Reddit RSS, Bluesky author feeds (work)", "per post", "seconds", "post bursts", "untested", None, "E5 open"),
    "official_calendars_macro": D("information", "have", "US macro release calendar (08:30 / 10:00 ET), FOMC", "event", "scheduled", "side residual around 12:30 / 14:00 UTC", "untested", None, "BUILD residual: 12:30 weekday miss share 0.39 (not elevated); the NYSE open is the outlier"),
    "fear_greed_search_trends": D("information", "missing", "alternative.me Fear & Greed, Google Trends", "daily", "daily", "daily activity / favourite share", "untested", None, ""),
    # own state
    "own_inventory": D("own_state", "have", "activity (cluster net position per window)", "block second", "own", "held outcome after entry (reported, not counted)", "drives", None, "after entry the side is persistence (own-history 0.822 > composite 0.790)"),
    "own_pnl_drawdown": D("own_state", "proxy", "activity cash flows + marks at the clean mid", "10 s", "own", "per-account rolling MTM (X207)", "untested", None, "never tested in the strong form"),
    "own_positions_other_markets": D("own_state", "proxy", "activity across families", "block second", "own", "aggregate BTC exposure vs entry side (X133)", "untested", None, "X133 weak"),
    # operator
    "operator_clock": D("operator", "have", "UTC hour, weekday, US session", "1 s", "0", "clock features in R3; US-session size switch", "drives", None, "presence clock inputs; size schedule at 12:00/21:00 UTC weekday"),
    "operator_restarts_salts": D("operator", "have", "calldata salt counters; 01:00 daily restart", "event", "own", "salt-counter resets", "inferred", None, ""),
    "bot_processing_loop": D("operator", "have", "dm_clob_raw pass detection (publish-anchored passes, 20-ms re-adds)", "ms", "own", "cross-market pass synchrony (X202)", "untested", None, "open"),
    "engine_instances": D("operator", "have", "per-account mid-band fill shares per 15-min slot (X177)", "15 min", "own", "instance_mode", "inferred", None, "11-01: bosona runs the main ladder alone in 7 of 10 slots"),
    "human_reaction": D("operator", "have", "requote lags 50-250 ms", "ms", "-", "-", "no_effect", None, "bot speeds; no human-scale delays"),
    # infrastructure
    "latency_colocation": D("infrastructure", "proxy", "requote / cancel lags on the match clock", "ms", "-", "lag distribution", "inferred", None, "reaction 0-250 ms, inside the 150-ms taker hold"),
    "engine_restarts_api_outages": D("infrastructure", "proxy", "status notes; post-only windows after restarts", "event", "minutes", "activity gaps", "untested", None, ""),
    "rate_limits": D("infrastructure", "missing", "CLOB API rate limits (not observable)", "-", "-", "-", "untested", None, ""),
}
s["dimensions"] = dims

# ---- indicators ledger: legacy rows from the hypotheses ledger (as they were), plus this iteration's rows
KEY = [("chainlink|rtds|report|nowcast|publish|twap|settlement", "pm_legacy_rtds"),
       ("futures|perp|usd-m", "binance_usdm_futures"), ("binance|spot|fair", "binance_spot"),
       ("kraken|coinbase|okx|bybit|bitstamp|venue", "other_spot_venues"), ("deribit|iv|implied", "deribit_options"),
       ("kalshi", "kalshi"), ("hyperliquid", "hyperliquid"), ("reward", "pm_liquidity_rewards"),
       ("rebate", "pm_fees_rebates"), ("restart|switch|on/off|operator|clock|session|version", "operator_clock"),
       ("book|queue|touch|tape|print|flow|taker", "pm_book_levels"), ("inventory|own", "own_inventory")]
rows = []
for h in s.get("hypotheses", []):
    txt = (str(h.get("family", "")) + " " + str(h.get("description", ""))).lower()
    dim = next((d for pat, d in KEY if re.search(pat, txt)), None)
    if dim is None:
        continue
    vm = h.get("validate_metrics") if isinstance(h.get("validate_metrics"), dict) else {"value": h.get("validate_metrics")}
    rows.append(ind.ledger_row(str(h.get("id")), dim, str(h.get("description", ""))[:300], str(h.get("family", ""))[:120],
                               vm or {}, "legacy", str(h.get("verdict", ""))[:200]))
e7 = e2s["e7"]
for k, v in e7.items():
    rows.append({"name": f"E7_{k}", "dimension": "common driver (any)", "definition": "residual_clustering on BUILD fill-level side decisions (one per tx x token), delta 2 s, 1,000 period-shift draws",
                 "event": "R8 public / iteration-15 rule side miss" if k.endswith("miss") else "side hit (control)", "period": "BUILD",
                 "result": {"ratio": v["ratio"], "p": v["p"], "n": v["n"], "n_markets": v["n_markets"], "null": v["null"]},
                 "verdict": "no synchrony (pre-registered bar p <= 0.01, ratio >= 1.5, miss ratio >= hit ratio + 0.3 not met)"})
rw = tk["reweighting"]
rows.append({"name": "X196_taker_latency_class", "dimension": "pm_taker_commit_times", "definition": "L = recorder match ms - taker order sign ms (calldata); classes auto <= 300 ms, mid 0.3-2 s, slow > 2 s; side per class x |F1 - mid| band",
             "event": "class x band reweighting 10-31 -> 11-01", "period": "VALIDATE (live development blocks)",
             "result": {k: {kk: v[kk] for kk in ("acc_1031", "acc_1101_actual", "acc_1101_reweighted", "n_1031", "n_1101")} for k, v in rw.items()},
             "verdict": "rejected: the taker mix does not explain the 11-01 drop"})
rows.append({"name": "X195_taker_hold_floor", "dimension": "pm_taker_hold_itode", "definition": "quantiles of L over every matched taker of the cluster's BTC 5m/15m fills",
             "event": "-", "period": "live development blocks", "result": {"1031": tk["1031"]["L_quantiles_ms"], "1101": tk["1101"]["L_quantiles_ms"]},
             "verdict": "floor 187-193 ms on both blocks: consistent with the 150-ms hold"})
rows.append({"name": "T5_nyse_open_window_cheaper", "dimension": "us_equity_market_open", "definition": "BTC 5m window starting at 09:30 America/New_York on weekdays -> the cheaper token",
             "event": "scheduled NYSE open (first occurrence per day)", "period": "VALIDATE",
             "result": {"study_open": ny["study"]["open"], "validate_open": ny["validate"]["open"], "validate_r8_all": ny["validate"]["r8_all"],
                        "validate_r8c_all": ny["validate"]["r8c_all"], "study_r8_all": ny["study"]["r8_all"], "study_r8c_all": ny["study"]["r8c_all"]},
             "verdict": "confirmed (pre-registered signature met); adopted as R8c"})
s["indicators"] = rows

# ---- catalog
cat = s["catalog"]
E = {
    "E1": ("tried", f"state.json dimensions written in iteration 17: {len(dims)} dimensions over every brief family (Polymarket internal, related markets, event state, information, own state, operator, infrastructure) plus the panel-named ones (taker hold, taker commit times, PolyBolt, legacy RTDS, Perps index, Data Streams). Several stay 'untested' or 'missing' (news, social, comments, funding, Perps index)."),
    "E2": ("tried", f"code17/e2_resid.py (results/iter17_e2_presence.json, iter17_e2_side.json): presence OOF on BUILD 10-09..22 (GroupKFold over 2-h blocks) rule {e2p['presence_oof_auc_rule']} vs activity {e2p['presence_oof_auc_activity']}; {e2p['presence_unexplained_share_fn']:.0%} of filled cells below the 85th percentile, concentrated at |edge| < 0.05 (0.74) and in quiet cells (0.73 vs 0.25 when activity is high). Side: {e2s['side_n_decisions']} BUILD decisions, miss share {e2s['side_miss_share']}; the NYSE-open window 13:30 UTC is the outlier (0.90 misses, 4x activity) -> T5/R8c."),
    "E3": ("open", "first screen pre-registered in NOTES.md (iteration 17): the scheduled market-structure calendar (NYSE open, CME reopen 22:00 UTC, Europe opens, US macro releases) against the side residual and the quote-unit posts; only the NYSE-open direction test was run (confirmed on VALIDATE)."),
    "E4": ("open", "discrepancy/composite indicators not yet screened in the BH framework (the nowcast and the futures re-peg are the closest legacy ones)."),
    "E5": ("open", "news / social / comments never fetched for this strategy; the residual's hour structure (NYSE open) is a scheduled event, not news."),
    "E6": ("open", "no latent fit yet; candidates: the per-block sigma multiplier k (C5) and the instance mode as hidden states."),
    "E7": ("tried", "residual_clustering on BUILD fill-level side misses vs hits: misses ratio 1.44 (5m+15m, p 0.23), 1.50 (with 1h, p 0.18), BTC vs alt 1.34 (p 0.044); hits 2.22 / 1.95 / 2.04 (p 0.013-0.044). No miss synchrony beyond the hits: the side residual has no common second-scale driver. The live quote-unit version (posts on 11-01) is not run."),
}
for k, (st_, ev) in E.items():
    cat[k] = {"status": st_, "source": "brief 2026-11-01", "evidence": ev}
X = {
    "X195": ("open", "panel iter16 information P1", "Taker hold as the decision clock: hold-aware strict replay, leak test, 08-17 / 09-04 hold changes", "partial (iteration 17): floor of L p5 193 / 187 ms on 10-31 / 11-01 (code17/taker_class.py) confirms the ~150-ms hold; the hold-aware replay and the natural experiments are not run."),
    "X196": ("tried", "panel iter16 information P2", "Fill side by the taker's information class (commit-to-match latency)", "code17/taker_class.py (results/iter17_taker_class.json): pre-registered reweighting of 10-31 class x band accuracies by 11-01 shares gives 0.844 (report) vs actual 0.675 (bosona 0.880 vs 0.729): the counterparties do not explain the 11-01 drop; within every class the small-edge band fell (auto takers 0.96 -> 0.48)."),
    "X197": ("tried", "panel iter16 information P3", "E1 dimension inventory plus E7 residual synchrony", "E1 written (dimensions); E7 on BUILD side misses: no synchrony (see E7). Cluster times not looked up in archives (no excess to look up)."),
    "X198": ("open", "panel iter16 information P4", "Re-align the nowcast to the settlement stream's lag; record the Polymarket Perps index", "not run (budget)."),
    "X199": ("open", "panel iter16 information P5", "Keep the exam's Chainlink input alive through the legacy-RTDS deprecation", "not run; code/cl_source.py falls back to the crypto-price endpoint (iteration 10) but the hidden-stream test is not done."),
    "X200": ("open", "panel iter16 mechanics P1", "Decode the walking bid as a state machine and predict the at-touch resting state", "not run (budget)."),
    "X201": ("open", "panel iter16 mechanics P2", "Identify the reference by the hazard of steps and resets", "not run (budget)."),
    "X202": ("open", "panel iter16 mechanics P3", "One engine pass for all markets: pass detection and trigger", "not run (budget)."),
    "X203": ("open", "panel iter16 mechanics P4", "The side is decided at the chain's origin, not at the fill", "not run (budget)."),
    "X204": ("open", "panel iter16 mechanics P5", "Do the engine instances share state? Cross-account crossing and joint caps", "not run (budget)."),
    "X205": ("tried", "panel iter16 assumptions P1", "Taker choice or engine-wide input: cross-market synchrony of out-of-fold misses (E2 + E7)", "BUILD part run (code17/e2_resid.py): presence OOF + side misses, residual_clustering with period 900 / 3600 and BTC vs alt: no miss synchrony beyond the hits; the live quote-unit part is not run."),
    "X206": ("open", "panel iter16 assumptions P2", "The center's reference weight learned online from the reference's recent informativeness", "not run (budget)."),
    "X207": ("open", "panel iter16 assumptions P3", "A per-account rolling mark-to-market loss breaker", "not run (budget)."),
    "X208": ("open", "panel iter16 assumptions P4", "Configuration as discrete operator pushes (change log of center and tilt)", "not run (budget)."),
    "X209": ("open", "panel iter16 assumptions P5", "Wallets that go quiet at the cluster's restart and switch seconds", "not run (budget)."),
    "X210": ("tried", "own (iteration 17, from the E2 residual)", "R8c: the BTC 5m window starting at the NYSE open -> the cheaper token", f"code17/nyse_open.py (results/iter17_nyse_open.json), pre-registered 10:57 UTC: open window cheaper STUDY {ny['study']['open']['cheaper']} / VALIDATE {ny['validate']['open']['cheaper']} vs R8 {ny['study']['open']['r8']} / {ny['validate']['open']['r8']}; per fill VALIDATE {ny['validate']['r8_all']} -> {ny['validate']['r8c_all']}, STUDY {ny['study']['r8_all']} -> {ny['study']['r8c_all']}. Adopted (code/side_sm.py counted side 'r8c_no_own_state')."),
    "X211": ("open", "own (iteration 17)", "Other scheduled slots with a high side residual on BUILD weekdays (06:15, 22:00 CME reopen, 07:45-08:00 Europe opens, 16:00, 01:15, 21:45)", "BUILD only, post hoc: miss shares 0.70-0.86 but mixed outcomes (won 0.10-0.87); needs the pre-registered E3 calendar screen."),
}
for k, (st_, src, title, ev) in X.items():
    cat[k] = {"status": st_, "source": src, "title": title, "evidence": ev}

# ---- target metrics, components, statement
tm = s["target_metrics"]
tm["side_accuracy"] = ny["validate"]["r8c_all"]
tm["side_baseline"] = 0.6785
tm["_notes"] = (tm.get("_notes", "") + " Iteration 17: side = R8c (R8's public side with the BTC 5m window starting at the NYSE open -> the cheaper token; pre-registered T5, VALIDATE per fill 0.6925 -> 0.7009; cheaper-token baseline 0.6785). Everything else unchanged.")
s["live_split"] = s.get("live_split", {})
s["status"] = "continue"
s["wall_reason"] = None
s.setdefault("data_sources", []).append("iteration 17: V2 calldata of 1,171 more cluster fill transactions (taker orders: sign ms, signer) for 10-31 14:00-16:53 and 11-01 07:00-10:50 (calldata/it17_taker_*.parquet)")
it = {"n": 17, "minutes": None, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half, aggregate)",
      "paradigm": "the residual as the target: out-of-fold misses on BUILD (E2), their cross-market synchrony (E7), the taker (counterparty) dimension from calldata (commit-to-match latency, the 150-ms hold), and the scheduled market calendar found in the residual (NYSE open)",
      "families": ["E1 dimension inventory (state.json dimensions)", "E2 presence out-of-fold residual shape (GroupKFold 2-h blocks)", "E2 side residual shape on BUILD fill decisions",
                   "E7 residual_clustering of side misses vs hits (period 900 / 3600, BTC vs alt)", "X196 taker information class reweighting (calldata commit-to-match latency)",
                   "X195 part: taker-hold floor", "T5/X210 NYSE-open window -> cheaper (R8c, adopted)", "legacy indicators ledger"]}
s["iterations"] = [x for x in s["iterations"] if x.get("n") != 17] + [it]
SP.write_text(json.dumps(s, indent=1, default=str), encoding="utf-8")
print("ok", len(dims), len(rows), sum(1 for v in cat.values() if v.get("status") == "open"))
