"""Iteration 9: bring state.json up to date (catalog X74-X86 and status changes, components, hypotheses, iteration entry,
strategy statement). R6 stays the frozen rule; target_metrics keep R6's VALIDATE values."""
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "state.json"
s = json.loads(P.read_text())
cat = s["catalog"]

X = {
    "X74": ("tried", "source: panel iter8 information I8-1 (slow volatility input for every Chainlink-edge component). Iteration 9: "
            "pre-registered H-VOL on the historical block clock (code9/vol_hist.py, vol_analyze.py): BUILD+STUDY 57,825 BTC 5m maker fills "
            "R6 1.4xv300 0.592 vs best slow (e1800/v3600 k1) 0.611 (+0.019; burst 0.566 -> 0.619); VALIDATE aggregate (27,988) the frozen "
            "choice e1800 0.569 vs R6 0.645, gain -0.076 [2-h bootstrap -0.119, -0.036], burst 0.434 vs 0.671: FAILS. VALIDATE fills are "
            "underdog-heavy (cheaper side 0.679) and accuracy rises with the sigma scale (v3600 x1/1.4/2/3: 0.564/0.643/0.677/0.683; at equal "
            "scale v300 = v3600). Live 10-31 12-18 match clock (seen by the panels): R6 0.786 vs v3600 0.832 (burst 0.39 vs 0.94). Quote unit "
            "(code9/quote_slow.py): slow edge 0.732 vs frozen 0.748, burst seconds frozen 0.695 vs slow 0.368. Cross-family (ETH/SOL/BTC 4h, "
            "36 fills): frozen 0.75 vs slow 0.58. Verdict: not adopted; secondary variant pre-registered for 11-01 06-12 in evaluate() "
            "('it9_slow_sigma_v3600')."),
    "X75": ("open", "source: panel iter8 information I8-2 (name the vol source; natural experiment through a vol regime change, 11-02 12-18). "
            "Iteration 9: the interval-censored sigma_e path of 10-31 12-18 is not identified (logistic slope 2.25, 95% intervals span a "
            "factor ~16; corr(log sigma_e, log v3600) 0.43, 1.4xv300 -0.06); the June signed-ms limit prices do not separate the "
            "estimators (MAD 0.053-0.063 for all, code9/june_vol.py). The regime-change test needs the 11-02 12-18 development block with "
            "the match clock; DVOL is available historically (no recorder needed)."),
    "X76": ("open", "source: panel iter8 information I8-3 (mo-money's own clock and feed). Iteration 9 (code9/wallet_delay.py, "
            "wallet_sigma.py): per-wallet posture by Chainlink delay: bosona peaks at 1,083 ms (0.815), almach 1,432 ms (0.852), mo-money flat "
            "and later (700 ms 0.709, 1,432 0.771, 2,000 0.774, 3,000 0.755); in common windows 0.829/0.863/0.757; mo-money's deficit is "
            "present in the sigma-free region D (0.799 vs 0.886-0.888), so it is a clock/reference difference, not a sigma parameter; at "
            "its own best delay 0.774 (< 0.80). Open: per-wallet burst hazard after dy_rtds publishes and the age of mo-money's wrong-side "
            "orders (needs the 11-01 full-depth book with per-wallet attribution)."),
    "X77": ("tried", "source: panel iter8 information I8-4 (reference level near the strike: Data Streams fields or a drift input). "
            "Iteration 9 (code9/vol_live.py): the best constant offset per slice of 10-31 12-18 is +0 / +3 / -1 dollars with gains <= "
            "+0.003: no stable offset; the small-edge events follow the previous event's side (0.91) rather than an offset (posture 0.45). "
            "The Data Streams report fields in resolution transactions and the futures premium were not decoded (low priority after the "
            "offset failed)."),
    "X78": ("tried", "source: panel iter8 information I8-5 (Kalshi with aligned strikes as an increment over the corrected posture). "
            "Iteration 9 (code9/kalshi_side.py): 18 quarters, 446 BTC 15m fills of 10-31 12-18; basis floor_strike - priceToBeat -$15..-$35 "
            "(both strikes are their own index's pre-open average, so the probabilities are comparable); 'PM cheap relative to Kalshi' 0.345 "
            "vs slow posture 0.917 (frozen 0.753); they disagree on 62% of fills, where the posture is right 96%: no increment."),
    "X79": ("tried", "source: panel iter8 mechanics M1 (invert the engine's volatility from its side decisions). Iteration 9: per-fill bounds "
            "sigma* in region A and a per-10-min logistic fit (code9/vol_live.py): sigma_e not identified (intervals x16); the June price "
            "test (code9/june_vol.py) does not separate; the quote unit favours the fast sigma in bursts while the fills favour the slow one "
            "(code9/quote_slow.py, side_by_order.py: burst fills are the favourite's 500s, 0.72 favourite); the historical block clock "
            "prefers a large scale, not a lookback. No estimator frozen."),
    "X80": ("tried", "source: panel iter8 mechanics M2 (ladder depth as a spread on the digital's risk). Iteration 9 (code9/m2_spread.py): "
            "half-spread on phi(z)/sqrt(tau), p(1-p), mid(1-mid), tau, |F-mid|: BTC 5m held-out R^2 0.47 (frozen) / 0.46 (slow), 15m 0.26 / "
            "0.26; top Up rung within a tick 0.26 (5m), 0.28-0.30 (15m) vs 0.185 anchor. Signature (R^2 >= 0.6, >= 50% within a tick) not met."),
    "X81": ("tried", "source: panel iter8 mechanics M3 (stale takers on the publish clock). Iteration 9 (code9/m3_stale.py; 5,437 BTC 5m/15m "
            "matches of 10-31 15:20-15:40 with taker signing ms; publish proxy stamp + 1,083 ms): P(cluster) fresh 0.030, stale with the new "
            "report raising the fair of the token the taker is short 0.037 (lift 1.11), stale lowering it 0.024 (0.73), stale flat 0.056; same "
            "order in every signatureType; cluster takers' median latency 764 vs 671 ms. Direction as predicted, signature (>= 3x) not met."),
    "X82": ("tried", "source: panel iter8 mechanics M4 (salt-counter forensics of the BTC 5m on/off switches). Iteration 9 (code9/m4_salt.py, "
            "m4_inspect.py, m4_restart0100.py): at the 10-31 16:53:54 switch-off the three counters run on without a jump and the signing "
            "rate does not drop (bosona 11.8 -> 13.6-15.5/s, almach 12.4 -> 12.3/s, mo-money 13.4 -> 15.2/s): no restart, no stop of "
            "signing; almach and mo-money were restarted at ~17:06:32 and ~17:05:52 (counters to 0), bosona not; positive control: the daily "
            "01:00 UTC restart resets all three within ~20 s. Reading: the switch was made inside the running processes (controller or live "
            "configuration), followed by an ad-hoc operator restart of two engines. Historical switches (lot calldata) not yet done."),
    "X83": ("open", "source: panel iter8 assumptions B1 (the exam lot is a weekend: family-general universe, module state as a selection "
            "component). Iteration 9 measurement (code9/scope.py): share of 6-h development blocks 10-08..31 where the universe holds >= 0.80 "
            "of trades and dollars: U1 BTC 5m+15m 0.34, +BTC 4h 0.45, +BTC hourly/daily 0.62, +ETH 0.89, all crypto Up/Down 1.00; minimum by "
            "block type for U1 0.00 (weekday 06, weekend 00/06). Calendar gate (Fri-Sun 18:00-09:00 ET) window AUC 0.68 (BTC 5m) / 0.63 (15m) "
            "since 10-16; BTC 5m off-runs >= 1 h all start Fri-Sun 16:35-18:30 ET except 10-29 (incident) and 10-31 (12:53 ET). Cross-family "
            "posture (code9/posture_xfam.py) 0.75 on 36 fills. Open: build and freeze the family-general universe (per-family presence, "
            "gate) before the next future exam."),
    "X84": ("tried", "source: panel iter8 assumptions B2 (settlement-source natural experiment, Binance-settled hourly/daily). Iteration 9 "
            "(code9/b2_hourly.py): 10-31 12-18, 40 cluster BUY fills in 6 BTC hourly markets (block clock): Binance-candle fair 0.75 vs "
            "Chainlink fair 0.70, references disagree on 25% (Chainlink $134 below Binance); inconclusive at this n (the lot cannot separate: "
            "Chainlink ~ Binance there)."),
    "X85": ("tried", "source: panel iter8 assumptions B3 (posture as a state with inertia; taker-event unit; own-history baselines). "
            "Iteration 9 (code9/vol_live.py; evaluate() now reports 'it9_taker_events'): 1,297 taker events in 71 windows: frozen posture "
            "0.780, slow 0.823, own-history 'side of the previous event' 0.865; switch events (n 165) slow 0.764 / frozen 0.703; small-edge "
            "events (|e| <= 1 c, n 80) posture 0.45, previous side 0.91; a hysteresis band fitted on 12-15 (theta 0.03) gives 0.820 on 15-18 vs "
            "0.830 without. The posture predicts the switches, inertia the rest; the own-history baseline is higher per event."),
    "X86": ("tried", "source: panel iter8 assumptions B4 (window-level anchor). Iteration 9 (code9/b4_anchor.py): 56 windows with >= 8 fills; "
            "failing windows (< 0.7) 17 frozen / 11 slow; the per-window best z-shift has no public correlate (Spearman with 30/60/300-s "
            "returns, open gap, v300/v3600, time left all |rho| <= 0.21; its sign matches the 60-s trend in 45-47% of failing windows)."),
}
for k, (st, ev) in X.items():
    cat[k] = {"status": st, "evidence": ev}

