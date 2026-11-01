"""Iteration 11: update state.json (catalog with the iteration-10 panel items X101-X113, components, target_metrics,
best, hypotheses, data sources, iteration entry). Reads the iteration-11 result files.
    python code11/update_state11.py <minutes>
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parent
S = json.loads((WS / "state.json").read_text())
R = WS / "results"
rep = json.loads((R / "iter11_replay.json").read_text())
orc = json.loads((R / "iter11_replay_oracle.json").read_text())
frz = json.loads((R / "iter11_replay_frozen.json").read_text())
ib = json.loads((R / "iter11_inblock_price_all.json").read_text())
ib15 = json.loads((R / "iter11_inblock_price_15m.json").read_text())
ws = json.loads((R / "iter11_window_side.json").read_text())
ft = json.loads((R / "iter11_fill_type.json").read_text())
fast = json.loads((R / "iter11_replay_fast.json").read_text())
si = json.loads((R / "iter11_side_inblock.json").read_text())
ec = json.loads((R / "iter11_entry_combo.json").read_text())
ef = json.loads((R / "iter11_entry_flow.json").read_text())
ipool = json.loads((R / "iter11_inblock_pooled.json").read_text())
minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 95
cat = S["catalog"]


def setc(k, status, evidence, source=None):
    old = cat.get(k, {})
    ev = (old.get("evidence", "") + " | iteration 11: " + evidence) if old.get("evidence") and source is None else \
        ((f"source: {source}. " if source else "") + evidence)
    cat[k] = {"status": status, "evidence": ev}


v5 = ib["validate"]
n5, n15 = v5["fills"], ib15["validate"]["fills"]
pooled_in = (v5["inblock_within_tick"] * n5 + ib15["validate"]["inblock_within_tick"] * n15) / (n5 + n15)
pooled_blk = (v5["block_clock_within_tick"] * n5 + ib15["validate"]["block_clock_within_tick"] * n15) / (n5 + n15)
fv = frz["posture_delta0.01_qsess_L2_strict"]["validate"]
fs = frz["posture_delta0.01_qsess_L2_strict"]["study"]
ov = orc["d0.01_qsess"]["validate"]
os_ = orc["d0.01_qsess"]["study"]

# ---- new catalog items from the iteration-10 panel
setc("X101", "open", "R7-price done: the in-block execution order (eth_getBlockByNumber) as a recording-free match clock for the "
     f"price rule; all {n5} VALIDATE BTC 5m maker fills {v5['inblock_within_tick']:.3f} vs block clock {v5['block_clock_within_tick']:.3f} "
     f"(gain {v5['gain']:+.3f}, 2-h block bootstrap {v5['gain_ci95_2h_blocks']}), per wallet {v5['per_wallet_inblock']}, halves "
     f"{v5['halves_inblock']}; BTC 15m {ib15['validate']['inblock_within_tick']:.3f} vs {ib15['validate']['block_clock_within_tick']:.3f}; "
     f"pooled {pooled_in:.3f}; adopted (pre-registered 00:43 UTC); in evaluate() as price_inblock / price_r7 (match clock where recorded, else "
     "in-block; smoke test 10-31 15:40-16:40: block 0.625, in-block 0.719, match 0.849, R7 0.843). Open: the recorder successors before "
     "11-03 00:00 and the side/selection parts of the recording-free path.",
     source="panel iter10 information I10-1 (recording-free evaluation path and recorder continuity)")
setc("X102", "open", "Not run: needs ~26-52k crypto-price requests (every 1-2 s of [S-65, E] of consecutive window pairs), ~5-10 h at the "
     "polite rate after the running X90 queue (done 9.5k of 46.6k at 01:03 UTC). Planned for the next iteration.",
     source="panel iter10 information I10-2 (print-level selection with the endpoint Chainlink posture, size mode, calendar gate)")
setc("X103", "open", "Needs the 11-01 06-12 development block (full-depth recorder scheduled 05:55-12:00).",
     source="panel iter10 information I10-3 (off-session ladder re-post race; pmxt replication)")
setc("X104", "open", "Partial: fill matching type on the lot (code11/fill_type.py): complement mints are "
     f"{ft['study']['type_share'].get('mint')} (STUDY) / {ft['validate']['type_share'].get('mint')} (VALIDATE) of the maker fills; the bought "
     f"token is the favourite in {ft['study']['fav_share_by_type']} / {ft['validate']['fav_share_by_type']}; the taker classification by "
     "signature type / round USD / repeat address is not done. Market-only taker-flow baseline for the entry (code11/entry_flow.py): "
     "the cluster's first fill is on the outcome the clean-tape takers were NOT net-buying in the previous 10-60 s 0.60-0.66 (STUDY) / "
     "0.58-0.61 (VALIDATE); net side in one-sided windows 0.57-0.62 / 0.52-0.59: stable across the halves (unlike the favourite), below "
     "the real-Chainlink posture at the entry (0.66 / 0.72, iteration 10).",
     source="panel iter10 information I10-4 (taker populations of the off-session ladder)")
setc("X105", "open", "Not run (endpoint runs on 10-30 12-24).", source="panel iter10 information I10-5 (Chainlink noise-regime onset)")
setc("X106", "tried", "Strict-fill window replay (code11/replay.py, replay_score.py, replay_keys.py, replay_oracle.py, replay_frozen.py): "
     f"240 configurations x 2,291 lot BTC 5m windows. Frozen posture at the rule's price (last print - 0.01), session size, latency 2 s, "
     f"slack 2: per-window PnL corr STUDY {fs['pooled']} / VALIDATE {fv['pooled']} (return {fv['replay_return']}); STUDY-chosen favourite "
     "rule 0.286 / 0.174 on STUDY reverses to -0.103 / -0.082 on VALIDATE; ORACLE side (the cluster's own terminal net side) "
     f"STUDY {os_} / VALIDATE {ov}: the outcome bar sits at the ceiling of a perfect window side under strict fills. Fast clock "
     f"(execution order, latency ~0, code11/replay_fast.py): posture {fast['posture_d0.01']['validate']['corr']} (return "
     f"{fast['posture_d0.01']['validate']['return']}), two-sided {fast['two_d0.0']['validate']['corr']}, oracle side "
     f"{fast['oracle_d0.0']['validate']['corr']}: speed removes the adverse selection (return -16% -> ~0%) but not the side gap.",
     source="panel iter10 mechanics P1 (window terminal net position and the strict-fill replay as a state machine)")
setc("X107", "open", "Not run.", source="panel iter10 mechanics P2 (size configuration as a controller state; reset clock and driver)")
sp_ = json.loads((R / "iter11_salt_pass.json").read_text())
setc("X108", "tried", "code11/salt_pass.py on the lot calldata (b1_cluster_orders_*): pairs of filled maker BUY orders of one wallet in one "
     "market with 0 < delta salt <= 40 (~3 s of signing): on the other outcome "
     f"{sp_['study']['all']['other_outcome_share']} (STUDY, {sp_['study']['all']['pairs']} pairs) / {sp_['validate']['all']['other_outcome_share']} "
     f"(VALIDATE, {sp_['validate']['all']['pairs']}) vs a within-(wallet, market) permutation null {sp_['study']['all']['null_mean']} / "
     f"{sp_['validate']['all']['null_mean']}; off-session {sp_['validate']['off_00_12']['other_outcome_share']} vs {sp_['validate']['off_00_12']['null_mean']}, "
     f"62/250 {sp_['validate']['62/250']['other_outcome_share']} vs {sp_['validate']['62/250']['null_mean']}, 500 {sp_['validate']['500']['other_outcome_share']} "
     f"vs {sp_['validate']['500']['null_mean']}. The 62/250 ladder looks exactly like the one-sided 500 ladder on this statistic, but because "
     "filled rungs live ~0.5-1.5 s the test is confounded with one-sided taker bursts and cannot separate one-sided passes from "
     "taker-chosen sides by itself.", source="panel iter10 mechanics P3 (same-pass salt adjacency on the whole lot from calldata)")
setc("X109", "tried", f"code11/window_side.py: one-sided windows (>= 70% of shares) STUDY {ws['study']['one_sided']} / VALIDATE "
     f"{ws['validate']['one_sided']}; time-weighted posture majority vs net side {ws['study']['posture_majority_vs_net_side']} / "
     f"{ws['validate']['posture_majority_vs_net_side']}; posture at the first quoting second {ws['study']['entry_posture_vs_net_side']} / "
     f"{ws['validate']['entry_posture_vs_net_side']}; first fill side = net side {ws['study']['first_fill_side_vs_net_side']} / "
     f"{ws['validate']['first_fill_side_vs_net_side']}; the net side won {ws['study']['net_side_won']} / {ws['validate']['net_side_won']}; strict "
     "replays' net side 0.38-0.63 / 0.32-0.71. No public window rule reaches 0.80.",
     source="panel iter10 mechanics P4 (re-scope the side to the window entry / net side)")
setc("X110", "tried", "Pick-off side (the outcome the last Binance second moved against) in the window replay: net side 0.44-0.53 "
     "(STUDY) / 0.68-0.70 (VALIDATE), PnL corr 0.10-0.20 / 0.10-0.19, no better than the posture or a two-sided ladder; the mechanics "
     "panel's match-clock test found no ms peak (0.43-0.58, 10-26) and the information panel no trigger spike.",
     source="panel iter10 assumptions P1 (off-session fill side = Binance pick-off)")
setc("X111", "open", "Partial (code11/fill_type.py, iter11_fav_by_block.json, replay by day): the favourite share of the maker fills falls "
     "by day 0.59, 0.56, 0.53, 0.45 (10-23..26), 0.36, 0.37, 0.29, 0.25 (10-27..30); per 6-h block 0.37-0.76 (STUDY) and 0.20-0.59 "
     "(VALIDATE; 10-28 18-24 0.59): a noisy drift with steps near 10-26 12:00 and 10-27 12:00, not one break; realised vol rose (v300 at "
     "fills 2.5-4.1e-5 STUDY days, 2.9-6.0e-5 VALIDATE) and DVOL stayed 37-40. The counterparty and engine-fingerprint steps are not done.",
     source="panel iter10 assumptions P2 (the 10-27 regime break)")
setc("X112", "open", "Partial: the price part of a recording-free unit exists (R7-price in-block); print-level selection on shared-only "
     "inputs is not scored yet (needs X102's Chainlink seconds or the 11-01 blocks).",
     source="panel iter10 assumptions P3 (an exam unit the whole next lot supports)")
setc("X113", "open", "Not run.", source="panel iter10 assumptions P4 (size configuration epochs)")
# ---- existing items closed or updated
setc("D3", "tried", f"strict-fill window replay built (code11/replay.py): frozen posture VALIDATE per-window PnL corr {fv['pooled']}, oracle "
     f"side ceiling {ov} (X106).")
setc("X64", "tried", f"done as X106: a strict-fill replay of the decoded generator (posture side, last print - 0.01, schedule size, stop "
     f"30 s before the end) against the public taker tape: VALIDATE {fv['pooled']}, oracle-side ceiling {ov}; the generator's touch fills "
     "(fresh posts) cannot be credited by trade-through fills on block-stamped prints.")

# ---- components
comp = S["components"]
comp["price"] = {"confidence": 0.75, "tag": "exam-verified (block clock); VALIDATE-only (in-block clock, match clock)",
                 "description": f"fill price = last clean trade of the market before the fill minus 0.01 (the trivial anchor 'last print' minus a "
                                f"tick). Historical VALIDATE: block clock {pooled_blk:.3f} pooled 5m+15m; in-block execution order (R7, recording-free) "
                                f"{pooled_in:.3f} pooled (5m {v5['inblock_within_tick']:.3f}, all {n5} fills; 15m {ib15['validate']['inblock_within_tick']:.3f}), "
                                f"trivial 'last print' with no offset {v5['inblock_last_print_no_offset_within_tick']:.3f}; live match clock 0.83-0.86 "
                                "(10-31 15:40-16:40: block 0.625 / in-block 0.719 / match 0.849). The ladder hangs off each market's own mid with a "
                                "~0.2 Chainlink skew (live)."}
comp["exit"]["description"] += (f" Iteration 11: a strict-fill window replay of the decoded quote reaches per-window PnL corr {fv['pooled']} on "
                                f"VALIDATE; even an oracle window side reaches only {ov}: the window PnL is made of touch fills of fresh quotes.")
comp["side"]["description"] += (f" Iteration 11 (window unit): first fill side = terminal net side 0.90 STUDY / 0.81 VALIDATE; the net side "
                                f"won 0.62 / 0.33 (favourite share of fills by day 0.59 -> 0.25 across 10-23..30); fill-free posture majority 0.43 / 0.63, "
                                "entry posture 0.57 / 0.57: no public window rule reaches 0.80; the fill side follows the takers' demand (81-88% complement mints).")
comp["selection"]["description"] += " Iteration 11: unchanged."
S["components"] = comp

# ---- target metrics (best rule R7 = R6 + in-block price; outcome now the strict replay, the target's definition)
tm = S["target_metrics"]
tm_old = {k: tm.get(k) for k in ("price_within_tick", "pnl_corr_pearson", "pnl_corr_spearman")}
tm["price_within_tick"] = round(pooled_in, 4)
tm["pnl_corr_pearson"] = fv["pooled"][0]
tm["pnl_corr_spearman"] = fv["pooled"][1]
tm["_notes"] = (tm.get("_notes", "") + f" Iteration 11 (R7 = R6 + in-block price): price_within_tick = the in-block execution-order clock "
                f"pooled BTC 5m + 15m on all {ipool['pooled_n']} VALIDATE maker fills ({ipool['pooled_validate']:.4f}; block clock {pooled_blk:.4f}; "
                f"pooled per wallet {ipool['pooled_validate_per_wallet']}, halves {ipool['pooled_validate_halves']}; 15m per wallet "
                f"{ipool['btc15m_validate_per_wallet']}; the rule is the trivial anchor 'last print' minus a tick on this clock, 'last print' "
                f"alone {v5['inblock_last_print_no_offset_within_tick']:.3f} on 5m); pnl_corr = the strict-fill window replay of the frozen posture "
                f"quote (BTC 5m, latency 2 s, slack 2, trade-through, last print - 0.01, session size; the target's definition), per wallet "
                f"almach {fv.get('almach')}, bosona {fv.get('bosona')}, mo-money {fv.get('momoney')}; halves "
                f"{frz['posture_delta0.01_qsess_L2_strict']['validate_h1']['pooled']} / {frz['posture_delta0.01_qsess_L2_strict']['validate_h2']['pooled']}; "
                f"oracle-side ceiling {ov}. Before: price {tm_old['price_within_tick']} (block clock), pnl {tm_old['pnl_corr_pearson']} / "
                f"{tm_old['pnl_corr_spearman']} (expectation proxy, union).")
S["target_metrics"] = tm
S["best"] = {"rule_id": "R7 = R6 + in-block execution-order price clock (recording-free R4)", "validate_metrics": {
    "historical_union": dict(tm), "live": S["best"].get("validate_metrics", {}).get("live", {}),
    "iter11_replay": {"frozen_posture_strict": frz["posture_delta0.01_qsess_L2_strict"], "oracle_side": orc}}}

# ---- hypotheses
S["hypotheses"] += [
    {"id": "H11-REPLAY", "family": "X106/D3/X64", "description": "strict-fill window replay of a one-sided posture ladder (and other side rules) "
     "reproduces the cluster's per-window PnL", "validate_metrics": {"frozen_posture": fv, "study_choice_favourite_validate": rep["frozen_validate"]["corr_has"],
                                                                    "oracle_side": ov, "by_side_validate": rep["validate_by_side_frozen_params"]},
     "verdict": "rejected as a route to the outcome bar: <= 0.25 for every public side rule, ceiling 0.47 / 0.53 with an oracle side"},
    {"id": "H11-R7PRICE", "family": "X101", "description": "price rule on the in-block execution-order clock", "validate_metrics": ib,
     "verdict": "adopted (pre-registered): VALIDATE +0.098 [0.084, 0.111]"},
    {"id": "H11-FASTREPLAY", "family": "X106", "description": "window replay on the execution-order clock (latency ~0)",
     "validate_metrics": {k: v["validate"] for k, v in fast.items()}, "verdict": "posture 0.18-0.23 / 0.24-0.26; oracle side 0.46-0.49 / 0.52-0.53: side-bound"},
    {"id": "H11-SIDE-INBLOCK", "family": "X101/side", "description": "per-fill posture with the in-block mid instead of b - 3 (pre-registered 01:06 UTC)",
     "validate_metrics": si["validate"], "verdict": "not adopted (gain +0.007 [-0.008, +0.021])"},
    {"id": "H11-ENTRY-COMBO", "family": "X104/X106", "description": "entry side = real-Chainlink posture at the first fill, with the market-only "
     "taker-flow complement (net clean taker demand over the previous 30 s) as a second vote (exploratory, not pre-registered)",
     "validate_metrics": {"combo": ec["validate"], "flow_baseline": ef["validate"]}, "verdict": "exploratory: 0.82 where both agree (53% of windows), "
     "posture alone 0.744, flow alone 0.592; pre-registered for 11-01 06-12"},
    {"id": "H11-WINSIDE", "family": "X109", "description": "window net side from fill-free public rules", "validate_metrics": ws["validate"],
     "verdict": "not met (best 0.63)"},
    {"id": "H11-FILLTYPE", "family": "X104/X111", "description": "fill matching type and the favourite-share drift", "validate_metrics": ft["validate"],
     "verdict": "descriptive: mints 88%, favourite share drifts 0.59 -> 0.25"},
]
S["data_sources"] += ["iteration 11: Polygon eth_getBlockByNumber(block, false) transaction order for every block with a lot BTC 5m / 15m "
                      "cluster fill (14,301 + 1,932 blocks, publicnode/drpc, 0 failures): the in-block execution-order clock"]
S["status"] = "continue"
S["strategy_statement"] = (
    "[engine: VALIDATE-only] One engine family (timestamp-0 orders, per-wallet salt counters reset by the daily ~01:00 UTC restart) runs "
    "three wallets. [selection: hypothesis] It quotes nearly every crypto Up/Down window of the modules it runs; BTC 5m/15m are switched "
    "off for hours, mostly Fri-Sun US-Eastern evenings. [timing: VALIDATE-only] It re-prices on each Chainlink report within ~0-150 ms of "
    "the RTDS relay and after Binance moves; its filled orders are fresh posts at the touch. [side: VALIDATE-only for the US-session 500 "
    "ladder, hypothesis elsewhere] Its 500-share rungs buy the outcome whose Chainlink edge over the Polymarket mid is positive (live 0.79 "
    "per fill, 0.93-0.97 where the reference and the market disagree, historically too); the off-session 62/250 ladder follows no public "
    "reference; per window the first fill sets the terminal net side (0.81-0.90), and the net side moved from the favourite (won 62%, "
    "10-23..26) to the underdog (won 33%, 10-27..30) while 81-88% of its fills are complementary mints, i.e. the fill side follows what the "
    "takers buy. [price: exam-verified (block clock) / VALIDATE-only (in-block and match clock)] Fill price = the last clean trade before "
    f"the fill minus a tick: {pooled_in:.2f} within a tick on the in-block execution order (recording-free), 0.83-0.86 on the live match clock. "
    "[size: VALIDATE-only] 500 x 2^k schedule rungs in the US session, 62/250 outside, plus imbalance-sized pairing bids. [exit: "
    "VALIDATE-only] Holds to resolution, completes pairs, merges ~65 s before the end. [economics: VALIDATE-only] It earns as a fast "
    "two-sided-at-the-touch maker with a Chainlink skew: a strict-fill replay of its decoded quote loses 15-17% and tracks its window PnL "
    f"at only {fv['pooled'][0]:.2f} / {fv['pooled'][1]:.2f} (oracle side {ov[0]:.2f} / {ov[1]:.2f}), because its profit comes from touch fills "
    "of quotes refreshed within ~0.1-1 s, which a 2-s-latency replay on block-stamped prints cannot obtain.")
S["iterations"].append({"n": 11, "minutes": minutes, "best_validate_score": 0.716,
                        "validate_definition": "2026-10-27..30 (lot second half, aggregate)",
                        "paradigm": "the window as the unit of decision with an executable state machine (strict-fill replay of the quote), "
                                    "plus a new data source for the price clock (the on-chain execution order inside each block)",
                        "families": ["X106/D3/X64 strict-fill window replay (240 configs, oracle-side ceiling)", "X109 window net side",
                                     "X110 pick-off side in the replay", "X101 R7-price in-block execution-order clock (5m all fills, 15m all fills)",
                                     "X104/X111 fill matching type and the favourite-share drift by day and 6-h block",
                                     "evaluate() R7 smoke test on 10-31 15:40-16:40"],
                        "ended_utc": "2026-11-01 01:55"})
(WS / "state.json").write_text(json.dumps(S, indent=1, default=str))
print("open:", [k for k, v in cat.items() if v.get("status") == "open"])
print("price", round(pooled_in, 4), "pnl", fv["pooled"])
