"""Iteration 12: bring state.json up to date (catalog X114-X127 and status changes, target_metrics, best, components,
strategy_statement, hypotheses, data_sources, iterations). Keeps a copy of the previous file in the cache.
    python code12/update_state12.py <minutes>
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE.parent / "state.json"
C = HERE.parents[3] / ".cache/re/directional-maker"
R = HERE.parent / "results"


def J(name):
    return json.loads((R / name).read_text())


def main(minutes: float):
    shutil.copy(ST, C / "it12" / "state_before_it12.json")
    s = json.loads(ST.read_text())
    cat = s["catalog"]
    rm = J("iter12_replay_machine.json")
    ts = J("iter12_typed_side.json")
    cv = J("iter12_composite_v2.json")
    ms = J("iter12_maker_shares.json")
    hs = J("iter12_hist_state.json")
    kg = J("iter12_live_k_grid.json")
    qk = J("iter12_quote_k_1793455600_1793464202.json")
    lc = J("iter12_longshot_capture.json")
    xm = J("iter12_xmarket_entry.json")
    ow = J("iter12_owners.json")
    v = cv["validate"]
    new = {
        "X114": ("tried", "source: panel iter11 information I11-1 (whole-history state of the side). Iteration 12 (code12/fetch_history.py, code12/hist_state.py, results/iter12_hist_state.json): whole activity from the first trade (almach 05-22, bosona 06-02, mo-money 02-04); 959,805 BTC 5m BUY fills in 637 6-h blocks to 10-30. Out-of-sample R^2 of the block favourite share on 10-01..30 (fit before 09-30): constant %.2f, weekday %.2f, log RV %.2f, weekday + RV %.2f, change points carried forward %.2f; in-sample R^2 <= 0.02. Weekday profile reverses across the history (May-Jul Monday 0.51 falling to Saturday 0.36; October Monday 0.37 rising to Sunday 0.53); corr(F, log RV) +0.12 / +0.14 / -0.24 by period; one change point (06-05) explaining 12%% of the block variance; wallets' block F correlate 0.69-0.78. Readings (a) Monday state, (b) volatility, (d) versions rejected; (c) risk budget not tested here. The k MLE with the fill-price proxy was not computed (the favourite share is the state variable, Spearman -0.93 with k)." % (
            hs["models"]["const"]["oos_r2"], hs["models"]["a"]["oos_r2"], hs["models"]["b"]["oos_r2"], hs["models"]["ab"]["oos_r2"], hs["d_pen4.0_oos_r2"])),
        "X115": ("tried", "source: panel iter11 information I11-2 (the competitor at the touch; same test as X126). Iteration 12 (code12/fetch_makers.py, maker_compact.py, maker_shares.py; results/iter12_maker_shares.json): maker-row tapes of 1,056 BTC 5m windows (02/08/14/20 UTC, 10-09..30), 2.8M maker BUY rows, 7,439 makers; the cluster holds 1.97%% of maker BUY volume. The market's maker favourite share is flat (variance of its log-odds 0.017 vs 1.53 for the cluster's); the cluster's favourite-side share stayed 0.022 -> 0.022 (BUILD+STUDY -> VALIDATE) while its underdog-side share rose 0.015 -> 0.026; top-10 competitors' favourite-side share 0.185 -> 0.181; no top-30 competitor moves against the cluster (Spearman over blocks -0.34..+0.28, bar <= -0.5); no top-15 maker shares its daily cycle (-0.47..+0.33). Competition rejected: the change is the cluster's own quote (more underdog-side bids). Favourite-side half-spreads (ii) and each maker's best k (iii) not computed."),
        "X116": ("open", "source: panel iter11 information I11-3 (k on the quote vs on fills, across weekdays; pmxt). Iteration 12 step 1 on the only recorded development block (code12/quote_k.py, results/iter12_quote_k_1793455600_1793464202.json): ladder-center k on 10-31 14:06-16:30 (Saturday): 5m median %.2f (window bootstrap %s, IQR %s), 15m %.2f (%s); fill-level best k on the same block 1.4 (bootstrap [0.7, 1.68], iter12_live_k_grid): quote k = fill k within the interval. Open: the Sunday 11-01 06-12 and Monday 11-02 development blocks (pre-registered: Monday quote k >= Sunday + 0.5) and the pmxt July Mondays." % (
            qk["5m"]["k_median"], qk["5m"]["k_median_window_boot95"], qk["5m"]["k_iqr"], qk["15m"]["k_median"], qk["15m"]["k_median_window_boot95"])),
        "X117": ("open", "source: panel iter11 information I11-4 (short-dated options IV and the engine's own Chainlink feed as the sigma source). Iteration 12: falsifier for (b) run (results/iter12_live_k_grid.json): on the live 10-31 14:06-16:30 block (noise regime; 1,668 match-clock fills) the per-fill posture peaks at k = 1.4 (0.809), k >= 2.4 <= 0.60, window-bootstrap argmax [0.7, 1.68], never >= 2.5: (b) Chainlink-stream RV is out. Open: (a) Deribit front-expiry ATM IV per hour (history.deribit.com option trades, verified by the panel) regressed against the per-block engine sigma."),
        "X118": ("open", "source: panel iter11 information I11-5 (the operator's other accounts and the weekly treasury path). Iteration 12 (code12/owners.py, results/iter12_owners.json): owners recovered: mo-money Safe owner 0xd1f9bc03... (threshold 1, Polygon nonce 445); almach and bosona are ERC-1967 proxies (implementation 0x58ca52eb..., factory 0x00000000000fb5c9...) with owner EOAs 0xb3f8b214... (nonce 1,456) and 0x4acd0e52... (nonce 2) in their immutable args. Hyperliquid: almach's and bosona's owners unknown there; mo-money's owner has no fills in the 120 days before T0 (last ledger event 2026-06-13). Open: decode the Monday 01:00 sweep USDC transfers to their destinations and the Safe/proxy creations of each owner."),
        "X119": ("open", "source: panel iter11 mechanics P1 (read the engine's k(t) off its own ladder through the Monday reset 11-02 00-06 and over July Mondays in pmxt). Needs the 11-02 00-06 and 12-18 development blocks (dx_clob runs to 11-03 00:00). Step-1 code exists (code12/quote_k.py; Saturday block 5m 1.14, 15m 1.37). The per-day best k from July fills (pmxt + Binance 1-s) not run."),
        "X120": ("tried", "source: panel iter11 mechanics P2 (decided-window longshot bids as their own order type; side per order hash and per window state). Iteration 12 (code12/typed_side.py, results/iter12_typed_side.json, iter12_longshot_capture.json): deep (limit <= 0.10) share of fills by day 2.5%% (10-24) -> 8.6%% (10-26) -> 15-23%% (10-27..30); capture of the >= 0.90 taker-BUY opportunity 0.2-0.4%% (10-23..25) -> 1.6%% (Mon 10-26) -> 2.3-5.5%% (10-27..30) at a flat opportunity: a >10x step of the deep-bid module on Monday 10-26. Side per type and per order: deep posture 0.83 / 0.88, cheaper 1.00 (by price); per-order numbers reported beside per-fill ones. Deep-limit price law (fixed grid vs last print) and the live lifetimes of deep rungs not run."),
        "X121": ("open", "source: panel iter11 mechanics P3 (complement-aware level censoring from all-match calldata). The quote-vs-competition question it targets is answered at the aggregate level by X115/X126 (competitors flat; the cluster's own underdog-side share rose). Open: the per-match level labels (present / absent at a cleared level) and the lot-wide F* inverse fit."),
        "X122": ("tried", "source: panel iter11 mechanics P4 (the per-fill side ceiling from the ladder geometry). Iteration 12 (code12/typed_side.py): near (within a tick of the R7 price) 0.59 / 0.48 of fills (STUDY / VALIDATE), far 0.12 / 0.07, above 0.10 / 0.08, deep 0.06 / 0.19, pairing 0.13 / 0.18. Posture on near fills 0.571 / 0.648 (not >= 0.80): the per-fill gap is not only the far side; on near rungs the cluster's held outcome is 0.753 / 0.741 (the after-entry rungs follow the position, not the posture)."),
        "X123": ("open", "source: panel iter11 mechanics P5 (one configuration vector, one change log). Partial: whole-history block favourite share has one change point (06-05; X114); the deep-bid capture steps on Monday 10-26 (X120). Open: minute-resolution change points of size class, salt slope, deep share and favourite share with the cross-parameter permutation test."),
        "X124": ("tried", "source: panel iter11 assumptions P1 (replay the whole decoded state machine, exit included). Iteration 12 (code12/replay_machine.py, replay_machine_score.py; results/iter12_replay_machine.json, iter12_replay_machine_touch.json): pairing leg (bid |U - D| on the under-held outcome at last print - 0.01) under strict fills: VALIDATE posture + pairing -0.016 / -0.002, held + pairing 0.027 / 0.028, oracle side + pairing 0.246 / 0.299 (without pairing 0.473 / 0.527); the replay's locked PnL -$106k to -$236k (at-touch fills -$87k to -$236k) vs the cluster's +$38.1k. Pre-registered STUDY choice (held, no pairing) VALIDATE 0.111 / 0.179, gain over R7 [-0.148, +0.008]: not adopted. The outcome ceiling is lower with the decoded exit: the cluster's locked pairs need fills that do not trade through."),
        "X125": ("tried", "source: panel iter11 assumptions P2 (the posture is a band). Iteration 12 (code12/typed_side.py): STUDY choice h 0.02 with the 30-s taker-flow complement inside; VALIDATE 0.6823 vs posture 0.6826 (gain [-0.009, +0.010]): not adopted. The posture outside the band is 0.51-0.75 by day and does not rise with h (VALIDATE 0.69-0.72 for h 0.01-0.10, STUDY 0.58 -> 0.51): E4's signature (>= 0.85 every day) fails historically. Quote-level band fit on the live block not run (the side after entry is the position, X122)."),
        "X126": ("tried", "source: panel iter11 assumptions P3 (maker-share accounting). See X115: pre-registered sample (02/08/14/20 UTC windows, 10-09..30, 1,056 windows); the cluster's favourite-side maker share flat (0.022), underdog-side share up (0.015 -> 0.026), competitors flat, no inverse co-movement (bar <= -0.5 not met by any of the top 30): own quote, not competition. The price race against the best competing maker per second was not run."),
        "X127": ("tried", "source: panel iter11 assumptions P4 (step or drift). Iteration 12 (code12/hist_state.py): on the whole history (637 6-h blocks) the optimal-partition piecewise-constant mean explains 12%% of the block variance (one break, 06-05), far from the 70%% of a step process; carried-forward levels predict October worse than a constant (OOS R^2 -1.22). The tilt drifts; per-wallet 15-30-min residualised change points not run (block-level wallets correlate 0.69-0.78)."),
    }
    for k, (stt, ev) in new.items():
        cat[k] = {"status": stt, "evidence": ev}
    upd = {
        "X24": ("tried", " | iteration 12: done through X115/X126: the full maker-row tape of 1,056 windows; competitors' favourite-side shares are flat and do not move against the cluster's."),
        "X111": ("tried", " | iteration 12: the drift is the cluster's own quote: its underdog-side maker share rose 0.015 -> 0.026 at a flat favourite-side share and flat competitors (X126); the deep-bid module stepped >10x on Monday 10-26 at a flat opportunity (X120); after entry its rungs follow the cluster's held outcome on both halves (0.74-0.77), so the residual drift is in the entry decision (posture 0.66-0.70)."),
        "X113": ("open", " | iteration 12: not run (see X123)."),
    }
    for k, (stt, add) in upd.items():
        if k in cat:
            cat[k]["status"] = stt
            cat[k]["evidence"] = cat[k].get("evidence", "") + add
    tm = s["target_metrics"]
    tm["side_accuracy"] = v["fill"]
    tm["side_baseline"] = 0.6785
    tm["_notes"] = tm.get("_notes", "") + (" Iteration 12 (R8 = R7 + the window state-machine side, OWN STATE, exploratory: designed after the per-type VALIDATE aggregates were seen): side_accuracy = per BTC 5m maker fill on VALIDATE "
                                           "%.4f (2-h block bootstrap %s; per order %.4f; halves %s; per wallet %s): decided window -> cheaper token, no cluster position -> Chainlink posture, after entry -> the cluster's held outcome "
                                           "for schedule-size orders and the under-held outcome for non-schedule (pairing) orders; side_baseline = the stronger market-only baseline (cheaper token 0.6785); own-inventory-only baseline (cluster held outcome) %.4f; "
                                           "the same rule without own state 0.6925. Before: 0.672 (bin-level presence-score side). BTC 15m not included in this side number." % (
                                               v["fill"], v["acc_ci95"], v["order"], v["halves"], v["per_wallet"], cv["own_inventory_baselines_cluster"]["validate"]["held_only_cluster"]))
    s["best"]["rule_id"] = "R8 = R7 + the window state-machine side (own state; evaluate() side_state_machine)"
    s["best"]["validate_metrics"]["historical_union"] = dict(tm)
    s["best"]["validate_metrics"]["side_state_machine_it12"] = {"validate": v, "study": cv["study"]}
    comp = s["components"]
    comp["side"] = {"confidence": 0.7, "tag": "VALIDATE-only (exploratory; own state for the after-entry branches)",
                    "description": "a window state machine shared by the three wallets: (i) decided window (|Up mid - 0.5| > 0.4) -> the cheap loser (deep-bid module, stepped >10x on Mon 10-26); (ii) entry (no cluster position) -> the Chainlink posture (0.66 STUDY / 0.70 VALIDATE per fill); (iii) after entry the schedule rungs (500/250/62/100) buy the outcome the CLUSTER holds more of (0.79 / 0.77; 500s and 250s 0.88-0.89 on STUDY) and the non-schedule pairing bids the under-held outcome (0.94 / 0.91). Per fill 0.753 STUDY / 0.790 VALIDATE ([0.766, 0.811]), per order 0.690 / 0.725; without own state 0.569 / 0.693; cheaper 0.484 / 0.679; wallet-level inventory 0.703 / 0.766 (the state is the cluster's). Live 10-31: the 500 ladder follows the Chainlink edge 0.79-0.85 per fill. The weekly favourite-share 'cycle' is not a stable state (whole history: weekday, RV and step models fail out of sample) and not competition (maker shares): it is the entry decisions plus the deep-bid module."}
    comp["exit"] = {"confidence": 0.65, "tag": "VALIDATE-only",
                    "description": "holds to resolution; after entry bids its own imbalance on the under-held outcome (non-schedule sizes), priced at the market, plus small complement taker buys; merges ~65 s before the end. Locked pairs made +$38.1k on VALIDATE (residual -$14.4k). A strict-fill replay of the same pairing leg loses -$106k to -$236k (at-touch -$87k..-$236k) and lowers the oracle-side outcome ceiling from 0.47 / 0.53 to 0.25 / 0.30: the cluster's pairs need queue-priority fills that do not trade through."}
    comp["selection"]["description"] = comp["selection"]["description"].rstrip(".") + ". Iteration 12: unchanged."
    s["strategy_statement"] = (
        "[engine: VALIDATE-only] One engine family (timestamp-0 orders, per-wallet salt counters reset by the daily ~01:00 UTC restart) runs three accounts with three owner keys (mo-money: Safe of 0xd1f9bc03...; almach / bosona: ERC-1967 proxies of 0xb3f8b214... / 0x4acd0e52...) that share one position state per window. "
        "[selection: hypothesis] It quotes nearly every crypto Up/Down window of the modules it runs; BTC 5m/15m are switched off for hours, mostly Fri-Sun US-Eastern evenings. "
        "[timing: VALIDATE-only] It re-prices on each Chainlink report within ~0-150 ms of the RTDS relay and after Binance moves; its filled orders are fresh posts at the touch. "
        "[side: VALIDATE-only, exploratory, own state after entry] A window state machine: the entry buys the outcome whose Chainlink edge over the Polymarket mid is positive (digital, 1.4 x 300-s vol; the ladder center implies k 1.1-1.4 live); after entry the schedule rungs keep buying the outcome the cluster already holds and imbalance-sized pairing bids buy the other one; in decided windows a deep-bid module buys the cheap loser (switched up >10x on Monday 10-26). Per fill 0.79 on VALIDATE (0.69 without own state, cheaper-token baseline 0.68). The fill-level favourite share drifts with these entry and deep-bid decisions; it is not a weekday, volatility or competitor effect. "
        "[price: exam-verified (block clock) / VALIDATE-only (in-block and match clock)] Fill price = the last clean trade before the fill minus a tick: 0.80 within a tick on the in-block execution order, 0.83-0.86 on the live match clock. "
        "[size: VALIDATE-only] 500 x 2^k schedule rungs in the US session, 62/250 outside, plus imbalance-sized pairing bids. "
        "[exit: VALIDATE-only] Holds to resolution, completes pairs with maker pairing bids, merges ~65 s before the end. "
        "[economics: VALIDATE-only] It earns as a fast at-the-touch maker with a Chainlink-skewed entry: its locked pairs (+$38k on VALIDATE) and its directional residual both depend on fills of quotes refreshed within ~0.1-1 s; a strict-fill replay of the decoded machine loses 11-16% and tracks its window PnL at <= 0.21 / 0.22 (oracle side 0.47 / 0.53 without the pairing leg, 0.25 / 0.30 with it).")
    s["hypotheses"] += [
        {"id": "PR12-A", "family": "X124/D3", "description": "full-machine strict-fill replay with the pairing leg", "validate_metrics": {k: rm["configs"][k]["validate"]["pnl"] for k in rm["configs"]}, "verdict": "rejected (pairing lowers every correlation; locked PnL -$106k..-$236k)"},
        {"id": "PR12-B", "family": "X125", "description": "band: posture outside |e| > h, taker-flow complement inside", "validate_metrics": {"chosen": ts["band"]["chosen_on_study"], "validate": ts["band"]["validate_chosen"], "posture": ts["band"]["validate_posture"], "gain_ci": ts["band"]["validate_gain_ci95"]}, "verdict": "rejected"},
        {"id": "PR12-C", "family": "X120/X122", "description": "typed orders (near/far/above/deep/pairing) side accuracies", "validate_metrics": {"type_share": ts["validate"]["type_share_fills"], "near_posture": ts["validate"]["near"]["posture_cl"], "near_held": ts["validate"]["near"]["own_held"]}, "verdict": "descriptive: near rungs follow the held outcome"},
        {"id": "PR12-F/R8-side", "family": "D2 state machine", "description": "window state-machine side (decided cheaper / entry posture / after-entry held or under-held by order size, cluster inventory)", "validate_metrics": v, "verdict": "adopted as R8's side (own state, exploratory); pre-registered H12-SIDE-SM for the next development blocks"},
        {"id": "PR12-D", "family": "X114/X127", "description": "whole-history favourite share: weekday / RV / steps", "validate_metrics": {"oos_r2": {k: m["oos_r2"] for k, m in hs["models"].items()}, "cp_oos_r2": hs["d_pen4.0_oos_r2"], "cp_var_share": hs["cp_all_share_of_var_explained"]}, "verdict": "rejected (no model predicts October)"},
        {"id": "PR12-E", "family": "X126/X115", "description": "maker-share accounting (competition vs own quote)", "validate_metrics": ms["halves"], "verdict": "competition rejected; own quote (underdog-side share up)"},
        {"id": "E9", "family": "cross-market own state", "description": "5m entry follows the cluster's 15m position / previous 5m net", "validate_metrics": xm["validate"], "verdict": "rejected (15m position adds nothing beyond the posture; previous window 0.50)"},
        {"id": "X117b", "family": "X117", "description": "Chainlink-stream RV as sigma: live best k >= 2.5?", "validate_metrics": {"best_k": kg["best_k"], "boot": kg["boot_argmax_quantiles"]}, "verdict": "rejected (best k 1.4)"},
    ]
    s["data_sources"] += [
        "iteration 12: data-api /activity whole history of the three wallets from the first trade (almach 2026-05-22, bosona 06-02, mo-money 02-04) to 10-08, reduced to crypto Up/Down rows (it12/hist_btc.parquet)",
        "iteration 12: data-api /trades with taker_only=False (maker rows with every maker's wallet) for 1,056 BTC 5m windows (02/08/14/20 UTC, 10-09..30), compacted to it12/maker_rows.parquet",
        "iteration 12: Polygon eth_call / eth_getCode / eth_getStorageAt on the three proxies (Safe getOwners; ERC-1967 immutable args) and the public Hyperliquid info API (userRole, userFillsByTime, userNonFundingLedgerUpdates, every window ending before T0)",
        "iteration 12: Binance spot BTCUSDT 1-m kline daily archive (checksum verified) for per-block realised vol, 05-22..10-30",
    ]
    s["iterations"].append({"n": 12, "minutes": minutes, "best_validate_score": 0.716, "validate_definition": "2026-10-27..30 (lot second half, aggregate)",
                            "paradigm": "typed decisions and the fill as a joint outcome with competitors: the window state machine for the side (entry posture, held-outcome adds, imbalance pairing, deep bids), the full maker-row tape (competitor shares) and the whole activity history as new data, and the full-machine strict replay for the outcome",
                            "families": ["X124 full-machine replay with the pairing leg (strict and at-touch)", "X122/X120 typed orders (near/far/above/deep/pairing) and longshot capture", "X125 band rule", "R8 side state machine (cluster inventory, order size) + evaluate() side_state_machine smoke test", "X126/X115 maker-share accounting from maker-row tapes", "X114/X127 whole-history favourite share (weekday, RV, change points)", "X117 falsifier (b) live k grid", "X116/X119 step 1 quote-level k on the live block", "X118 owners (Safe, ERC-1967) and Hyperliquid", "E9 cross-market entry (15m position, previous window)"],
                            "ended_utc": "2026-11-01 03:30"})
    s["status"] = "continue"
    s["wall_reason"] = None
    ST.write_text(json.dumps(s, indent=1))
    opn = sorted([k for k, x in cat.items() if x.get("status") == "open"], key=lambda z: (z[0], int(z[1:]) if z[1:].isdigit() else 0))
    print("catalog", len(cat), "open", len(opn), opn)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 100.0)
