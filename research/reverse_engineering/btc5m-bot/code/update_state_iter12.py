"""Iteration 12: update state.json (catalog X100-X112 from the iteration-11 panel, the exposure-tracker PnL rule, target_metrics,
components, strategy statement, hypotheses, data_sources, iterations).
Usage: python update_state_iter12.py MINUTES"""
import os, json, shutil, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
P = _ROOT + "/research/reverse_engineering/btc5m-bot/state.json"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
shutil.copy(P, _ROOT + "/.cache/re/btc5m-bot/state_backup_iter11.json")
s = json.load(open(P, encoding="utf-8"))
MIN = float(sys.argv[1]) if len(sys.argv) > 1 else None


def J(name):
    p = f"{R}/{name}"
    return json.load(open(p)) if os.path.exists(p) else None


t_nf, t_avg, t_b, t_e3 = J("track12.json"), J("track12_avg.json"), J("track12_nf12b.json"), J("track12_ens3.json")
n12, n12b, n12c, fv, cb, rg, net, sm = J("nf12.json"), J("nf12b.json"), J("nf12c.json"), J("fvnet12.json"), J("cbx12.json"), J("regime12.json"), J("net12.json"), J("smoke12.json")
tg, n12m, bsl = J("trkgain12.json"), J("nf12m.json"), J("blkslow12.json")
# pre-registered choice of the PnL rule: avg (pre-registration 2) unless ens3 beats it on BOTH pooled Pearson and Spearman (pre-registration 3)
prim, prim_name = t_avg["trk_a"], "trk_a_avg (0.5 it4b netflow + 0.5 nf12b)"
if t_e3 and t_e3["trk_a"]["pnl_corr_pool"]["pearson"] > prim["pnl_corr_pool"]["pearson"] and t_e3["trk_a"]["pnl_corr_pool"]["spearman"] > prim["pnl_corr_pool"]["spearman"]:
    prim, prim_name = t_e3["trk_a"], "trk_a_ens3 ((it4b netflow + nf12b + nf12c) / 3)"
ENS3_WON = prim_name.startswith("trk_a_ens3")

cat = s["catalog"]
I11 = "panel iteration 11"
cbA, cbC = (cb or {}).get("fit_A_score_C", {}), (cb or {}).get("fit_C_score_A", {})
cat["X100"] = {"status": "open", "source": f"{I11}, information P1 (cross-venue divergence gate: take Binance-led moves the US / EU venues have not reflected; London-arrival order)",
               "evidence": "Step 1 tried on 10-31 A / C with the recorded Coinbase ticker (cbx12.py, results/cbx12.json; class over [tau - 500, tau + 70) ms pre-registered: N no trade, M mid "
                           "moved >= 0.1 bp toward o, S otherwise). Price-level events: P(take) N / S / M = "
                           f"{json.dumps({k: (cb or {}).get(h, {}).get('take_by_class', {}).get('PRICE') for k, h in (('A', 'A'), ('C', 'C'))})} (N is only 23 / 7 events); size-only events: M raises "
                           "the take 3-4x (DEPLETE A 0.239 vs 0.054-0.059, C 0.184 vs 0.044-0.046): confirmation for weak ticks, a freshness gate for strong ones. Out-of-sample AUC of the "
                           f"evt10-style FULL logistic + Coinbase class: fit A score C {cbA.get('auc_full')} -> {cbA.get('auc_full_plus_coinbase')} (gain {cbA.get('gain')}, window-block CI "
                           f"{cbA.get('gain_ci95_window_blocks')}); fit C score A {cbC.get('auc_full')} -> {cbC.get('auc_full_plus_coinbase')} (gain {cbC.get('gain')}, CI {cbC.get('gain_ci95_window_blocks')}). "
                           "A small replicated gain, far from deciding the take. Step 2 (pre-registered scoring of 11-01 06-12 with rec_eu11 Coinbase level2_50, Bitstamp, Kraken and the "
                           "London-arrival clock) needs the next development block. Open."}
