"""Update state.json for iteration 16 (catalog X177-X190 from the iter15 panels, statuses, hypotheses, components, strategy
statement, iteration entry). Run once at the end of the iteration."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent / "state.json"
s = json.loads(P.read_text(encoding="utf-8"))
R = HERE.parent / "results"


def rj(name):
    f = R / name
    return json.loads(f.read_text()) if f.exists() else {}


ocl = rj("iter16_open_cl.json")


def cl_line():
    if not ocl:
        return "part (a) not scored"
    parts = []
    for f_ in ("BUILD", "STUDY", "VALIDATE"):
        r = ocl.get(f_) or {}
        if r.get("n"):
            parts.append(f"{f_} n {r['n']}: disagreement {r['disagree_share']} ({r['disagree_n']}); itm Binance stand-in {r['itm_binance_standin']} vs "
                         f"Chainlink-true {r['itm_chainlink_true']} (on the disagreements {r['itm_binance_standin_on_disagree']} vs "
                         f"{r['itm_chainlink_true_on_disagree']}); posture k0.7 {r['post_binance_standin']} vs {r['post_chainlink_true']}")
    h1, h2 = ocl.get("VALIDATE_half_first") or {}, ocl.get("VALIDATE_half_second") or {}
    if h1:
        parts.append(f"VALIDATE halves posture Chainlink-true {h1.get('post_chainlink_true')} / {h2.get('post_chainlink_true')}")
    return "; ".join(parts)


cat = s["catalog"]
new = {
    "X177": ("tried", "panel iter15 assumptions P1", "decode per engine instance from the 11-01 split onward (instance-module map)",
             "code16/inst_map.py (results/iter16_inst_map.json): split := one wallet >= 0.80 of the mid-band (0.10-0.90) BTC 5m+15m BUY fills "
             "of a 15-min slot with >= 20 (pre-registered). BUILD 9 of 1,016 slots (0.9%), STUDY 0 of 147, VALIDATE 0 of 319 (aggregate), after "
             "T0 5 of 49, all on 11-01 07:00-08:15 (bosona alone; almach and mo-money only deep bids, both first BTC fill 07:15:03). From 08:30 "
             "mo-money is back on the mid band (12-33 per slot), almach partly (4-11); 09:15 split again. Deep-band share equal across wallets "
             "in every fold (0.14-0.31). Reading: an operational transient after the 05:00-06:59 listing gap (A8), not a new configuration; "
             "the pooled rule stays; evaluate() reports instance_mode (code/r10_mode.py)."),
    "X178": ("tried", "panel iter15 mechanics P2 (+ assumptions P1 step 3)", "per-wallet module configuration; the quote side within one instance",
             "code16/inst_side.py (results/iter16_inst_side_1793455200_1793524800.json): bosona's own mid-band fills on the match clock, "
             "report k1.0: 10-31 14:00-16:53 0.851 (n 484) vs 11-01 07:00-09:20 0.633 (n 297; nowcast 0.677, cheaper 0.654). By |F - mid| band: "
             "< 0.05 0.719 (32) vs 0.435 (124); 0.05-0.1 0.866 (67) vs 0.582 (55); >= 0.1 0.860 (385) vs 0.864 (118); share >= 0.1 0.795 vs "
             "0.397. Pre-registered reading: not composition (bands differ by 0.28 below 0.1); inside one instance the large-edge behaviour is "
             "unchanged and the small-edge fills go below chance; the large-edge share halved. almach / mo-money on 10-31: 0.879 / 0.830."),
    "X179": ("tried", "panel iter15 information I15-3", "one BTC reference for both regimes: the latency-corrected Chainlink nowcast",
             "code16/nowcast.py (results/iter16_nowcast.json): S_now = CL(stamp) + F(t - 50 ms) - F(stamp); k frozen on 10-31 14-18 safe clock "
             "= 1.0 (nowcast 0.785 vs report 0.779). Pure 500 posts per hour (safe clock): 10-31 15 0.792 = 0.792, 16 0.766 vs 0.771, 17 0.808 vs "
             "0.769 (exact 0.888 vs 0.863); 11-01 07 0.631 vs 0.570 (cheaper 0.629), 08 0.633 vs 0.532 (cheaper 0.660). Disagreements on 11-01: "
             "nowcast right 0.871 (140). Signature: nowcast >= report in 4 of 5 hours (-0.005 in one); >= cheaper + 0.08 in the clean hours "
             "fails. On fills (inst_side): pooled 11-01 0.560 -> 0.685, 10-31 0.852 -> 0.848. Clean-block posts split into futures-move re-pegs "
             "(19-26% of posts; on the outcome whose fair rose 0.89-0.96) and still posts on the cheaper token (0.70). Reported in evaluate() "
             "(side_nowcast_match_clock); the counted side is unchanged (on the pre-registered live VALIDATE split 10-31 15:00-16:30 the "
             "nowcast is -0.003 to -0.006)."),
    "X180": ("tried", "panel iter15 assumptions P2 (+ mechanics P3 center part)", "ladder center vs favourite/underdog spread asymmetry",
             "code16/ladder_center.py (results/iter16_ladder_center.json): (window, publish) units with a 500-class add on both outcomes within "
             "300 ms of a public publish: 10-31 17:29-18:00 (437): half-spread median 0.075; c - mid on F_k - mid slope 0.31 / R2 0.52 at k1.0 "
             "(k2 0.04, k3 0.01); two-feature (nowcast): edge 0.30, (0.5 - mid) -0.014. 11-01 07:00-09:15 (1,138): half-spread median 0.075; "
             "slope 0.09-0.16, R2 0.03 (k1) .. 0.13-0.16 (k2-3); two-feature: edge 0.13, (0.5 - mid) +0.090 (R2 0.17). Neither pre-registered "
             "reading holds alone: the best k moves (1 -> 2-3) AND the cheapness term changes sign (nearly collinear for a digital). The ladder "
             "geometry (half-spread) is unchanged; the center's dependence on the reference weakened and it shrinks toward 0.5 by ~9% of "
             "(0.5 - mid) (bids the underdog), the same belief as the deep-bid module."),
    "X181": ("tried", "panel iter15 mechanics P3", "full-ladder snapshot per publish pass; the fair cap min(touch, floor(F - h)) on the main 500 ladder",
             "iteration 16: only the center / half-spread part was measured (X180); the capped-join law (top-rung price change on dF and dtouch "
             "split by F_s - h >= touch_s; within-tick share of min(touch, floor(F - h)) for h constant, h(tau), h(phi(z)/sqrt(tau)); 'no at-touch "
             "500 when |F - mid| < h - spread/2') is not run."),
    "X182": ("tried", "panel iter15 information I15-2", "settlement-grade per-symbol Chainlink at the alt-window open",
             "part (c) code16/open_strike.py (results/iter16_open_strike.json): Binance S against Gamma priceToBeat is the wrong comparison "
             "(USDT/USD basis 12-14 bp; the two strikes disagree on the itm side for 35-44% of opening fills; posture 0.45-0.54 vs 0.85-0.93 with "
             "the stand-in). Part (a) code16/fetch_alt_cl.py + open_cl.py (results/iter16_open_cl.json; ETH/SOL/XRP; priceToBeat = mean "
             "CL[st-61, st-2] verified exactly): " + cl_line()),
    "X183": ("tried", "panel iter15 assumptions P3", "strict per-market replay of the idle module's decoded opening (outcome criterion)",
             "code16/idle_replay.py (results/iter16_idle_replay.json): alt 5m/15m markets, rule = T1d posture at st + 5 s, bid last print - 0.01, "
             "family off-session size, strict trade-through fills T + 2 s .. end - 30 s, hold to resolution. Per-market Pearson / Spearman vs the "
             "cluster: STUDY (781) 0.185 / 0.311, VALIDATE (572) 0.084 / 0.105; oracle first-fill side 0.373 / 0.668 and 0.417 / 0.697; markets "
             "whose first fill is at the open: STUDY 0.402 / 0.653 (side 0.855), VALIDATE 0.305 / 0.394 (0.751). Signature (>= 0.5 both; oracle "
             ">= 0.6) not met: the later two-sided fills carry the per-market PnL."),
    "X184": ("tried", "panel iter15 assumptions P4", "price on thin books: the other makers' touch, not the stale last print",
             "code16/touch_price.py (results/iter16_touch_price_1793512800_1793525100.json), 11-01 06:00-09:25 fills with a recorder match ms: alt "
             "5m/15m (n 72) touch 0.722, touch - 0.01 0.611, ask - 0.01 0.597, R7 0.556, last print 0.431; BTC 5m/15m (383) touch 0.747, R7 0.950. "
             "On thin books the fill sits at the best bid before the match (median price - touch 0.00), a trivial anchor, still < 0.80 on one "
             "block (n 72); no 4h/hourly fills in the span; the best-OTHER-bid version (own level removed) and the hourly/daily book recorder were "
             "not built."),
    "X185": ("open", "panel iter15 information I15-1", "CLOB prices-history as the examinable market state of the long families (hourly, daily, 4h)",
             "not run in iteration 16 (about 1,000 requests; endpoint semantics check on the recorded 4h books first)."),
    "X186": ("open", "panel iter15 information I15-4", "which feed moves the idle module's alt 5m/15m and 4h ladders, and how fast",
             "not run in iteration 16 (dw_clob touch changes vs per-symbol Binance futures, BTC futures, dv_rtds / dy_rtds publishes, dz_rtdsbn)."),
    "X187": ("open", "panel iter15 information I15-5", "the long-horizon fair read off the 4h ladder (fingerprinted rungs, center, horizon-matched fair race)",
             "not run in iteration 16."),
    "X188": ("open", "panel iter15 mechanics P1", "resting state at each print (post and cancel hazards, queue ahead), then print-level selection",
             "not run in iteration 16 (the only unit whose oracle ceiling, 0.81-0.83 at recall 0.62-0.69, is above the selection bar)."),
    "X189": ("open", "panel iter15 mechanics P4", "the non-BTC module as a quote on its recorded books (configured-size labels)",
             "iteration 16: only the fill-price part (X184: touch 0.72 on alt 5m/15m) was measured; purity of the family sizes, opening-post "
             "side and presence at the open, later-post price and re-siding on per-symbol publishes not run."),
    "X190": ("open", "panel iter15 mechanics P5", "replace-all re-sign: does the queue reset at every publish pass?",
             "not run in iteration 16 (needs the makerOrders positions of the cluster's fills in all-match calldata vs the level sizes at the "
             "last pass and at the first add)."),
}
new.update({
    "X191": ("ruled_out", "panel iter15 assumptions Q4 (measured by the panel)", "day-level public calibration drivers of the side tilt",
             "panels/iter15_assumptions.md Q4 (scratchpad p15a/tilt_drivers.py): the realized-move ratio, the market favourite's excess win "
             "rate and their trailing versions against iteration 11's per-day best k and favourite share on 14 BUILD days: Spearman |rho| <= "
             "0.40 (p >= 0.16) in every case."),
    "X192": ("ruled_out", "panel iter15 assumptions Q5 (measured by the panel)", "a Binance-fair price for the non-BTC later fills",
             "panels/iter15_assumptions.md Q5 (p15a/nb_price.py): STUDY later fills, delta fitted on 10-23/24, scored on 10-25/26, sigma v300 or "
             "v3600 x 0.7/1.0/1.4: fair - delta within a tick 0.17-0.30 by family vs last print - 0.01 0.18-0.56."),
    "X193": ("ruled_out", "panel iter15 information C2 (weak form, measured by the panel)", "the Kalshi KXBTCD hourly ladder as the fair of the BTC hourly fills",
             "panels/iter15_information.md C2: 33 BTC hourly windows, 1,210 later fills, Kalshi 1-min candle mid: fill below the Kalshi fair "
             "0.62 of fills, bought outcome = Kalshi favourite 0.52 (in the money 0.55, market favourite 0.51). The trade-resolution form "
             "is part of X187."),
    "X194": ("tried", "own (iteration 16, T6)", "R8b: the dead zone (|F_cl - mid| < 0.05) to the cheaper token",
             "code16/band_side.py (results/iter16_band_side.json), pre-registered 09:45 UTC: VALIDATE per fill 0.6862 vs R8 0.6925, STUDY "
             "0.521 vs 0.569; in the dead zone (36-37% of fills) the posture beats the cheaper token (0.632 vs 0.614; 0.568 vs 0.437). "
             "Rejected; R8 stays."),
})
for k, (st, src, title, ev) in new.items():
    cat[k] = {"status": st, "source": src, "title": title, "evidence": ev}
cat["X160"]["status"] = "tried"
cat["X160"]["evidence"] += (" | iteration 16 (code14/qu_oos.py on 11-01 07:00-09:15, 2,010 at-touch schedule adds, 34 windows; code16/nowcast.py): "
                            "frozen posture (k1.4, stamp 1.25 s) 0.610 (n 1,823), 62/250 posts 0.558 (242), 'rose on moving' (W500, 19% of posts) "
                            "0.884, 'rose else posture' 0.695; pure 500 posts per hour 07 / 08: report k1.0 0.570 / 0.532, nowcast 0.631 / 0.633, "
                            "cheaper 0.629 / 0.660. The 10-31 quote side does not replicate on the clean Sunday block (0.53-0.63 vs 0.77-0.87); "
                            "inside bosona alone the large-edge part does (X178).")
cat["X61"]["status"] = "tried"
cat["X61"]["evidence"] += (" | iteration 16 (strike_poll_1793512800.jsonl, the one polled development hour 11-01 06:00-07:00): no BTC 5m/15m "
                           "listings in that DST hour, so Gamma priceToBeat never appeared; the crypto-price endpoint served the strike "
                           "6.3-9.2 s after the window start (laptop receive, laptop ~0.7-0.9 s slow). Since priceToBeat = mean CL[st-61, st-2] "
                           "(verified exactly again on ETH/SOL/XRP in X182), the strike is computable from the public Chainlink stream ~1 s "
                           "after st - 2, before either source shows it.")
cat["X116"]["evidence"] += (" | iteration 16 (code16/ladder_center.py, X180): Sunday 11-01 07:00-09:15 ladder center best k 2-3 (R2 0.12-0.16) vs "
                            "Saturday 10-31 17:29-18:00 k 1.0 (R2 0.52-0.55); with a (0.5 - mid) term the Sunday center shrinks toward 0.5 "
                            "(+0.090). The Monday blocks (11-02) fall after the budget's end.")
cat["X103"]["status"] = "tried"
cat["X103"]["evidence"] += (" | iteration 16 (code14/qu_oos.py + code16/nowcast.py on 11-01 07:00-09:15, the clean Sunday block): 19-26% of the "
                            "at-touch 500 posts follow a futures move of >= $2 over 450 ms, on the outcome whose fair rose (0.89-0.96); 1-8% on "
                            "10-31. The re-post race is the futures re-peg, not a reaction to the last print (bid hit by the last print 0.504).")
s["hypotheses"] += [
    {"id": "H16-SPLIT", "family": "engine / selection", "description": "one wallet runs the main BTC ladder (split slots)",
     "validate_metrics": {"BUILD": 0.009, "STUDY": 0.0, "VALIDATE": 0.0, "after_T0": 0.102, "1101_0700_0815": "5 of 6"},
     "verdict": "operational transient after the 11-01 listing gap; mo-money rejoined at ~08:30"},
    {"id": "H16-NAT-EXP", "family": "side (one instance)", "description": "bosona's band-conditional side unchanged between 10-31 and 11-01",
     "validate_metrics": {"band_ge_0.1": [0.860, 0.864], "band_0.05_0.1": [0.866, 0.582], "band_lt_0.05": [0.719, 0.435]},
     "verdict": "rejected for small edges (rule or regime change inside one instance); large-edge behaviour unchanged"},
    {"id": "H16-NOWCAST", "family": "side (quote unit, fills)", "description": "latency-corrected Chainlink nowcast as the reference",
     "validate_metrics": {"posts_1101": [0.546, 0.632], "posts_1031": [0.779, 0.785], "fills_1101": [0.560, 0.685], "fills_1031": [0.852, 0.848], "cheaper_posts_1101": 0.668},
     "verdict": "better than the bare report in the clean regime (+0.06-0.12), neutral in the noise regime; below the cheaper token + 0.08 on 11-01; reported"},
    {"id": "H16-CENTER", "family": "price / side (ladder)", "description": "ladder center c = (b_up + 1 - b_dn)/2 per publish pass vs the fair",
     "validate_metrics": {"1031_slope_r2_k1": [0.305, 0.519], "1101_slope_r2_k1": [0.092, 0.032], "1101_best_k_r2": 0.159, "half_spread_median": [0.075, 0.075], "cheapness_coef": [-0.014, 0.090]},
     "verdict": "geometry unchanged, center shrinks toward 0.5 on 11-01 (flatter fair): the configuration moved; both readings collinear"},
    {"id": "H16-IDLE-REPLAY", "family": "outcome (non-BTC)", "description": "strict per-market replay of the decoded alt opening",
     "validate_metrics": {"STUDY": [0.185, 0.311], "VALIDATE": [0.084, 0.105], "oracle_STUDY": [0.373, 0.668], "oracle_VALIDATE": [0.417, 0.697]},
     "verdict": "fails the outcome bar even with an oracle side (Pearson <= 0.43)"},
    {"id": "H16-THIN-TOUCH", "family": "price (non-BTC)", "description": "fill price = best bid of the bought token before the match",
     "validate_metrics": {"alt_touch": 0.722, "alt_r7": 0.556, "btc_touch": 0.747, "btc_r7": 0.950},
     "verdict": "touch beats R7 on thin books (one block, n 72), below 0.80; reported"},
    {"id": "H16-ALT-CL", "family": "side (non-BTC opening)", "description": "the opening bid reads the per-symbol Chainlink vs priceToBeat (vs the Binance stand-in)",
     "validate_metrics": {k: ocl.get(k) for k in ("BUILD", "STUDY", "VALIDATE")} if ocl else {}, "verdict": "see X182"},
]
comp = s["components"]
comp["side"]["description"] = (
    "Iteration 16: inside one instance (bosona's own fills on the match clock) the large-edge side is the same on 10-31 and 11-01 "
    "(|F - mid| >= 0.1: 0.860 vs 0.864) while small-edge fills fell below chance (0.44-0.58) and their share doubled; a latency-corrected "
    "Chainlink nowcast (report + futures move since its stamp) fixes part of it (11-01 fills 0.56 -> 0.685; posts 0.55 -> 0.63; neutral on "
    "10-31); the clean block's at-touch posts are futures re-pegs (0.89-0.96 on the outcome whose fair rose) plus still posts on the cheaper "
    "token (0.70); the ladder center shrinks toward 0.5 on 11-01 (cheapness +0.09) with the same half-spread (0.075). Non-BTC opening: "
    "per-symbol Chainlink vs priceToBeat (X182). | " + comp["side"]["description"])[:2600]
comp["selection"]["description"] = (
    "Iteration 16: instance mode per 15-min slot (X177): one wallet ran the main BTC ladder on 11-01 07:00-08:15 (bosona; never in a "
    "STUDY/VALIDATE slot, 0.9% of BUILD slots), mo-money rejoined ~08:30: an operational transient after the listing gap; reported as "
    "instance_mode. | " + comp["selection"]["description"])[:2600]
comp["timing"]["description"] = (
    "Iteration 16: on the clean 11-01 block a quarter of the at-touch 500 posts are re-pegs within ~0.5 s of a futures move (on the outcome "
    "whose fair rose, 0.89-0.96; 1-8% of posts on 10-31). | " + comp["timing"]["description"])[:2600]
comp["price"]["description"] = (
    "Iteration 16: on the thin alt 5m/15m books the fill sits at the best bid before the match (touch 0.72 within a tick, R7 0.56; n 72, "
    "11-01), on BTC 5m/15m R7 on the match clock 0.95 (touch 0.75). | " + comp["price"]["description"])[:2600]
s["strategy_statement"] = (
    "[engine: VALIDATE-only] One engine runs three accounts with three owner keys; on 10-31 it posted each main-ladder decision in all three "
    "(29% triplet posts), on 11-01 07:00-08:15 (after the listing gap) only bosona ran the main BTC ladder and mo-money rejoined at ~08:30 (an "
    "operational transient; never seen in STUDY/VALIDATE slots). It quotes every crypto Up/Down family at a configured size per family "
    "(BTC 5m/15m 500 x 2^k with 1/8, 1/2, 1/5 levels; other families 10-400). [selection: hypothesis] Modules are switched on and off by hand; "
    "in idle weekend blocks only the non-BTC families trade. [timing: VALIDATE-only] The BTC ladders are re-sided by each public Chainlink "
    "publish within ~300 ms and re-pegged within ~0.5 s of Binance futures moves (a quarter of the at-touch posts on the clean 11-01 block); it "
    "stops ~45 s + TWAP lookback before the end. [side: VALIDATE-only] BTC fills: decided window -> cheaper token, else the Chainlink posture "
    "(0.693 per fill VALIDATE); the ladder center moves ~0.3 of the way from the mid to the Chainlink fair on 10-31 (half-spread 0.075) and only "
    "~0.13 of the way on 11-01 with a shrink toward 0.5 (same half-spread): the side configuration moves between blocks; a nowcast reference "
    "(report + futures move since its stamp) is never worse and helps in the clean regime; non-BTC opening fills follow a public posture "
    "(0.87-0.92), later fills are two-sided. [price: exam-verified block clock; VALIDATE-only in-block] last clean trade minus 0.01 on the "
    "fastest clock (0.807 VALIDATE; 0.95 match clock 11-01); on thin non-BTC books the best bid (0.72) beats it. [size: VALIDATE-only] the "
    "per-family configured table plus imbalance pairing sizes. [exit: VALIDATE-only] holds to resolution, pairs imbalances, merges near the "
    "end. Money: spread and queue priority on the BTC ladders (strict replays lose), and the later two-sided fills of the 4h/hourly/alt "
    "families (a strict replay of the decoded opening tracks per-market PnL at only 0.08-0.19 Pearson, 0.37-0.42 with an oracle side).")
s["iterations"].append({"n": 16, "minutes": 100, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half, aggregate)",
                        "paradigm": "engine instances and the clean-regime quote: instance-module map, a within-instance natural experiment, the "
                                    "latency-corrected Chainlink nowcast, the ladder center per publish pass, plus the idle module's outcome replay, "
                                    "thin-book price anchors and the settlement-grade per-symbol Chainlink at the alt open",
                        "families": ["X177 instance-module map", "X178 within-instance natural experiment (bosona 10-31 vs 11-01 by edge band)",
                                     "X179 nowcast (posts per hour, fills per wallet)", "X180 ladder center / half-spread per publish pass",
                                     "X182 alt opening: true strike with Binance (basis) and per-symbol Chainlink (endpoint fetch)",
                                     "X183 idle-module strict per-market replay", "X184 thin-book touch anchors",
                                     "X160 quote side on 11-01 07:00-09:15", "X61 strike publication (poller output)",
                                     "evaluate(): instance_mode + side_nowcast_match_clock (code/r10_mode.py)"]})
s["status"] = "continue"
s["wall_reason"] = None
s["live_lab_note"] = (s.get("live_lab_note") or "") + (" | iteration 16: dy_rtds clk offset 1.315 s (Binance minus laptop) at 11-01 09:26 UTC "
                                                       "(w32tm: not synchronized, last sync 10-31 18:29 local); the user must resync Windows "
                                                       "time; all own readers filter by server stamps.")
s["best"]["rule_id"] = s["best"]["rule_id"].replace("(iterations 14-15: unchanged; reported blocks quote_unit_side, quote_presence_event_time and r9_nonbtc_module added)",
                                                    "(iterations 14-16: unchanged; reported blocks quote_unit_side, quote_presence_event_time, r9_nonbtc_module, instance_mode and side_nowcast_match_clock added)")
tm = s["target_metrics"]
tm["_notes"] = (tm.get("_notes") or "") + (" Iteration 16: unchanged (R8 kept; no frozen decision changed). The primary unit (10-s fill presence) "
                                           "has an oracle ceiling of ~0.80 with the cluster's actual quote (X72), below the 0.85 bar; the print-level "
                                           "unit's oracle is 0.81-0.83 at recall 0.62-0.69 (mechanics panel).")
P.write_text(json.dumps(s, indent=1, default=str), encoding="utf-8")
op = sorted([k for k, v in s["catalog"].items() if v.get("status") == "open"], key=lambda k: (k[0], int(k[1:]) if k[1:].isdigit() else 0))
print("open", len(op), op)