upd = {
    "A4b": ("tried", " | iteration 9 (X78): Kalshi aligned strikes add nothing to the 15m side beyond the posture (0.345 vs 0.917, n 446)."),
    "X48": ("tried", " | iteration 9 (X78): closed with the aligned-strike side race (no increment)."),
    "X58": ("tried", " | iteration 9 (X82): the 16:53 switch-off kept the salt counters continuous and the signing rate unchanged; two "
                     "engines restarted ad hoc at ~17:06; the trigger itself remains undecoded."),
    "X60": ("tried", " | iteration 9: the Kalshi part (X78) adds nothing to the side; iteration 8's live cross-horizon step found no "
                     "taker trigger; the historical cross-horizon step is not done."),
    "X66": ("tried", " | iteration 9 (X81): by taker signatureType on the publish clock, stale sellers of a newly favoured token fill "
                     "the cluster 1.1-1.8x the base rate in every population; no population carries the edge alone."),
    "X70": ("tried", " | iteration 9 (X83, X82): calendar gate window AUC 0.68 since 10-16 (weekend evenings ET); the 10-31 switch-off "
                     "was inside the running processes (no restart, signing rate unchanged), followed by ad-hoc restarts; a loss "
                     "controller remains plausible (own state) but undecided."),
    "A4": ("tried", " | iteration 9: the frozen posture rule applied unchanged to ETH/SOL 5m-15m-4h and BTC 4h fills scores 0.75 (n 36, "
                    "10 windows; slow sigma 0.58)."),
}
for k, (st, add) in upd.items():
    if k in cat:
        cat[k]["status"] = st
        cat[k]["evidence"] = str(cat[k].get("evidence", "")) + add

