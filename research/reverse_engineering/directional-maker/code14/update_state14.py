"""Iteration 14 bookkeeping: catalog X146-X161, component tags, strategy statement, hypotheses, iteration entry."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent / "state.json"
s = json.loads(P.read_text())
c = s["catalog"]
R = HERE.parent / "results"


def add(k, status, evidence, source):
    c[k] = {"status": status, "source": source, "evidence": evidence}


def upd(k, status, text):
    v = c.setdefault(k, {"status": "open", "evidence": ""})
    v["evidence"] = (v.get("evidence") or "") + " | iteration 14: " + text
    if status:
        v["status"] = status


scan = {}
try:
    scan = json.loads((R / "iter14_qu_scan_1793455200_1793469600.json").read_text())
except OSError:
    pass

add("X146", "tried", "T1 (code14/lagged_quote.py, code14/qu_oos.py; results/iter14_lagged_quote_*.json, iter14_qu_oos_1793455200_1793469600.json): "
    "uncensored quote unit = every schedule-size post at the touch, 10-31 14-18 (6,200 rebuilt with new price levels; it13 table 6,084). Posture 0.733 "
    "(500/1000 0.753, 62/250 0.509); on the 4-6% of posts after a futures move of >= $2 over 0.5-1 s the 'fell' law scores 0.18-0.28 (the post is on the "
    "outcome that ROSE 0.72-0.82); the filled class-(i) orders are on the outcome that fell (0.90-1.00): the panel's one-law account fails on unfilled posts "
    "(fill selection by the takers' momentum). Rose-else-posture 0.743 vs posture 0.733. 11-01 06-07 out-of-sample impossible: no BTC 5m/15m windows "
    "listed 11-01 ~05:00-06:59 UTC (DST hour).", "panel iter13 mechanics P1")
add("X147", "tried", "T6 (code14/pres_event.py; results/iter14_pres_event_1793455200_1793469600.json): (window, outcome, 1-s) fill presence on the match clock, "
    "fit 14-16 / test 16-18: activity 0.774, activity + Chainlink/futures 0.805 (5m 0.736 vs 0.691, 15m 0.798-0.810 vs 0.769), gain +0.031 [20-min block "
    "bootstrap +0.006, +0.044]. Event time raises both the rule and the activity baseline; the gain is unchanged from the 10-s unit.", "panel iter13 information I13-2")
add("X148", "tried", "T2 (code14/lagged_quote.py): per filled order at the match (n 799 / 498): posture 0.855 / 0.815; 'outcome the futures move went against' "
    "where |move| >= theta over [match - D, match - 50 ms], else posture: best fit W 0.5 s 0.855, test 0.825 (+0.010). Class (ii) at the fill follows the "
    "posture 0.852 / 0.755 (0.663 / 0.572 at the post). No class-free public two-regime rule beats the posture.", "panel iter13 assumptions P3")
add("X149", "tried", "T3 (code14/lagged_quote.py): class-(ii) posture with futures-mid sigma over 60/300/900/3,600 s x k 0.5-2.5: fit-best L900 k0.7 0.760 -> test "
    "0.541; L900 k1.4 0.505 -> 0.742; class (i) 0.72-0.85. The resting rungs' side flips with the scale (fair near the mid): not identifiable out of sample.",
    "panel iter13 information I13-1")
add("X150", "tried", "code14/sel_geometry.py (results/iter14_sel_geometry_1793455200_1793469600.json): print unit 10-31 14-18 (38,204 test prints, base 1.5%); "
    "cluster fills by d = last clean print - price: d1 48%, d0 22%, d2-3 11%. Fixed geometry score (posture side at t - 1.25 s for d in {0,1}, c fitted 0 for "
    "d 2-3): AUC 0.558, no threshold with lift >= 3. Activity LightGBM 0.683 (recall 0.20 at lift 3); activity + posture + d 0.742 (within-window 0.762), "
    "recall 0.42 at lift 3 (gain +0.059). Selection bar (0.80, 50% at lift 3) not reached; oracle ceiling 0.81-0.83 (X72).", "panel iter13 assumptions P2")
add("X151", "open", "steps 1-2 done (results/iter9_scope.json blocks, NOTES iteration 14 T5): R8 universe (BTC 5m + 15m) on the pre-registered weekend "
    "analogs: Sat 06-12 0.00/0.00, 0.87/0.94, 0.83/0.90; Sat 18-24 0.53/0.52, 0.60/0.76, 0.82/0.91; Sun 00-06 0.00/0.00, 0.43/0.59, 0.83/0.83 (10-31 00-06 "
    "0.91/0.95); Sun 12-18 0.72/0.66, 0.53/0.52, 0.84/0.90; U4 fails 3 of 4 blocks of 10-24/25; U5 (all crypto) 1.00. Family composition of the idle "
    "weekend blocks: BTC 4h/hourly/daily, ETH 15m/hourly/daily, XRP 5m, BNB hourly, non-schedule sizes. Steps 3-5 (family-general R9 frozen and scored on "
    "the analogs) not built.", "panel iter13 assumptions P1")
add("X152", "tried", "light form (code14/trip.py, results/iter14_trip.json): BTC 5m off-runs >= 60 min (7 events in development 10-08..31); AUC of the "
    "drawdown since the 01:00 restart BUILD 0.875 / STUDY 0.822 / VALIDATE 0.927 / live 0.73, since the last re-enable 0.565 / 0.889 / 0.960 / 0.922; "
    "calendar gate 0.726 / 0.629 / 0.49 / 0.20; values at the events $1.1k-$14.6k (no stable level; CV >> 0.25). BTC 15m (25 events) 0.547 / 0.797 / 0.53. "
    "Per-wallet and 10-s mark-to-market variants not run (7 events cannot meet the >= 8-event signature).", "panel iter13 mechanics P2")
add("X153", "tried", "code14/triplets_qu.py and qu_oos.py: on the uncensored quote unit singles / pairs / triplets 0.706 / 0.785 / 0.804 (14-16), 0.738 / "
    "0.729 / 0.675 (16-18), rebuilt 0.720 / 0.753 / 0.734: no triplet advantage; the per-fill one (0.876 vs 0.751) is fill selection.", "panel iter13 mechanics P3")
add("X154", "tried", "code14/replay_batch.py (results/iter14_replay_batch.json): one taker print per decision second instead of the second's through-volume. "
    "VALIDATE strict posture 0.207/0.218 (-16.6%) -> 0.213/0.214 (-10.7%); at-touch 0.222/0.226 (-12.8%) -> 0.228/0.222 (-6.2%); oracle side 0.472-0.475 / "
    "0.530-0.532. Return +5-7 points; window-correlation ceiling unchanged.", "panel iter13 mechanics P4")
add("X155", "tried", "code14/pairing_persist.py (results/iter14_pairing_persist.json): exact-|Z| pairing bid within 10 s for 0.188 of 876 imbalance changes "
    "(placebo 0.001), 0.210 / 0.220 / 0.221 for states persisting >= 2 / 3 / 5 s: not a transient-state artefact.", "panel iter13 mechanics P5")
add("X156", "open", "step 1 (code14/gmx_probe.py, results/iter14_gmx_probe.json): arb1.arbitrum.io/rpc serves eth_getLogs (publicnode: HTTP 403 archive "
    "token; drpc free plan: HTTP 400 range). GMX v2 EventEmitter OraclePriceUpdate for BTC (0x47904963..., WBTC 0x2f2a2543...) from provider 0x7ba7ae61... "
    "equals the RTDS Chainlink value of the same stamp to the cent (4 of 6; +$1.12 for 2) on 10-31 15:00-15:10, but only ~3 distinct BTC stamps per 10 min: "
    "a sparse basis anchor, not a 1-s reference. Steps 0 and 2 (stand-in agreement by week; September stable hours) not run.", "panel iter13 information I13-3")
add("X157", "open", "not run (the takers' clock; the information panel's C3 measured 39% in-flight takers and a print-burst trigger).", "panel iter13 information I13-4")
add("X158", "open", "not run (hour-of-week public covariates); the X152 events show a scheduled 18:15-18:30 ET weekend-evening component.",
    "panel iter13 information I13-5")
add("X159", "tried", "code14/who_paid.py (results/iter14_who_paid.json): 34,410 cluster maker BUY fills of the stable sample joined to takers (99.8%). "
    "September +8.3% per $: rest 53% of shares / 42% of PnL (+6.6%), round-USD 23% / 26% (+9.2%), top-20 September counterparties 23% / 31% (+11.4%); "
    "October control +0.6%: rest +4.1%, round-USD -11.2% (27% of shares), top-20 9% of shares (+3.2%). Top-20 share of the cluster's fills -63% (market "
    "share 17% -> 11%); the cluster's cheaper-token share against round-USD takers 0.70 -> 0.49. No single population >= 60% of September PnL.",
    "panel iter13 assumptions P4")
add("X160", "open", "own (iteration 14): T1 out of sample on the off-session configuration (quote unit of 62/250 posts, posture vs cheaper / rose / "
    "inventory) on the next development block with BTC books (11-01 07:00-12:00 or 18-24); frozen in code14/qu_oos.py.", "iteration 14 (own)")
add("X161", "open", "own (iteration 14): R9 = a family-general universe for the exam lot (every crypto Up/Down family: R7 price, R8 public side with the "
    "cheaper-token branch where no Chainlink series exists, presence by transfer of the R3 class), frozen before scoring on the weekend analogs.",
    "iteration 14 (own)")
upd("X133", "tried", "code14/agg_delta.py (results/iter14_agg_delta.json): BTC 5m entry on the outcome offsetting the cluster's open BTC 5m/15m/4h "
    "exposure 0.455 / 0.484 / 0.486 (BUILD / STUDY / VALIDATE agg), |exposure| >= 500 0.436 / 0.517 / 0.458: no hedge.")
upd("X132", "ruled_out", "T2 on the exact live clock: the futures move over 0.25-2 s before the match adds <= +0.01 to the posture per filled order "
    "(test 0.825 vs 0.815); the lot's derived ms clock cannot add more than the exact one.")
upd("X75", None, "T3: the class-(ii) resting rungs do not identify the volatility source (best scale flips between halves); still open for the 11-02 "
    "12-18 regime change.")
upd("X83", None, "T5 (see X151): R8's universe fails scope on the 10-24/25 weekend analogs; every crypto family is needed.")
upd("X103", None, "the 11-01 06-07 part of the development block had no BTC 5m/15m listings (DST hour); the full-depth recorder had no CLOB feed "
    "until the 07:00 windows.")
upd("X104", None, "X159 measured the taker populations across the September -> October boundary (on-session hours included).")
upd("A8", None, "no BTC/ETH 5m-15m windows listed for 11-01 ~05:00-06:59 UTC (the US DST fall-back hour); windows from 07:00 exist (created 10-31 07:07).")

comp = s["components"]
pre = {
    "selection": "Iteration 14: BTC 5m switch-offs follow drawdowns since the 01:00 restart (AUC 0.82-0.93 over 7 events) but at no fixed level ($1.1k-$14.6k), "
                 "plus a scheduled-looking 18:15-18:30 ET weekend-evening component (own state, reported); R8's universe fails scope on the latest weekend "
                 "analogs (BTC 5m + 15m 0.00-0.72), where small non-schedule orders run on BTC 4h/hourly/daily, ETH and XRP. ",
    "timing": "Iteration 14: on the uncensored quote unit the engine re-posts at the touch on the outcome that ROSE after a futures move (0.72-0.82 of the 4-6% "
              "moving posts): it follows the moving mid; event-time (1-s) presence 0.805 vs activity 0.774 (gain unchanged). ",
    "side": "Iteration 14: the uncensored quote (every 500/1000 post at the touch, 10-31 14-18) follows the Chainlink posture taken at the post with the report "
            "stamped <= t - 1.0 s and k 1.0 x futures-mid sigma300 at 0.815 (fit 14-16) / 0.811 (test 16-18); exam-recorder form 0.804 on 15:53-18:00 "
            "(always-Up 0.506, cheaper 0.439, mid-rose-1s 0.648); with the R8 form (L 1.25 s, k 1.4) 0.733 (500/1000 0.753; 62/250 0.509), "
            "not own inventory (0.41-0.57); fills are posture-enriched (0.82-0.86 per filled order) by the takers' choice; futures-move rules add <= +0.01 per "
            "fill; the class-(ii) volatility scale is not identifiable out of sample. ",
    "price": "Iteration 14: unchanged. ",
    "size": "Iteration 14: pairing bids follow only ~1/5 of imbalance states even when they persist >= 5 s (0.22, placebo 0.002). ",
    "exit": "Iteration 14: one taker batch per order raises a strict replay's return by 5-7 points but not its window correlation (0.213 vs 0.207; oracle "
            "ceiling 0.47-0.53). ",
}
for k, v in pre.items():
    comp[k]["description"] = v + comp[k]["description"]
s["strategy_statement"] = (
    "[engine: VALIDATE-only] One engine family runs three accounts with three owner keys whose fill sides move together; the operator reconfigures it "
    "every few days to weeks and switches modules off by hand. [selection: hypothesis] It quotes nearly every crypto Up/Down window of the modules it runs; "
    "BTC 5m is switched off on weekend evenings (~18:15-18:30 ET) and ad hoc after losing stretches (no fixed drawdown level); with BTC 5m/15m off it runs "
    "small non-schedule orders on BTC 4h/hourly/daily, ETH and XRP. [timing: VALIDATE-only] It re-prices on each Chainlink report just after the public RTDS "
    "relay publishes it (tracer re-signs track the report stamped ~1.25 s earlier, no lead) and follows the moving mid after Binance moves; 73% of its fills "
    "are fresh posts at the touch a median 0.9 s before the fill; it stops filling ~43 s plus the settlement lookback before the end. [side: VALIDATE-only "
    "(public part); own-state description otherwise] Its uncensored at-touch quote follows the Chainlink posture computed from the report "
    "just published (stamp <= post - 1.0 s, sigma 1.0 x the 300-s futures-mid sigma): 0.81 per post on the 500 ladder out of sample within 10-31 14-18 "
    "(the 62/250 posts at chance with the R8 form); its fills follow the posture more (0.82-0.86 per filled order on the exact live clock, 0.69 per fill on the lot block "
    "clock) because takers fill the posture-side posts; in September its fills followed the cheaper token (0.71). [price: exam-verified (block clock) / "
    "VALIDATE-only (in-block and match clock)] Fill price = the last clean trade before the fill minus a tick (0.80 in-block, 0.83-0.86 match clock). "
    "[size: VALIDATE-only] 500 x 2^k rungs in the US session, 62/250 outside, plus imbalance-sized pairing bids for ~1/5 of imbalance states. [exit: "
    "VALIDATE-only] Each order serves one taker batch and is cancelled; it holds to resolution, merges ~65 s before the end. [economics: VALIDATE-only] "
    "September maker fills earned +8.3% per $ spread over all taker populations (buying the cheaper token below its probability); in October (+0.6%) the "
    "best counterparties left (-63%) and its fills against round-USD retail moved to the favourite and lost 11%; a strict-fill replay of the decoded quote "
    "loses 6-17% and tracks its window PnL at <= 0.23.")
tm = s["target_metrics"]
tm["_notes"] = tm.get("_notes", "") + (" Iteration 14: unchanged (R8 kept; no frozen decision changed). Pivot tests: uncensored quote unit side 0.733 "
                                       "(posture), event-time presence 0.805 vs 0.774, quote-geometry selection 0.558 (model 0.742 / recall 0.42 at lift 3), "
                                       "batch-capped replay 0.213 / 0.214.")
s["hypotheses"] += [
    {"id": "H14-LAGGED-QUOTE", "family": "D1/D2 uncensored quote unit", "description": "one lagged-quote law: at-touch posts on the outcome that fell",
     "validate_metrics": {"posture": 0.733, "fell_on_moving_W0.5": 0.180, "rose_on_moving_W0.5": 0.820, "rose_else_posture": 0.743, "62_250_posture": 0.509},
     "verdict": "rejected: reversed on unfilled posts (fill selection)"},
    {"id": "H14-EVENT-PRESENCE", "family": "D1 unit (1-s event time)", "description": "fill presence at 1-s on the match clock",
     "validate_metrics": {"rule": 0.805, "activity": 0.774, "gain": 0.031}, "verdict": "gain unchanged (+0.03)"},
    {"id": "H14-SEL-GEOMETRY", "family": "selection (print)", "description": "fixed quote-geometry print score",
     "validate_metrics": {"geo_auc": 0.558, "act_post_auc": 0.742, "act_auc": 0.683, "act_post_recall_lift3": 0.42}, "verdict": "rejected"},
    {"id": "H14-TWO-REGIME", "family": "side", "description": "futures-move two-regime rule per fill", "validate_metrics": {"test": 0.825, "posture": 0.815},
     "verdict": "+0.010, not adopted"},
    {"id": "H14-VOL-CLASS2", "family": "side", "description": "class-(ii) vol scale", "validate_metrics": {"fit_best": 0.760, "test_of_fit_best": 0.541},
     "verdict": "rejected out of sample"},
    {"id": "H14-BATCH1", "family": "D3 replay", "description": "one taker batch per order", "validate_metrics": {"corr": [0.213, 0.214], "return": -0.107,
                                                                                                                 "oracle": [0.472, 0.530]},
     "verdict": "return +6 points; correlation unchanged"},
    {"id": "H14-TRIP", "family": "selection (own state)", "description": "drawdown trip", "validate_metrics": {"auc_dd_day": [0.875, 0.822, 0.927],
                                                                                                              "levels_usd": [1129, 14555]},
     "verdict": "associated, no fixed threshold"},
    {"id": "H14-WHO-PAID", "family": "D4/C3 economics", "description": "taker populations Sept -> Oct",
     "validate_metrics": {"sep_return": 0.083, "oct_return": 0.006, "round_usd_sep": 0.092, "round_usd_oct": -0.112, "top20_share_drop": -0.63},
     "verdict": "no single population; side change against retail + exit of top counterparties"},
]
tml = s.setdefault("target_metrics_live", {})
tml["quote_unit_side_iter14"] = {"rule": "posture at the post, Chainlink stamp <= t - 1,000 ms, priceToBeat, 1.0 x futures-mid sigma300",
                                 "fit_10-31_14-16": 0.8146, "test_10-31_16-18": 0.8111, "dx_clob_form_15:53-18:00": 0.8043, "n_dx": 2575,
                                 "baselines_dx": {"always_up": 0.506, "cheaper": 0.4392, "mid_rose_1s": 0.6481},
                                 "per_filled_order_match_clock_R8_form": [0.855, 0.815], "note": "unit = post at the touch (exact 500/1000 adds; ~12% "
                                 "other makers); reported by evaluate() as quote_unit_side; a second development block is pending (X160)"}
if scan:
    s["hypotheses"].append({"id": "H14-QU-SCAN", "family": "side (quote unit)", "description": "posture parameters and accuracy by |F - mid| on the quote unit",
                            "validate_metrics": {"best_on_fit": scan.get("best_on_fit"), "frozen": scan.get("frozen_L1250_k1.4"),
                                                 "by_abs_edge": scan.get("by_abs_edge")}, "verdict": "see NOTES"})
s["data_sources"] += ["iteration 14: Arbitrum One public RPC arb1.arbitrum.io/rpc (eth_getLogs on the GMX v2 EventEmitter: OraclePriceUpdate = Chainlink "
                      "Data Streams values; publicnode needs an archive token, drpc free plan limits ranges)",
                      "iteration 14: stable-sample taker tapes re-read from the HTTP cache (code13/fetch_stable.py, 1,488 windows)"]
s["iterations"].append({"n": 14, "minutes": 100, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half, aggregate)",
                        "paradigm": "pivot: the uncensored quote unit (every at-touch post, filled or not) and event time (1-s match clock) instead of fills in "
                                    "10-s bins; the side as a lagged partial-adjustment pricer on the fast reference; selection by quote geometry; the order "
                                    "life cycle in the replay; plus the exam-lot scope, the switch-off controller and who paid the profitable version",
                        "families": ["X146 lagged-quote law on the uncensored quote unit (T1)", "X148 two-regime futures rule per fill (T2)",
                                     "X149 class-(ii) volatility scale (T3)", "X151 weekend-analog scope (T5)", "X147 event-time presence (T6)",
                                     "X150 quote-geometry print selection", "X153 pass multiplicity on the quote unit", "X154 one-batch replay",
                                     "X152 drawdown trip (light)", "X159 who paid (taker populations Sept -> Oct)", "X155 pairing on persisting states",
                                     "X156 GMX on-chain Chainlink Data Streams probe", "X133 aggregate exposure and the entry side",
                                     "quote-unit inventory and posture parameter scan"]})
s["status"] = "continue"
s["wall_reason"] = None
P.write_text(json.dumps(s, indent=1))
print("open:", sorted([k for k, v in c.items() if v.get("status") == "open"], key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0)))