co = J("coat12.json") or {}
cat["X101"] = {"status": "open", "source": f"{I11}, information P2 (shared-actionability instrument: the independent fast crowd as a second label; conditional-independence test of every candidate input)",
               "evidence": "Steps 1-2 tried for the recorded onset design (coat12.py, results/coat12.json; fast crowd = non-operator taker BUYs of o with sign-to-match 180-400 ms matched in "
                           f"[tau + 150, tau + 700) ms; {co.get('fast_crowd_orders')} orders, {co.get('fast_crowd_wallets')} wallets; diagnostic only). Co-take: A {json.dumps((co.get('A') or {}).get('co_take'))}; "
                           f"C {json.dumps((co.get('C') or {}).get('co_take'))}. Conditional on the evt10-style FULL design the crowd log OR falls only from "
                           f"{((co.get('A') or {}).get('conditional') or {}).get('none', {}).get('crowd_log_OR')} to {((co.get('A') or {}).get('conditional') or {}).get('FULL', {}).get('crowd_log_OR')} (A) and from "
                           f"{((co.get('C') or {}).get('conditional') or {}).get('none', {}).get('crowd_log_OR')} to {((co.get('C') or {}).get('conditional') or {}).get('FULL', {}).get('crowd_log_OR')} (C): the recorded "
                           "inputs explain 14-21% of the shared selection, Coinbase adds nothing to that. Most of what the cluster and the fast crowd share is outside the recorded design. "
                           "Caveat: the crowd window does not exclude orders signed after the cluster's match became visible. Open: the other candidate inputs (11-01 feeds: Bitstamp, "
                           "Kraken, depth5, PolyBolt touch, alt perps) and step 3 (the selector fitted on the crowd's takes, transferred)."}
cat["X102"] = {"status": "open", "source": f"{I11}, information P3 (pre-signed peer census: clones of the same TypeScript ladder bot and siblings on other burst schedules)",
               "evidence": "Not tested in iteration 12. Open."}
cat["X103"] = {"status": "tried", "source": f"{I11}, information P4 (the bot's private channel: does its own fill re-arm the take? won vs exogenously lost races)",
               "evidence": "The core signature was measured on development data by the iteration-11 mechanics panel (panels/iter11_mechanics.md): after a WON race the operator decides again on "
                           "the same outcome within 1 s 33.4% of the time, after a race LOST to a queued crowd order (exogenous) 33.3%: fills do not re-arm presence. Iteration 12 regime12.py "
                           "(per-wallet decomposition, 120-s segment FE): a wallet's take does not rise with its OWN recent decisions (beta_own <= 0) but with the OTHER wallets' (beta_other "
                           "> 0), an operator-level state, not a per-wallet fill channel. The ms-scale kink test at m + 5-50 ms was not run; with equal 1-s re-fire rates it cannot carry a "
                           "large effect. Tried: no fill re-arming."}
cat["X104"] = {"status": "open", "source": f"{I11}, mechanics P1 (two archived live labs: 07-01 and 08-01 from pmxt plus the Tardis free days; decode the selection by bot version)",
               "evidence": "Not tested in iteration 12 (the pmxt range reader of iteration 11 is the route; ~100-115 MB of range requests per hour). Open."}
cat["X105"] = {"status": "open", "source": f"{I11}, mechanics P2 (recover the PRNG with the measured signing-loop layout fixing the generation offsets)",
               "evidence": "Not tested in iteration 12 (with X99). Open."}
r6 = {k: (rg or {}).get(k, {}).get("per_wallet_own_vs_other") for k in ("A", "C")}
cat["X106"] = {"status": "tried", "source": f"{I11}, mechanics P3 (where the persistent state lives: per-wallet executor processes or one operator-level strategy state)",
               "evidence": "regime12.py (results/regime12.json; onset tables of 10-31, decisions from large_dec): linear probability model of 'wallet w decides on o in [tau + 150, tau + 700) ms' "
                           "on log(1 + w's own decisions on the window in the last 30 s) and log(1 + the other wallets'), |bp| and class, with 120-s segment FE (and window FE): "
                           f"{json.dumps(r6)}. Own-recent beta is ~0 or negative (refractory slot), other-wallet beta positive: the persistent state is operator-level and the wallets "
                           "are slots. Steps 2-4 (joint-take excess, rerouting while a wallet is busy, archive days) not run."}