comp = s["components"]
comp["side"] = {"confidence": 0.6, "tag": "VALIDATE-only", "description": (
    "the outcome it buys is the one whose Chainlink edge over the Polymarket mid is positive (digital of the report stamped T - 1.432 s, "
    "Gamma strike, 1.4 x 300-s vol; no fitted parameter): 0.786 per fill over the 10-31 development block (n 2,244; 0.855 in the "
    "sigma-free region where the reference and the market disagree on the favourite, 0.762 where they agree); per taker event 0.78 "
    "(own-history baseline 0.865); unexamined families 0.75 (n 36); historical block clock 0.60-0.65. A slow sigma lifts the live "
    "per-fill score to 0.83 but fails the historical replication and the quote-level test (not adopted). Mo-money is 0.76-0.80 "
    "(older/smoothed reference).")}
comp["selection"] = {"confidence": 0.4, "tag": "hypothesis", "description": (
    "one engine over crypto Up/Down; BTC 5m and 15m are modules switched off for hours, mostly Fri-Sun US-Eastern evenings (gate "
    "window AUC 0.68); the 10-31 16:53 switch-off happened inside the running processes (salt counters continuous, signing rate "
    "unchanged) and two engines were restarted ad hoc 12-13 min later; R6's universe (BTC 5m + 15m) covers >= 80% of trades and "
    "dollars in only 34% of 6-h blocks, the all-crypto universe in all. BTC 15m presence (R3 class) 0.812 vs 0.778 on VALIDATE.")}
comp["price"] = {"confidence": 0.65, "tag": "exam-verified (block clock); VALIDATE-only (match clock)", "description": (
    "fill price = last clean print minus 0.01 (match clock 0.83-0.86, block clock 0.70, exam 0.688); the ladder hangs off each "
    "market's own mid with a ~0.2 Chainlink skew; its half-spread follows the digital's risk only partly (R^2 0.47 in 5m, 0.26 in "
    "15m; top rung within a tick 26-30% vs 19% anchor).")}
comp["timing"]["description"] = str(comp["timing"].get("description", "")) + (
    " Iteration 9: daily restart at ~01:00:10-01:00:22 UTC resets all three counters; signing ~11-18 orders/s per wallet.")

