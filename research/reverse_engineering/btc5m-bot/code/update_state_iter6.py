"""Iteration 6: bring state.json up to date (catalog with the iteration-5 panel proposals as X13-X27, components, target
metrics, live_lab, hypotheses, iteration entry). Reads the iteration-6 result files for the numbers."""
import os, json
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
S = os.path.join(D, "state.json")


def load(name):
    p = os.path.join(D, name)
    return json.load(open(p)) if os.path.exists(p) else {}


def main(minutes, now_ts):
    s = json.load(open(S))
    live = load("results_live6_iter6.json")
    ct = load("results_calldata_touch_iter6.json")
    prey = load("results_prey_iter6.json")
    fan = load("results_fanout_iter6.json")
    reb = load("results_rebate_iter6.json")
    val = load("results_value_iter6.json")
    sub = load("results_subs_iter6.json")
    comp = live.get("composite_600_100ms_largest_move", {})
    cat = s["catalog"]

    SRC = {**{f"X{13 + i}": f"panel iteration 5, assumptions proposal {i + 1} (panels/iter5_assumptions.md)" for i in range(5)},
           **{f"X{18 + i}": f"panel iteration 5, information proposal {i + 1} (panels/iter5_information.md)" for i in range(5)},
           **{f"X{23 + i}": f"panel iteration 5, mechanics proposal {i + 1} (panels/iter5_mechanics.md)" for i in range(5)}}

    def put(k, status, ev):
        old = cat.get(k) or {}
        cat[k] = {"status": status, "evidence": ev}
        src = old.get("source") or SRC.get(k)
        if src:
            cat[k]["source"] = src

    put("A1", "tried", cat["A1"]["evidence"] + " | Iteration 6: Chainlink RTDS 1-s values against 600+ live taker matches at matching-engine ms under an assumed availability lag of 0-3 s: side agreement 46-51% (placebo 49-55%) at every lag; settlement-TWAP lock-in in the last minute (sign of observed partial TWAP minus current price, n = 83-85) 51-57%, permutation 97.5% = 0.61: not significant.")
    put("A2", "tried", cat["A2"]["evidence"] + " | Iteration 6 live at exchange ms (results_live6_iter6.json): Binance spot BTC/ETH, Coinbase BTC/ETH, OKX swaps BTC/ETH aligned on the bot's matching-engine ms; reaction window [m-600, m-100) ms: Binance spot ETH 97.6%, spot BTC 93.3%, Coinbase BTC 78% when moved (> 0.1 bp).")
    put("A3", "tried", cat["A3"]["evidence"] + " | Iteration 6: sized top of book recorded live (rec_lab6.py: Binance USD-M bookTicker incl. size-only updates, Bybit orderbook.1, OKX bbo-tbt, Hyperliquid bbo): microprice moves in [m-600, m-100) agree 93-100% when present but barely move before quiet matches (see X24).")
    put("A4", "tried", cat["A4"]["evidence"] + " | Iteration 6: Hyperliquid BTC/ETH bbo + trades recorded live (never tested before); ETH perp is the strongest single trigger feed live (Binance USD-M ETH 98.3% agreement over [m-600, m-100) when moved, 19% of matches vs 6% placebo).")
    put("A7", "tried", cat["A7"]["evidence"] + " | Iteration 6: own UNTHROTTLED BTC 5m book recorder (btc5m_clob_raw) and the shared 200-ms book: see X19.")
    put("B6", "tried", "CORRECTED in iteration 6 (rebate6.py, results_rebate_iter6.json): data-api TAKER_REBATE rows exist (polyrea ACTIVITY_TYPES omits the type); each wallet receives exactly 0.500 of its previous UTC day's BTC 5m taker fees (13/13 days for GF, XM, DS). History before H: taker rebates XM $201.1k (since 06-20), DS $111.7k, GF $63.4k, W4 $36.5k; maker rebates XM $29.8k, DS $13.5k, GF $7.3k, W4 $5.1k. VALIDATE: taker fees $61.6k -> rebate $30.8k vs trading PnL after fees +$4.4k (t = 0.50): ~85% of income is the rebate.")
    put("B9", "ruled_out", "Its maker fills are by-products (lost-race remainders of taker orders at the old ask; 81% of the cluster's resting orders appear live as bot-size insertions at the bought outcome's ask of the previous 300 ms), it trades every BTC 5m window (94-99%) with no market choice to explain, and maker rebates are ~$2.6k vs taker rebates ~$25.6k over 10-16..21: no maker-pool targeting.")
    xs = {
        "X13": ("tried", "Panel iteration 5 (assumptions P1) value threshold net of the rebate. value6.py: value gap delta*dS - dPM (market-implied d, sigma fitted on the first half) predicts the quiet live side 61-67% on the second half (BTC futures 10 s 67.3%); a delta-scaled (FV-unit) trigger is not better than a bp threshold (quiet 58-59%); no hazard step. Weak value signal only; a calibrated level FV (strike + vol) is X21."),
        "X14": ("open", "Panel iteration 5 (assumptions P2) per-wallet rules and a role switch at 10-13 14:10. Partial (iteration 6): side_wallet6.py on VALIDATE XM one-sided seconds (10,749): frozen pooled side model 72.6% (80.7% pooled-one-sided, 59.1% where a sibling bought the other outcome, XM taker seconds 79.1%, halves 73.2/72.1); XM-only model trained on BUILD 72.4% (no gain); live participation does not rise with the trigger strength (DS 79-86%, GF 31-40%, XM 3-12% in every bin, fanout6.py); XM one-sided in 24.3% of VALIDATE windows: pooled side model 80.6% on XM's 6,716 pooled-one-sided seconds, presence-argmax 72.7% on all 10,749 XM one-sided seconds. Not done: per-wallet / post-switch retraining and change points."),
        "X15": ("ruled_out", "Panel iteration 5 (assumptions P3) decode submissions from the L2 bid side. subs6.py on the unthrottled book (14:13-14:22): 2,756 bot-size increments at the bought outcome's ask of the previous 300 ms (~25x the cluster's fills), only 20% link to a cluster fill; 81% of cluster resting orders are preceded by one. The book is anonymous, bot sizes are common among the race crowd and W4, and unfilled orders never reach the chain: the cluster's unfilled submissions cannot be attributed. Measured, not argued."),
        "X16": ("tried", "Panel iteration 5 (assumptions P4) decision event across wallets. fanout6.py: 633 live taker matches -> 486 events (< 300 ms, same window and outcome): size 1: 367, 2: 99, 3+: 20; DS first in 80%; DS->GF median 69 ms (p10 7, p90 246), GF->XM 15 ms; participation flat in trigger strength."),
        "X17": ("tried", "Panel iteration 5 (assumptions P5) PnL ceiling and economics. Sibling per-window VALIDATE PnL correlations DS-GF 0.198, DS-XM 0.002, GF-XM 0.145 (Spearman 0.28/0.02/0.17), each wallet vs rest of cluster 0.10-0.24; TAKER_REBATE = 0.5 x prior-day fees (B6). A replica that does not see the wallet's own fills is a fourth sibling: the 0.5 PnL-correlation target is out of reach by construction. Not done: the resampling estimate."),
        "X18": ("infeasible", "Panel iteration 5 (information P1) pmxt v2 archive. curl https://archive.pmxt.dev/ and /docs/v2-data-overview from this laptop 2026-10-31 14:15 UTC: 'Connection timed out after 15005 ms' (the panel saw connection refused at 13:50-14:00 and HTTP 401 'missing api key' from the keyed API, which must not be used). Used instead: own unthrottled recorder (X19) and calldata touch (X25)."),
        "X19": ("tried", "Panel iteration 5 (information P2) unthrottled BTC 5m book recorder: rec_lab6.py (feed btc5m_clob_raw, development blocks only) since 10-31 14:13:33 UTC; results in results_live6_iter6.json (raw_book_bought_outcome)."),
        "X20": ("tried", "Panel iteration 5 (information P3) venues at match ms: fetch_rest6.py (Binance USD-M/spot BTC+ETH, Coinbase BTC+ETH, OKX swaps BTC+ETH, time-bounded REST inside the development block) + rec_lab6.py quotes (Binance futures/spot, Bybit, OKX, Hyperliquid, Coinbase ticker). The largest move among six fast trade series over [m-600, m-100) ms > 0.05 bp covers 36% of matches with 94% side agreement; 45% of matches are quiet on all seven trade feeds over 1 s; quote feeds do not fill the quiet gap."),
        "X21": ("open", "Panel iteration 5 (information P4) inverse-fit the bot's own FV with a streaming Chainlink record. RTDS kept open with PING every 5 s still only sends the initial 60-s snapshot (no stream). Move-based value gap 61-67% in quiet (X13). Calibrated level FV (levelfv6.py: strike = Chainlink mean over [start-60, start), Binance x basis, TWAP variance, k x realized vol): calibration error 4.8 c at placebo instants (> the 1.5 c bar) and side at chance (50.5%): inconclusive. Not done: a better-calibrated FV (priceToBeat strike, implied vol from the market, ETH-led composite) fitted by maximum likelihood."),
        "X22": ("open", "Panel iteration 5 (information P5) historical match-time estimator. Partial (iteration 6, 633 live matches): block ts - match ms = 1.29-3.20 s (5-95%); a linear fit on tx_index (corr -0.31) leaves |error| < 200 ms for 27.5% of txs vs 26.5% for a constant; tx_index orders same-block matches correctly in 77.7% of pairs; the freshest consumed maker quote bounds the match from below only loosely (median age 2.0 s). Not done: co-racers' signing ms from all BTC 5m txs of the block."),
        "X23": ("open", "Panel iteration 5 (mechanics P1) prey makers. Live part done (prey6.py): age of the best consumed maker quote median 2.0 s (quiet 1.65 s, moving 2.35 s), < 500 ms 26% quiet vs 21% moving: fresh quotes not specific to quiet matches; maker 0xec10d230 is 11% of quiet-match counterparties vs 3% in moving ones. Not done: historical full-market calldata and the makers' quote functions."),
        "X24": ("tried", "Panel iteration 5 (mechanics P2) race anatomy on full quote streams: rec_lab6.py (btc5m_venues) records sized top of book for Binance USD-M (every update), Bybit linear, OKX swap, Hyperliquid, Binance spot. CONFIRMED in strong form (results_micro_iter6.json, 204 covered live matches): microprice moves > 0.002 bp over [m-600, m-100) ms precede most quiet matches in the bot direction (Binance USD-M ETH 85.3% of 34/61, OKX ETH 82.8%, Bybit ETH 80.6%, Bybit BTC 89.5%; placebo 35-56%); vote of ten quote series covers 90% of matches at 86.4% (quiet 84.0%, moving 87.3%; placebo 46%). Price-only quote moves (> 0.05 bp) and the touch-imbalance level do not show it. Historical replication via Bybit ETHUSDT orderbook archives started (side_book_eth6.py)."),
        "X25": ("tried", "Panel iteration 5 (mechanics P3) price from calldata: VALIDATE sampled hours 6,306 cluster taker orders: limit within one tick of the best consumed effective ask 95.1% (equal 83.9%; halves 95.0/95.3; DS 96.6, GF 93.9, XM 84.0); limit above every consumed level 11.3%. In final_rule.evaluate as price.calldata_touch (trivial touch anchor measured on the match, not a PIT forecast)."),
        "X26": ("open", "Panel iteration 5 (mechanics P4) versioned config vector. Partial: VALIDATE block-second AUC by window time 0.80 (0-120 s), 0.85, 0.91, 0.96-0.98 (240-270 s): the 240->270 s stop change costs little; the deficit is early in the window. Not done: change-point detection over the whole history."),
        "X27": ("open", "Panel iteration 5 (mechanics P5) capital and fan-out. Fan-out measured live (X16). Not done: collateral balance paths from Transfer logs and participation vs free balance."),
    }
    for k, (st, ev) in xs.items():
        put(k, st, ev)
    s["catalog"] = cat
    s["components"] = {
        "selection": {"confidence": 0.85, "tag": "VALIDATE-only", "description": "Every BTC 5m Up/Down window (94-99% traded, all wallets in the same windows), nothing else; inside a window only prices in the ladder range ~0.12-0.88; whole-cluster outages of 40 min-5 h are bot-side."},
        "timing": {"confidence": 0.75, "tag": "VALIDATE-only", "description": f"Decision = submission of a pre-signed ladder order 100-600 ms after a tick-level move of the BTC/ETH perps (mostly ETH; Binance USD-M, OKX, Bybit): live (10-31 development block) trade moves precede {comp.get('moved', 0.5)} of taker matches at {comp.get('agree', 0.865)} agreement, and sized-quote MICROPRICE moves (> 0.002 bp) precede 90% of them at 86.4% agreement, including the 37% with no trade move (84.0%); the quiet ones are late in the window and in bursts. Historically presence on block seconds 0.875 vs pure baseline 0.819."},
        "side": {"confidence": 0.6, "tag": "VALIDATE-only", "description": "Per second: the outcome the fast composite just moved toward (VALIDATE one-sided seconds 76.7%); live: the direction of the ETH/BTC perp microprice move over the last 100-600 ms, 86.4% of taker matches (84.0% of the quiet ones), ~94% after a > 0.05 bp trade move; both outcomes in 99.8% of windows pooled; XM one-sided in 24.3% of its windows (side model 80.6% where pooled one-sided, 72.7% on all XM seconds)."},
        "price": {"confidence": 0.9, "tag": "VALIDATE-only", "description": "Limit = the touch of the chosen outcome at the decision (the trivial touch anchor, stated as such): VALIDATE calldata, limit within a tick of the best consumed maker price 95.1% of taker orders (equal 83.9%; 11% one or more cents above the touch, more for large orders); live 93% against the recorded ask 50 ms before the match; remainders rest at that price."},
        "size": {"confidence": 0.7, "tag": "VALIDATE-only", "description": "Fixed (small, large) menu per day signed at every price (60/100, 30/50, 30/100); large share is a per-wallet setting (DS 5%, GF 30%, XM 32%), weakly higher after big moves; large orders more often priced above the touch."},
        "exit": {"confidence": 0.9, "tag": "VALIDATE-only", "description": "Holds to resolution; no sells, merges, splits or conversions; one REDEEM per window; daily TAKER_REBATE = 0.5 x prior-day taker fees (~$30.8k in the VALIDATE week, ~85% of income) and MAKER_REBATE (~$3k/week); no liquidity or holding rewards."},
    }
    tm = dict(s["target_metrics"])
    vt = ct.get("validate", {}) if isinstance(ct.get("validate"), dict) else {}
    tm["price_within_tick"] = 0.9512
    s["target_metrics"] = tm
    notes = s.get("target_metrics_notes", {})
    if not isinstance(notes, dict):
        notes = {"previous": notes}
    notes["iteration6"] = ("price_within_tick = calldata touch on the 7 sampled VALIDATE hours (6,306 taker orders; trivial touch anchor measured on the "
                           "match, not a PIT forecast; tape anchor 53%; live book 93%). presence/selection/side/pnl unchanged from iteration 5. Side: XM is one-sided "
                           "in 24.3% of its windows (condition likely applies to XM: 80.6% where pooled one-sided, 72.7% on all XM one-sided seconds). PnL "
                           "correlation ceiling: sibling wallets correlate 0.00-0.20 with each other per window.")
    s["target_metrics_notes"] = notes
    s["best"]["validate_metrics"]["price_within_tick"] = 0.9512
    s["best"]["validate_metrics"]["price_calldata_touch_validate"] = {"n": 6306, "within_tick": 0.9512, "equal": 0.839, "halves": [0.9496, 0.9527], "by_wallet": {"DS": 0.9663, "GF": 0.9388, "XM": 0.84}}
    s["best"]["rule_id"] = "it6: it5 rule + price.calldata_touch (code/final_rule.py)"
    s["best"]["validate_metrics"]["candidate_side_eth_book_it6"] = {"side_accuracy": 0.7717, "taker": 0.8026, "halves": [0.7649, 0.7784], "model": "code/model_it6_side_book_eth.txt", "status": "VALIDATE-only, not wired into final_rule.py"}
    s["best"]["validate_metrics"]["live_microprice_trigger"] = {"first_interval": {"n": 204, "cover": 0.902, "agree": 0.8641, "quiet_agree": 0.84, "placebo": 0.461}, "replication": {"n": 162, "cover": 0.9074, "agree": 0.8299, "quiet_agree": 0.7727, "placebo": 0.553}}
    s["live_lab"] = [x for x in s.get("live_lab", []) if "rec_lab6" not in x.get("what", "")] + [
        {"what": "rec_lab6.py v1 (pid 15084, stopped by taskkill to replace it with the capped v2): feeds btc5m_clob_raw (unthrottled Polymarket BTC 5m book within 3 c of the touch + trades), btc5m_venues (sized top of book Binance USD-M/spot, Bybit, OKX, Hyperliquid coalesced to 20 ms; OKX/Hyperliquid/Coinbase trades), btc5m_rtds_stream; development blocks only (drops sealed-block messages)", "start": 1793456013, "end": 1793458474},
        {"what": "rec_lab6.py v2 (pid 14304; REC6_SUFFIX=2 -> feeds btc5m_clob_raw2, btc5m_venues2, btc5m_rtds_stream2; near-touch 2 c, quotes coalesced to 30 ms, disk cap 250 MB, development blocks only)", "start": 1793458456, "end": 1793642400},
    ]
    s["hypotheses"] = [h for h in s.get("hypotheses", []) if h.get("id") not in {f"H{i}" for i in range(53, 70)}]
    s["hypotheses"].extend([
        {"id": "H53", "family": "economics / rebates (E5)", "description": "TAKER_REBATE = 0.5 x prior-day taker fees; ~85% of VALIDATE income", "validate_metrics": {"ratio_min": 0.5, "ratio_max": 0.5, "validate_rebate": 30.8e3, "trading_pnl": 4.4e3}, "verdict": "supported"},
        {"id": "H54", "family": "trigger: fast-venue trade move at ms (E1)", "description": "largest move among 6 fast trade series over [m-600, m-100) ms > 0.05 bp -> buy that direction", "validate_metrics": {"live_coverage": comp.get("moved"), "live_agreement": comp.get("agree"), "n": comp.get("n")}, "verdict": "supported live (development block), covers ~36% of taker matches"},
        {"id": "H55", "family": "trigger: venue quotes (E2)", "description": "sized top-of-book / microprice moves explain the quiet matches", "validate_metrics": {"see": "results_live6_iter6.json quotes"}, "verdict": "not supported for quiet matches (quote feeds rarely move before them)"},
        {"id": "H56", "family": "trigger: prey makers / fresh quotes (E3)", "description": "quiet matches lift freshly posted quotes", "validate_metrics": {"quiet_age_lt_500": (prey.get("quiet") or {}).get("share_age_lt_500"), "moving_age_lt_500": (prey.get("moving") or {}).get("share_age_lt_500")}, "verdict": "weak: fresh quotes not specific to quiet matches; one maker over-represented"},
        {"id": "H57", "family": "value / level rule (E4)", "description": "quiet side = sign of value gap (FV move minus Polymarket move)", "validate_metrics": {"quiet_test_half2": "0.61-0.67"}, "verdict": "weak support"},
        {"id": "H58", "family": "settlement feed (E7)", "description": "Chainlink RTDS 1-s value moves at any availability lag 0-3 s", "validate_metrics": {"agreement": "0.46-0.51"}, "verdict": "rejected"},
        {"id": "H59", "family": "price from calldata", "description": "limit = best consumed maker price of the same match", "validate_metrics": {"within_tick": 0.9512, "equal": 0.839}, "verdict": "supported (trivial touch anchor)"},
        {"id": "H61", "family": "trigger: perp MICROPRICE (sized top of book) moves (E2, strong form)", "description": "vote of tick-level microprice moves of ten BTC/ETH quote series over [m-600, m-100) ms -> side", "validate_metrics": {"live_cover": 0.902, "live_agree": 0.8641, "quiet_cover": 0.794, "quiet_agree": 0.84, "placebo_agree": 0.461, "n": 204}, "verdict": "supported live (n = 204, development block); historical replication pending (Bybit ETH book archives)"},
        {"id": "H62", "family": "historical ETH perp book in the side model", "description": "Bybit ETHUSDT orderbook.200 features (BE_*) added to the it5 side model", "validate_metrics": {"side": 0.7717, "it5": 0.7666, "control_same_rows": 0.7666, "taker": 0.8026, "halves": [0.7649, 0.7784], "mcnemar_p": 1.3e-9}, "verdict": "small significant gain; not yet in final_rule.py"},
        {"id": "H63", "family": "microprice trigger, out-of-sample live replication", "description": "frozen vote rule on 14:55-15:10 (v2 recorder)", "validate_metrics": {"n": 162, "cover": 0.9074, "agree": 0.8299, "quiet_agree": 0.7727, "placebo_agree": 0.553}, "verdict": "replicates"},
        {"id": "H60", "family": "submissions from the anonymous book (X15)", "description": "bot-size insertions at the old ask reveal unfilled submissions", "validate_metrics": {"insertions": sub.get("at_old_ask"), "linked_share": sub.get("linked_share")}, "verdict": "ruled out (not attributable)"},
    ])
    s["status"] = "continue"
    s["wall_reason"] = None
    s["iterations"] = [x for x in s.get("iterations", []) if x.get("n") != 6]
    s["iterations"].append({"n": 6, "minutes": minutes, "best_validate_score": 0.9132, "block_seconds_presence": 0.8747, "block_seconds_pure_baseline": 0.8193,
                                           "price_within_tick_calldata": 0.9512, "pnl_corr": 0.1755,
                                           "families": ["live ms event study on 7 trade feeds + 5 quote feeds (X20, X24)", "unthrottled BTC 5m book recorder (X19)", "TAKER_REBATE economics (X17/B6)", "PnL-correlation ceiling from siblings (X17)", "calldata touch price (X25)", "prey-maker quote age (X23)", "value gap / fade (X13)", "fan-out events (X16)", "submissions from the anonymous book (X15)", "Chainlink lag scan + TWAP lock-in (A1)", "per-wallet side (X14 partial)", "AUC by window time (X26 partial)", "pmxt archive (X18)"]})
    s["strategy_statement"] = ("One operator runs a TypeScript clob-client bot on four wallets [VALIDATE-only]. For every BTC 5-minute Up/Down window it pre-signs a ladder of "
        "BUY limit orders on both outcomes at every cent, in bursts 90 s before the open and at +42 s and +173 s, signing the wallets one after another [VALIDATE-only, calldata]. "
        "It submits a pre-signed order at the current touch of the outcome toward which the BTC/ETH perpetuals' top of book just ticked: live, a tick-level microprice move "
        "(queue/size change) of the ETH and BTC perps on Binance, OKX and Bybit in the 100-600 ms before the match gives its side in 86% of taker decisions, including the "
        "37% with no trade move anywhere (84%) [VALIDATE-only: live development block, n = 204; historical replication pending]; after a clear trade move (> 0.05 bp) ~94% "
        "[VALIDATE-only]. The limit is the touch (95% within a tick from calldata) and an unfilled remainder rests there [VALIDATE-only]. Sizes come from a fixed daily menu "
        "(30/60/100) [VALIDATE-only]. It buys both outcomes in almost every window and holds to resolution [VALIDATE-only]. About 85% of its income is the 50% taker-fee rebate on "
        "its huge volume; trading after fees is near break-even (+$4.4k in the VALIDATE week, t = 0.5) [VALIDATE-only]. Nothing is exam-verified.")
    s["sealed_from"]["development_after_H_used"] = [[1793404800, 1793426400], [1793448000, int(now_ts)]]
    json.dump(s, open(S, "w"), indent=1, default=str)
    print("state updated", len(s["catalog"]), "catalog items;", sum(1 for v in s["catalog"].values() if v["status"] == "open"), "open")


if __name__ == "__main__":
    import sys
    main(float(sys.argv[1]), int(sys.argv[2]))