cat["X107"] = {"status": "open", "source": f"{I11}, mechanics P4 (the exit as a slot discipline: cancel then send, sub-5-share remainders dropped, in the recorded-book simulator)",
               "evidence": "Not tested in iteration 12. Open."}
cat["X108"] = {"status": "open", "source": f"{I11}, mechanics P5 (requote-echo anchors: fill-reactive makers re-sign 0-20 ms after the match, a ~10-ms historical clock)",
               "evidence": "Not tested in iteration 12 (with X89). Open."}
rA, rC = (rg or {}).get("A", {}), (rg or {}).get("C", {})
cat["X109"] = {"status": "open", "source": f"{I11}, assumptions P1 (decode the 1-2-minute regime the investigation called self-excitation)",
               "evidence": "Step 1 tried (regime12.py, 200 redraws of each onset inside its (window, L-segment), clean filter enforced, rec30 and label recomputed from the actual decisions): "
                           f"A: L300 {rA.get('L300')}, L120 {rA.get('L120')}, L60 {rA.get('L60')}; C: L300 {rC.get('L300')}, L120 {rC.get('L120')}, L60 {rC.get('L60')}. "
                           "Within 2-minute segments the own-recent coefficient sits inside the mechanical null; at 60 s it falls below it (refractory). Finding 13 of iteration 11 "
                           "('self-exciting internal state') is corrected: the latent is a slow 1-2-minute operator-level regime (X106). "
                           + (f"Step 5 (blkslow12.py, measurement only): the block-second presence model retrained on BUILD with outcome-signed slow spot-path features scores VALIDATE "
                              f"block seconds {(bsl or {}).get('auc_full_plus_slow')} vs the frozen {(bsl or {}).get('auc_full_frozen')} (pure baseline {(bsl or {}).get('auc_pure_baseline')}; "
                              f"slow minus frozen {json.dumps((bsl or {}).get('slow_minus_frozen_block_bootstrap_2h'))}; slow features {(bsl or {}).get('slow_importance_share')} of the gain). " if bsl else "")
                           + "Steps 2-4 (Hawkes vs Cox/HMM held-out likelihood, public regressors of the decoded state, refractory curve inside the 'on' state) open."}
w = (n12b or {}).get("validate_window_net_corr", {})
cat["X110"] = {"status": "tried", "source": f"{I11}, assumptions P2 (condition 5 as an exposure-path target; fit the bot's fair value on the window net)",
               "evidence": "The pivot of iteration 12. (1) PnL ~ net x outcome per VALIDATE window r 0.884 (net12.json). (2) Window-net predictability (BUILD-fit, VALIDATE-scored): it4b "
                           f"netflow sum 0.458, nf12 (with Gamma priceToBeat) {(n12 or {}).get('validate_window_net_corr', {}).get('nf12')}, nf12b (spot-only slow features) {w.get('nf12')}, "
                           f"average {w.get('avg')}" + (f", nf12c {(n12c or {}).get('validate_window_net_corr', {}).get('nf12c')}, three-model average {(n12c or {}).get('validate_window_net_corr', {}).get('avg3')}" if n12c else "")
                           + "; per-wallet models do not beat the pooled one. (3) Executable strict-fill EXPOSURE TRACKER (pre-registered): "
                           f"it4b target {t_nf['trk_a']['pnl_corr_pool']}, average target {t_avg['trk_a']['pnl_corr_pool']} (CI {t_avg['trk_a']['pnl_corr_pool_pearson_block_ci95']}), "
                           + (f"three-model target {t_e3['trk_a']['pnl_corr_pool']}; " if t_e3 else "") + f"primary {prim_name}. (4) FV decoding (fvnet12.json): current-minute move +, earlier "
                           "minutes -, previous window's outcome +; M1 / M2 and the spot-vs-strike gap do not replicate in sign BUILD vs VALIDATE: no strike-at-open or drifted FV. Tried."}