s["hypotheses"] += [
    {"id": "H-VOL", "family": "X74", "description": "slow sigma (1-h realised / EWMA 1800 s) in the posture", "validate_metrics": {
        "buildstudy_R6": 0.592, "buildstudy_slow": 0.611, "validate_R6": 0.645, "validate_slow_e1800": 0.569, "gain": -0.076,
        "gain_ci95": [-0.119, -0.036], "live_R6": 0.786, "live_v3600": 0.832, "quote_unit_frozen": 0.748, "quote_unit_slow": 0.732},
     "verdict": "rejected by the pre-registered VALIDATE test; mixed live evidence; not adopted"},
    {"id": "H-SIGE", "family": "X79", "description": "interval-censored engine sigma path", "validate_metrics": {"bins": 22, "corr_log_v3600": 0.43,
     "corr_log_1.4v300": -0.06}, "verdict": "not identified (intervals x16)"},
    {"id": "H-XFAM", "family": "X83", "description": "frozen posture on ETH/SOL/BTC 4h", "validate_metrics": {"n": 36, "windows": 10,
     "frozen": 0.75, "slow": 0.58, "cheaper": 0.64}, "verdict": "weakly consistent (small n)"},
    {"id": "H-KALSHI-ALIGNED", "family": "X78", "description": "PM cheap vs Kalshi (aligned) as 15m side", "validate_metrics": {"n": 446,
     "kalshi": 0.345, "slow_posture": 0.917}, "verdict": "rejected"},
    {"id": "H-STALE", "family": "X81", "description": "paid fills are stale takers on the publish clock", "validate_metrics": {"lift_stale_up": 1.11,
     "lift_stale_down": 0.73, "base": 0.033}, "verdict": "direction right, signature not met"},
    {"id": "H-SALT-SWITCH", "family": "X82", "description": "switch-off kind from the salt counters", "validate_metrics": {
     "jump": 0, "rate_before_after": "11.8-13.4 -> 12.3-15.5 /s", "adhoc_restarts": 2}, "verdict": "switch inside running processes; ad-hoc restarts after"},
    {"id": "H-SCOPE", "family": "X83", "description": "R6 universe coverage per 6-h block", "validate_metrics": {"U1": 0.34, "U2": 0.45,
     "U3": 0.62, "U4": 0.89, "U5": 1.0, "gate_auc_btc5m": 0.68}, "verdict": "R6 fails scope in 2/3 of blocks; all-crypto universe needed"},
    {"id": "H-INERTIA", "family": "X85", "description": "posture with inertia, taker-event unit", "validate_metrics": {"events": 1297,
     "slow": 0.823, "frozen": 0.780, "prev_event": 0.865, "switch_events_slow": 0.764}, "verdict": "own-history baseline higher; hysteresis not better held out"},
    {"id": "H-SPREAD", "family": "X80", "description": "ladder half-spread on digital risk", "validate_metrics": {"r2_5m": 0.47, "r2_15m": 0.26,
     "within_tick_5m": 0.26}, "verdict": "partial, signature not met"},
    {"id": "H-ANCHOR", "family": "X86", "description": "window-level anchor", "validate_metrics": {"max_abs_spearman": 0.21}, "verdict": "no public correlate"},
    {"id": "H-REGION-PNL", "family": "D4", "description": "PnL by region (sigma-free D vs vol-comparison A) and favourite/underdog",
     "validate_metrics": {"build_underdogA_share_of_pnl": 0.73, "build_underdogA_ret": 0.121, "validate_ret_all": 0.043,
                          "validate_D_refside_ret": 0.128, "validate_A_fav_ret": 0.035, "validate_A_underdog_ret": 0.074},
     "verdict": "profit concentrated in underdog fills (region A) and reference-side fills (region D)"},
]
s["iterations"].append({
    "n": 9, "minutes": 100, "best_validate_score": 0.716,
    "validate_definition": "2026-10-27..30 (lot second half, aggregate); live 10-31 12-18 (seen by the panels: descriptive)",
    "paradigm": "the engine's pricer state as a latent variable (side = information part + volatility comparison), decoded by interval-censored "
                "inversion on a much larger sample (86k historical block-clock fills, June signed-ms orders, live match clock), and the module "
                "state / family-general universe for scope",
    "families": ["X74 I8-1 slow sigma: pre-registered historical replication (fails VALIDATE), live, quote unit, cross-family",
                 "X79 M1 interval-censored sigma_e path; June price residual by estimator", "X76 I8-3 per-wallet delay and region split",
                 "X77 I8-4 constant reference offset", "X78 I8-5 Kalshi aligned strikes", "X80 M2 ladder half-spread on digital risk",
                 "X81 M3 stale takers on the publish clock (all-match calldata)", "X82 M4 salt counters at the switch-off and at the 01:00 restart",
                 "X83 B1 scope per 6-h block, calendar gate", "X84 B2 Binance-settled hourly markets", "X85 B3 taker events, own-history baseline, hysteresis",
                 "X86 B4 window anchor", "D4 PnL by region and favourite/underdog", "posture on unexamined families (ETH/SOL/BTC 4h)",
                 "which filled orders carry the side (calldata order size x regime)", "both-sided touch at fill times"]})