lk = J("lock12.json") or {}
cat["X111"] = {"status": "open", "source": f"{I11}, assumptions P3 (split decisions into time-locked and unlocked; judge new feeds by time-locking, not AUC lift)",
               "evidence": "Steps 1-2 tried (lock12.py, results/lock12.json; 2,155 live decisions of 10-31; locked = a net microprice move >= 0.1 bp toward o inside the kernel7 peak bin "
                           "+-25 ms of any of the seven series with excess >= 0.05; definition amended once, before any comparison was read, from 'any change' which flagged 98.5% vs "
                           f"97.6% placebo): P(locked) {lk.get('P_locked')} vs placebo {lk.get('P_locked_placebo')} -> locked excess {lk.get('locked_fraction_excess')} "
                           f"(by wallet {json.dumps(lk.get('by_wallet_locked_excess'))}). Locked vs unlocked: {json.dumps(lk.get('by_class'))}. The time-locked minority is the strong-tick, "
                           "large, early, more-winning snipe; ~90% of decisions have no sharp clock in the recorded feeds (61% without a six-series tick) and do not differ on the "
                           "underdog-since-open share. Step 3 (clocks for the unlocked decisions from the 11-01 feeds, composite crossing time) open."}
ct = J("ctrl12.json") or {}
cat["X112"] = {"status": "tried", "source": f"{I11}, assumptions P4 (a competition-aware controller: the regime is the bot's recent race success)",
               "evidence": "ctrl12.py (results/ctrl12.json): decisions of large_dec labelled won / lost (all 829 located lost races of ins9b_M matched); for every clean onset of 10-31 A / C "
                           "the operator's decisions on the window in [tau - 120 s, tau) and the share that won. P(take) by win-share tercile with the count held fixed: "
                           f"A {json.dumps((ct.get('A') or {}).get('by_count_bin'))}; C {json.dumps((ct.get('C') or {}).get('by_count_bin'))}. LPM win-share coefficient with 120-s FE "
                           f"A {(ct.get('A') or {}).get('lpm_win_share_coef_120s_fe')}, C {(ct.get('C') or {}).get('lpm_win_share_coef_120s_fe')}; window FE A {(ct.get('A') or {}).get('lpm_win_share_coef_window_fe')}, "
                           f"C {(ct.get('C') or {}).get('lpm_win_share_coef_window_fe')}. The signature (take after mostly won races >= 2x after mostly lost, count fixed) is absent: "
                           "high / low ratios 0.45-1.6 with inconsistent signs; with the mechanics panel's equal 1-s re-fire after won vs exogenously lost races (33.4% vs 33.3%), the "
                           "race-success controller is rejected. The exogenous-loss split (crowd queued ahead) and the crowd-count 'off'-state proxy were not run (no effect to split)."}
cat["X85"]["evidence"] = cat["X85"].get("evidence", "") + (" | Iteration 12 correction (regime12.py, X109 / X106): the own-recent effect is absorbed by 2-minute segment FE (inside a "
                                                           "200-draw redraw null) and reverses at 60 s; a wallet's take follows the OTHER wallets' recent decisions, not its own: the "
                                                           "window-level rate is a slow operator-level regime, not a self-exciting kernel.")
open_ids = sorted([k for k, v in cat.items() if v.get("status") == "open"], key=lambda k: (k[0], int(k[1:]) if k[1:].isdigit() else 0))
s["catalog_open_after_iteration12"] = open_ids

comp = s["components"]
comp["exit"]["description"] = ("Remainders and lost races rest as GTC bids at the old ask (cancelled never-filled remainders live DS median 328 ms, GF 240, XM 124); every position is held to "
                               "resolution; 87% of shares end paired at 0.979; TAKER_REBATE = 0.5 x the previous day's taker fees. Iteration 12, the INVENTORY PATH: per window PnL = net x "
                               "outcome (r 0.884); the net follows the current minute's BTC move (+), is bought back against the earlier minutes' moves (-) and leans with the previous "
                               "window's outcome (+); public models predict the window net at r 0.46-0.48 (pooled), and an executable exposure tracker that buys the predicted net deficit "
                               f"with strict fills reproduces the per-window PnL at {prim['pnl_corr_pool']} (GF {prim['pnl_corr_GF']['pearson']}, DS {prim['pnl_corr_DS']['pearson']}, "
                               f"XM {prim['pnl_corr_XM']['pearson']}); the three wallets' per-window PnLs are nearly independent (0.00-0.20).")