s["status"] = "continue"
s["wall_reason"] = None
s["data_sources"] += [
    "iteration 9: activity of the three wallets for 10-31 12:00-18:00 (all markets; .cache/re/directional-maker/it9/act_*.parquet)",
    "iteration 9: V2 calldata of every cluster fill tx 10-31 15:50-18:00 and 00:40-01:50, and the ETH/SOL/BTC 4h fills (calldata/it9sw_, it9rs_, it9xf_)",
    "iteration 9: Binance ETHUSDT / SOLUSDT / BTCUSDT 1-s klines (REST) for 10-31 10:00-18:00",
    "iteration 9: Kalshi KXBTC15M public trades and market metadata (floor_strike) for 18 quarters of 10-31 12-18",
    "iteration 9: shared recorder rtds 'crypto_prices' for eth/sol Chainlink (tolerant dev-folder reader)",
]
s["strategy_statement"] = (
    "[engine: VALIDATE-only] One engine runs three wallet processes (per-wallet sequential salt counters, reset by the daily ~01:00 UTC "
    "restart within ~20 s of each other; real ms timestamps until ~06-21, 0 since), each signing ~11-18 orders/s. "
    "[selection: hypothesis] It quotes nearly every crypto Up/Down window of the modules it runs: BTC 5m and 15m on weekdays, BTC 4h, "
    "hourly and daily, ETH, SOL, XRP and others around the clock; BTC 5m/15m are switched off for hours, mostly from Friday-Sunday US-Eastern "
    "evenings to the next morning (calendar gate window AUC 0.68); the 10-31 16:53 switch-off was made inside the running processes "
    "(counters continuous, signing rate unchanged) and two engines were restarted ad hoc 12-13 min later. R6's universe (BTC 5m + 15m) "
    "holds >= 80% of trades and dollars in only 34% of 6-h blocks; only the all-crypto universe does in every block type. "
    "[timing: VALIDATE-only] It re-prices its ladders on each Chainlink report within ~0-150 ms of the public RTDS relay's publish, plus "
    "re-posts 50-400 ms after Binance moves; filled orders are fresh 500-share posts at the touch matched ~0.7 s later; it stops ~30 s "
    "before the end. [side: VALIDATE-only] It buys the outcome whose Chainlink edge over the Polymarket mid is positive (digital of the "
    "report stamped T - 1.432 s, Gamma strike, 1.4 x 300-s vol): 0.79 per fill on the 10-31 match clock (0.85 where the reference and the "
    "market disagree on the favourite: an information part that needs no volatility; 0.76 where they agree and the choice is a volatility "
    "comparison), 0.78 per taker event against an own-history baseline of 0.86, 0.75 on the families nobody examined (36 fills), 0.60-0.65 "
    "on the historical block clock. A slow sigma fits the live fills better but fails the historical replication and the quote-level "
    "test, so it is not adopted. [price: exam-verified (block clock) / VALIDATE-only (match clock)] Fill price = last clean print minus a "
    "tick (0.83-0.86 match clock, 0.70 block clock); each ladder hangs off its own market's mid with a ~0.2 Chainlink skew, and its depth "
    "follows the digital's risk only partly (R^2 0.47). [size: VALIDATE-only] 500 x 2^k shares in the weekday session or high vol, "
    "62/250 otherwise. [exit: VALIDATE-only] Holds to resolution; small complement merges. [economics: VALIDATE-only] Profit is "
    "concentrated in cheap underdog fills when the reference and the market agree (BUILD: 73% of PnL on 13% of dollars) and in fills on "
    "the reference's side when they disagree; it is a liquidity provider skewed by the settlement stream, paid by takers who buy "
    "favourites through complement mints.")
tm = s["target_metrics"]
tm["_notes"] = str(tm.get("_notes", "")) + " Iteration 9: unchanged (R6 kept; the slow-sigma variant failed its pre-registered VALIDATE test)."
P.write_text(json.dumps(s, indent=1))
print("open:", [k for k, v in cat.items() if v.get("status") == "open"])
print("n catalog", len(cat))