comp["exit"]["confidence"] = 0.9
comp["timing"]["description"] = ("Decision = submission of a pre-signed ladder order; a time-locked MINORITY (~9% beyond a placebo: 13.2% vs 4.7%) comes 100-150 ms after a sharp venue microprice move "
                                 "toward the outcome (strong ticks, large size, early, more often won); ~90% have no sharp clock in any recorded feed (61% without a six-series tick). Under Polymarket's "
                                 "150-ms taker delay the order ARRIVES ~150 ms before its match; the bot reads Polymarket's book ~30 ms old and Binance ~100+ ms old (near the engine). "
                                 "Selective: it reacts mostly at the onset of a flagged episode; no self-kept vol scale, snapshot gate, cross-market confirmation or crowd timing selects "
                                 "the onsets; the recorded Coinbase ticker adds a small replicated out-of-sample gain (+0.014 / +0.016 AUC; strong Binance ticks are taken more when "
                                 "Coinbase has not yet moved). Iteration 12: the take rate's window-level heterogeneity is a slow 1-2-minute OPERATOR-level regime (a wallet's take "
                                 "follows the other wallets' recent decisions; its own are refractory; the own-recent effect sits inside a redraw null at 2-minute FE), not a "
                                 "self-exciting kernel. Historically presence on block seconds 0.875 vs 0.821 (+0.054).")
for k in ("timing", "side", "price", "size", "exit", "selection"):
    comp[k]["tag"] = "VALIDATE-only"
s["strategy_statement"] = (
    "One operator runs a TypeScript clob-client bot on three (plus a fourth) wallets in every BTC 5-minute Up/Down window, and only there [VALIDATE-only]. It pre-signs BUY orders on both "
    "outcomes at every cent in bursts each window (three bursts at -89.5 / +42 / +173 s since 08-22; other two-burst schedules in early August) [VALIDATE-only]. It submits one about "
    "100-150 ms after a microprice tick of the Binance USD-M / OKX / Bybit BTC and ETH perps toward an outcome, at the ask it saw ~30 ms before arriving [VALIDATE-only]; it runs near "
    "Polymarket's engine [VALIDATE-only, location hypothesis]. Polymarket holds every marketable order 150 ms, so the bot races the crowd in that delay queue [VALIDATE-only]. It takes "
    "about one in three flagged episodes; which ones is not decoded: no recorded public input separates taken from skipped strong ticks beyond small gains (Coinbase freshness +0.015 "
    "AUC), and the take rate follows a slow 1-2-minute operator-level regime shared by the wallets [VALIDATE-only; open]. The side is the tick direction (83% per decision live, 77% "
    "at the block clock) [VALIDATE-only]. Lost races rest at the old ask for ~0.1-1 s and fill as maker about half the time [VALIDATE-only]. The size is small unless the operator's "
    "intended position is flat or long the outcome [VALIDATE-only, own state, tentative]. Inside a window the net exposure follows the current minute's move and is bought back "
    "against earlier moves; it is predictable from public data at r ~0.48, and an executable exposure tracker built on that prediction reproduces the cluster's per-window PnL at "
    f"r {prim['pnl_corr_pool']['pearson']} / {prim['pnl_corr_pool']['spearman']} under strict fills with >= 2 s latency (per wallet 0.06-0.43) [VALIDATE-only]. Positions are held to "
    "resolution; 87% of shares end in complete sets bought at 0.979 [VALIDATE-only]. Income = locked sets (~2.1 c per pair) and the 50% taker-fee rebate; the lean is a coin with "
    "respect to the outcome and carries the per-window PnL variance [VALIDATE-only]. Nothing is exam-verified.")
s["status"] = "continue"
tm = s["target_metrics"]
tm["pnl_corr_pearson"] = prim["pnl_corr_pool"]["pearson"]
tm["pnl_corr_spearman"] = prim["pnl_corr_pool"]["spearman"]
s["best"]["rule_id"] = (f"it12: presence / side / price rule unchanged since iteration 8 (code/final_rule.py); PnL rule = exposure tracker {prim_name}, convention (a)")
s["best"]["validate_metrics"].update({"pnl_corr_pearson": tm["pnl_corr_pearson"], "pnl_corr_spearman": tm["pnl_corr_spearman"],
                                      "pnl_corr_by_wallet_tracker": {k: prim[f"pnl_corr_{k}"] for k in ("GF", "XM", "DS")},
                                      "pnl_corr_pool_block_ci95_tracker": prim["pnl_corr_pool_pearson_block_ci95"], "pnl_corr_pool_halves_tracker": prim["pnl_corr_pool_halves"],
                                      "pnl_corr_frozen30_pearson_spearman": [0.1755, 0.1692], "tracker_return_before_rebates": prim["return_before_rebates"],
                                      "tracker_return_with_50pct_fee_rebate": prim["return_with_50pct_fee_rebate"]})
s["target_metrics_notes"]["iteration12"] = (f"pnl_corr_* now come from the iteration-12 exposure tracker ({prim_name}; pre-registered; strict fills on other traders' taker prints, latency "
                                            ">= 2 s, capture 1.0, cluster takers and cluster-maker transactions excluded): pooled Pearson / Spearman "
                                            f"{prim['pnl_corr_pool']['pearson']} / {prim['pnl_corr_pool']['spearman']} (2-h block CI {prim['pnl_corr_pool_pearson_block_ci95']}; halves "
                                            f"{prim['pnl_corr_pool_halves']}); per wallet GF {prim['pnl_corr_GF']}, DS {prim['pnl_corr_DS']}, XM {prim['pnl_corr_XM']} (condition 7 not met). "
                                            + (f"Co-occurrence check: the same tracker on a market-activity-only net-flow model reaches {(tg or {}).get('tracker_market_only')}; gain of the "
                                               f"reference feeds Pearson {(tg or {}).get('gain_pearson')} (paired 2-h block CI {(tg or {}).get('gain_pearson_ci95')}), Spearman {(tg or {}).get('gain_spearman')} "
                                               f"(CI {(tg or {}).get('gain_spearman_ci95_300draws')}). " if tg else "") +
                                            "The iteration-4 30-share replica (0.1755 / 0.1692) is kept as pnl_corr_*_frozen30. End-to-end evaluate on 36 VALIDATE windows reproduces the "
                                            "offline tracker exactly. Other keys unchanged.")
hy = s["hypotheses"]
nxt = max(int(h["id"][1:]) for h in hy) + 1
new = [
    ("exposure target identity (X110)", "per-window PnL vs net x outcome", (net or {}).get("by_wallet", {}).get("pool"), "PnL is the net lean (r 0.884 on VALIDATE)"),
    ("exposure tracker, it4b netflow target (X110)", "strict-fill deficit tracker, convention (a), pre-registered primary 1", {k: t_nf[k]["pnl_corr_pool"] for k in t_nf}, "0.43-0.44 for every execution variant"),
    ("exposure tracker, average target (X110)", "0.5 it4b netflow + 0.5 nf12b", {k: t_avg[k]["pnl_corr_pool"] for k in t_avg}, "primary (pre-registration 2)" if not ENS3_WON else "superseded by ens3"),
    ("window-net predictability (X110)", "BUILD-fit per-second net-flow models summed over the window", {"nf12": (n12 or {}).get("validate_window_net_corr"), "nf12b": w,
     "nf12c": (n12c or {}).get("validate_window_net_corr")}, "r 0.42-0.48; per-wallet models no better"),
    ("structural net path / fair value (X110 step 4)", "window-minute OLS of the net on minute moves, M1, M2, previous outcome, gap", {k: {m: v[m]["t"] for m in v} for k, v in (fv or {}).items() if isinstance(v, dict)},
     "buy with the current move, buy back against earlier moves; no other-strike FV"),
    ("Coinbase divergence gate (X100 step 1)", "Coinbase class at Binance onsets, fit A score C and reverse", {"fit_A_score_C": cbA, "fit_C_score_A": cbC}, "small replicated gain (+0.014 / +0.016)"),
    ("regime vs self-excitation (X109 step 1)", "segment-FE scan with a 200-draw redraw null", {"A": {k: rA.get(k) for k in ("L300", "L120", "L60", "L30")}, "C": {k: rC.get(k) for k in ("L300", "L120", "L60", "L30")}},
     "own-recent effect inside the null at 2-min FE; refractory at 60 s"),
    ("where the state lives (X106 step 1)", "per-wallet own vs other recent decisions, 120-s FE", r6, "operator-level state; wallets as refractory slots"),
]
if co:
    new.append(("fast-crowd co-take instrument (X101 steps 1-2)", "co-take table and the crowd odds ratio conditional on the recorded onset design", {k: co.get(k) for k in ("A", "C")}, "recorded inputs explain 14-21% of the shared selection"))
if lk:
    new.append(("locked vs unlocked decisions (X111 steps 1-2)", "net microprice move toward o in the kernel7 peak bin +-25 ms, placebo shifts -2 / -4 s", lk, "~9% locked beyond placebo; the rest unclocked"))
if ct:
    new.append(("competition-aware controller (X112)", "P(take) vs the operator's recent win share with the count fixed", {k: ct.get(k) for k in ("A", "C")}, "rejected (no 2x, inconsistent signs)"))
if tg:
    new.append(("PnL co-occurrence baseline (X110)", "the same exposure tracker on a market-activity-only net-flow model (nf12m)", tg, "reference feeds add +0.116 / +0.125 (CI excludes 0)"))
if bsl:
    new.append(("slow public state at the block clock (X109 step 5)", "block-second presence retrained with outcome-signed slow spot-path features", {k: bsl.get(k) for k in ("auc_full_frozen", "auc_full_plus_slow", "auc_pure_baseline", "slow_minus_frozen_block_bootstrap_2h", "halves")}, "measurement only; see NOTES"))
if t_e3:
    new.append(("exposure tracker, three-model target (X110)", "(it4b netflow + nf12b + nf12c) / 3, pre-registration 3", {k: t_e3[k]["pnl_corr_pool"] for k in t_e3},
                "primary (beat avg on both)" if ENS3_WON else "not adopted (did not beat avg on both)"))
for i, (fam, desc, vm, ver) in enumerate(new):
    hy.append({"id": f"H{nxt + i}", "family": fam, "description": desc, "validate_metrics": vm, "verdict": ver})
s["data_sources"] += ["Iteration 12: data-api taker tapes of the 2,016 VALIDATE and 2,016 BUILD windows rebuilt from the shared HTTP cache into the session scratchpad (tapes12.py; not kept)",
                      "Iteration 12: it12/nf12_val.parquet, nf12b_val.parquet, nf12c_val.parquet (VALIDATE predictions of the BUILD-fitted net-flow models), it12_win_net.parquet",
                      "Iteration 12: btc5m_venues2 Coinbase 'cbT' ticker at the 10-31 onsets (cbx12.py)"]
it = {"n": 12, "minutes": MIN, "best_validate_score": 0.9132, "block_seconds_presence": 0.8747, "block_seconds_stronger_baseline": 0.8211,
      "pnl_corr": prim["pnl_corr_pool"]["pearson"], "pnl_corr_spearman": prim["pnl_corr_pool"]["spearman"],
      "paradigm": "PIVOT: condition 5 as an exposure-path target (window net exposure and its per-second increments as the unit; an executable deficit-tracking replica instead of decision replays)",
      "families": ["exposure target identity PnL ~ net x outcome (X110)", "BUILD-fit per-second net-flow models with slow path features: nf12 / nf12b / nf12c (X110)",
                   "executable strict-fill exposure tracker, pre-registered, two conventions and execution variants (X110)", "structural net path / fair-value variants per window-minute (X110 step 4)",
                   "per-wallet PnL independence and per-wallet net models", "Coinbase divergence gate at onsets (X100 step 1)", "regime vs self-excitation with a 200-draw redraw null (X109 step 1)",
                   "operator-level vs per-wallet state (X106 step 1)", "end-to-end evaluate of the new PnL rule on a VALIDATE slice", "market-only co-occurrence tracker and paired gain (X110)", "slow public state at the block clock (X109 step 5)", "race-success controller (X112)", "locked vs unlocked decisions (X111 steps 1-2)", "fast-crowd co-take instrument (X101 steps 1-2)"]}
s["iterations"].append(it)
json.dump(s, open(P, "w", encoding="utf-8"), indent=1)
print("primary", prim_name, prim["pnl_corr_pool"])
print("open", len(open_ids), open_ids)
