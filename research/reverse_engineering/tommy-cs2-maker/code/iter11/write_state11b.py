"""Iteration 11 state.json update, part two (run after write_state11.py): survival curve, class knockout, components,
strategy statement, live lab, data sources, hypotheses, iteration entry, next steps."""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
WS = ROOT / "research/reverse_engineering/tommy-cs2-maker"
RES = WS / "results"
MINUTES = int(__import__("os").environ.get("IT11_MINUTES", "0"))


def rj(n):
    p = RES / n
    return json.load(open(p, encoding="utf-8")) if p.exists() else None


S = json.load(open(WS / "state.json", encoding="utf-8"))
cat = S["catalog"]
rs, ck = rj("remainder_survival.json"), rj("class_knockout.json")
if rs:
    cv = rs["curve"]
    txt = (f" | Step 2 (remainder_survival.json, BUILD-live raw book, {rs['takes']} in-play FAK BUYs, fill median {rs['F_median']}): depth at <= its limit vs signing "
           f"{cv['-900']['depth_rel_to_signing_median']} at +140 ms, {cv['-500']['depth_rel_to_signing_median']} at +540 ms, {cv['-200']['depth_rel_to_signing_median']} at +840 ms, {cv['-50']['depth_rel_to_signing_median']} at +990 ms (flat over the last ~200 ms before its match; it covers its fill: mean {cv['-50']['refill_mean']}); "
           f"after its match the residual at <= its limit is a median 0 (mean {cv['0']['refill_mean']} of its fill at 0 ms, {cv['100']['refill_mean']} at +100 ms, {cv['300']['refill_mean']} at +300 ms; >= 50% kept in {cv['300']['share_refill_ge_50pct']} of takes at +300 ms). "
           "On the observed book its own take empties the stale remainder, so an examinable public-lag copy lives in the T_lo world; the T_hi world needs the wallet absent. Signature if true (>= 50% of its refill at +300 ms) fails on the observed book. Step 3 (executable replica) not run: bounded above by T_lo.")
    if "Step 2 (remainder_survival.json" not in str(cat["X149"].get("evidence", "")):
        cat["X149"]["evidence"] = str(cat["X149"].get("evidence", "")) + txt
    cat["X149"]["status"] = "tried"
if ck:
    v, b = ck["VALIDATE"], ck["BUILD"]
    parts = []
    for ko in ("none", "quiet", "follow", "msg", "repair", "endgame", "quiet+follow", "all"):
        parts.append(f"{ko}: {v[ko]['maker_plus_real_taker'][0]}/{v[ko]['maker_plus_real_taker'][1]} (Spearman loss {v[ko]['spearman_loss']} {v[ko]['spearman_loss_ci95']}, pair cost {v[ko]['pair_cost_median']}; BUILD {b[ko]['maker_plus_real_taker'][0]}/{b[ko]['maker_plus_real_taker'][1]})")
    cat["X151"]["status"] = "tried"
    cat["X151"]["evidence"] = ("class_knockout.json (code/iter11/class_knockout.py; validated engine, its own maker orders with one ledger class re-priced at the last public print, timing and size kept, plus its real taker leg). VALIDATE Pearson/Spearman: " + "; ".join(parts))
cs, csn, sc2, ds = rj("crossbook_sync.json"), rj("crossbook_sync_near.json"), rj("slot_ceiling_v2.json"), rj("disruption_scan.json")
if cs and csn:
    a, b = cs["pooled"], csn["pooled"]
    add = (f" | Step 2 (live, uncensored; crossbook_sync.json / crossbook_sync_near.json, BUILD-live, the two events with >= 2 recorded books): of {a['own_adds']} validated own adds with no trade on any book of the event in the prior 300 ms, "
           f"{a['sync_rate']} have a non-own level change on a DIFFERENT book of the event within +-40 ms, vs {a['null_rate']} at +-1-5 s shifts and {b['null_rate']} at +-0.2-1 s shifts (excess {a['excess_share']} / {b['excess_share']}); "
           f"quiet adds (no trade in 5 s) {a['quiet_sync_rate']} vs {a['quiet_null_rate']} / {b['quiet_null_rate']}. Invisible messages exist (other makers re-price another market of the event at the same moment beyond near-time clustering, about 10% of its quiet re-pricings), but their increments are not its own (steps 3-4): one event stream, priced by each receiver's own model.")
    cst, sps = rj("crossbook_sync_strict.json"), rj("sameprice_sync_strict.json")
    if cst and sps:
        add += (f" Strict check (non-own adds of any size the wallet uses in that book dropped, in case they are its own unlabelled cross-market re-pricing): cross-book {cst['pooled']['sync_rate']} vs {cst['pooled']['null_rate']} at +-0.2-1 s (unchanged). "
                f"Same book: a synchronous non-own add within +-40 ms for {sps['real']['sync']} of its adds vs {sps['null_near_shift']['sync']} shifted; given one, it lies within 1c of its price {sps['real']['sync_1c_given_sync']} vs {sps['null_near_shift']['sync_1c_given_sync']} (median gap {sps['real']['diff_c_median_given_sync']}c vs {sps['null_near_shift']['diff_c_median_given_sync']}c): other makers land near, not at, its level (partial agreement).")
    if "crossbook_sync.json" not in str(cat["X154"].get("evidence", "")):
        cat["X154"]["evidence"] = str(cat["X154"].get("evidence", "")) + add
    cat["X154"]["status"] = "tried"
if sc2:
    ad = sc2["add"]["V_after"]
    add2 = f" | Version 2 with own-event state (slot and age of its last own add and own decrease; slot_ceiling_v2.json): adds LightGBM {ad['within_tick_lgbm_loeo']} (V before {sc2['add']['own_top']['within_tick_lgbm_loeo']}), fills {sc2['fill']['V_after']['within_tick_lgbm_loeo']}: the ceiling does not move with richer own state."
    if "Version 2 with own-event state" not in str(cat["X150"].get("evidence", "")):
        cat["X150"]["evidence"] = str(cat["X150"].get("evidence", "")) + add2
if ds:
    cat["X157"]["status"] = "tried"
    add3 = (f" | Iteration 11 (disruption_scan.json, CS2 proxy over {ds['markets']} windowed taker tapes of 16-22 Oct): {ds['zero_print_busy_minutes']} of {ds['busy_minutes']} busy minutes (>= 8 markets in play by schedule) without a print, {len(ds['droughts_ge_3min'])} droughts >= 3 min; 8 outside its sessions (evenings, schedule proxy over-counts finished matches); the only in-session one (10-17 10:30, 4 min) did not interrupt it (92 / 9 / 87 maker orders and 11 / 1 / 4 merges in the 30 min before / during / after). "
            "No development analogue shows an intraday session break. Pre-registered (NOTES iteration 11, before any exam): evaluate() and the universe unchanged for h1; the examiner reports 10-29 selection with and without the events starting after the publicly announced pause start (descriptive only). The pause time itself is in h1 (sealed) and was not looked up in data.")
    if "disruption_scan.json" not in str(cat["X157"].get("evidence", "")):
        cat["X157"]["evidence"] = str(cat["X157"].get("evidence", "")) + add3
cat["X146"]["status"] = "ruled_out"
cat["X146"]["evidence"] = ("Ruled out by measurement under the brief's executable conditions (strict fills, latency >= 2 s, match_slack 2): the protection must act before the delayed informed takes execute at about +1.04 s after the message; on the BUILD-live book the depth at the wallet's take limit falls to 0.34 of its signing value at +140 ms and 0.145 by +840 ms (remainder_survival.json), i.e. the adverse flow completes within the 1-s delay. A maker with >= 2-s latency cannot pull in time, so the echo-protected public maker is not an admissible executable rule; and X155 shows that even an oracle copy of every wallet decision at 2 s fails Spearman on the observed record (0.43 / 0.40 VALIDATE). "
                           "(Calibration of the echo on BUILD-live and a sub-second replay remain possible as a descriptive study, not as an examinable rule.)")
S["catalog"] = cat

comp = S["components"]
comp["price"]["description"] = (
    "Maker: whole-cent BUY ladders near the touch; slots below its own top 0 / -1 / -2 / -3 / -4c = 44 / 19 / 13 / 10 / 13% of adds (BUILD-live). "
    "Examinable historical anchor: the last print 0.305-0.322 within one tick (VALIDATE); no point-in-time own-state anchor beats it (iteration 11, X152: its own level revealed on chain at signing 0.280, union with the last print 0.418; the earlier 0.500 / 0.599 / 0.716 used the predecessor's later fill and are fill-selected footnotes). "
    "Live (BUILD-live): touch 0.42 on fills / 0.45 on adds; a freshness-filtered touch is lower at every window (X153); SX Bet's in-play quotes are sparse and track Polymarket, not the wallet (X145); synchronous fast-maker re-pricings do not share its increment (X154, corr 0.28 = shifted control). "
    "Its level is an informed private value (adds predict the others' mid, X135) and one valuation per event (series coherence). Even with that value V known, a per-order rule caps at about 0.71-0.75 within one tick (X150 oracle ceiling): the per-order price item is structurally capped for this ladder. All its orders lie in [0.05, 0.95]. Pre-game it bids 1-2c under Polymarket's own print (X144 step 2).")
comp["exit"]["description"] = (
    "Never sells. Pulls the complement at its takes and re-posts ~1.03 s later; re-prices bids away from private adverse events between takes; merges complete pairs in one 300-s loop for CS2 and Dota (300.22 s + 7.28 s per merge on 16-22 Oct; on 10-31 the per-merge increment drifted, X156) and holds the residual. Pair cost 0.978 (CS2), ~0.98 (Dota). Hard client band [0.05, 0.95]; bids the eventual loser down to the band with no early stop. "
    "Outcome (iteration 11, X155 / X149 / X151): its own maker orders delayed up to 2 s with the real taker leg keep 0.70 / 0.62 (VALIDATE); the take is binding: on the observed book its own FAK empties the stale remainder (median residual 0 after its match), so a public-lag copy reaches at most 0.50 / 0.41.")
comp["size"]["description"] = ("Maker: 100 shares in CS2 (88-92% of orders on 16-22 Oct) or an event-wide ramp that starts near 54 and steps up to 100 (36% of events on 16-22 Oct; 3 of 4 CS2 events on 10-31, so 57% 100-share orders there), exactly 10 shares in Dota 2; size rule accuracy 0.894 (VALIDATE, v4). "
    "Taker: odd sizes ~0.3x of the pre-event depth; on 10-31 a median of 129 shares and no 1000 / 2000 caps (X156): re-fit the taker size on BUILD-live before a future-block exam.")
comp["size"]["confidence"] = 0.58
S["components"] = comp

base = S["strategy_statement"].split(" [VALIDATE-only, iteration 11]")[0]
S["strategy_statement"] = (base +
    " [VALIDATE-only, iteration 11] No point-in-time own-state price anchor beats the last print (0.280 vs 0.305), SX Bet's on-chain in-play fills are too sparse and Polymarket-following to carry its value, a fresh public touch scores below the touch, and synchronous fast-maker re-pricings do not share its increment: the value is its own. [hypothesis, BUILD-live oracle] Even with its value known, slot choice caps a per-order price rule at about 0.71-0.75 within one tick. [VALIDATE-only, iteration 11] The outcome item is bound by the take, not the maker's timing: its maker orders delayed 2 s keep 0.70 / 0.62 with its real taker leg, while on the observed book its own take empties the stale remainder, so a public-lag copy reaches at most 0.50 / 0.41. [hypothesis, 10-31 development blocks] The forward build changed its taker sizes and merge timing (and more CS2 events use its known maker size ramp) but not its price band.")

if not any("tommy_tp_odds2" in x.get("what", "") for x in S["live_lab"]):
    for x in S["live_lab"]:
        if "tommy_tp_odds (code/iter10" in x.get("what", ""):
            x["end"] = 1793511010
            x["what"] = x["what"] + "; STOPPED 11-01 05:30 UTC (iteration 11, before any development block), replaced by tommy_tp_odds2"
    S["live_lab"].append({"what": "own recorder v2, feed tommy_tp_odds2 (code/iter11/tp_odds_recorder_v2.py; X144 / X148): bo3.gg live index every 3 s (B, as v1), upcoming index with start < now + 90 min every 30 s (U, the pre-game Thunderpick line), per-match object of matched development-unit in-play matches round-robin every 2 s (P, cadence check), bo3 coverage fields in every record; unit-rule filing via code/iter5/unit_writer.py; detached (launcher 24512, worker 27892), hard stop 2026-11-03 00:00 UTC, 150 MB cap, < 0.9 request/s", "start": 1793510977, "end": 1793664000})
    S["data_sources"].append("SX Rollup (SX Bet) on chain, key-free: Blockscout explorer API explorerl2.sx.technology (Etherscan-style getLogs of exchange proxy 0x890482680C3a0116aBB003B17e7D694D13a6c1eB, topic0 0x9267299c fill summaries, blocks 10,543,166-10,686,804 = 10-16..H) + /api/v2/transactions/<hash> raw input decoded for the 80 esports fill txs + api.sx.bet/markets/find (key-free) -> .cache/re/tommy-cs2-maker/sx/")
    S["data_sources"].append("bo3.gg upcoming index and per-match object (structure probe; recorded from 11-01 05:29 UTC by tommy_tp_odds2)")
    S["hypotheses"].extend([
        {"id": "H122", "family": "price", "description": "A second venue (SX Bet, on chain) carries the wallet's in-play value or leads Polymarket.", "validate_metrics": {"cs2_markets_week": 11, "cs2_fill_txs": 63, "wallet_events_with_sx": 6, "sx_minus_pm_last_sd_c": 3.56, "sx_minus_wallet_bid_sd_c": 7.05}, "verdict": "rejected (sparse, Polymarket-following)"},
        {"id": "H123", "family": "price", "description": "A freshness-filtered touch (levels re-priced by non-own makers in the last D s) anchors its quotes better than the touch.", "validate_metrics": {"fills_second_half": [0.391, 0.402], "adds_second_half": [0.390, 0.411]}, "verdict": "rejected (lower than the touch at every D; the v1 gain was a reconstruction artefact)"},
        {"id": "H124", "family": "price", "description": "With the wallet's own value V known, a per-order rule reaches 0.80 within one tick (slot choice is predictable).", "validate_metrics": {"adds_price_eq_V": 0.625, "adds_lgbm_loeo": 0.75, "fills_price_eq_V": 0.708}, "verdict": "rejected (oracle ceiling 0.71-0.75): per-order price item structurally capped"},
        {"id": "H125", "family": "price", "description": "A point-in-time own-state anchor (its level revealed on chain) is the best examinable price rule.", "validate_metrics": {"own_pit": 0.28, "last_print": 0.305, "union": 0.418}, "verdict": "rejected (below the last print)"},
        {"id": "H126", "family": "price", "description": "Synchronous fast-maker re-pricings share the wallet's increment (a shared value product).", "validate_metrics": {"corr": 0.28, "null_p50": 0.276, "p": 0.36}, "verdict": "rejected historically (own model by the pre-registered thresholds); live uncensored step pending"},
        {"id": "H127", "family": "outcome", "description": "The outcome item survives public latency: its decisions delayed by L keep the per-market correlation >= 0.5.", "validate_metrics": {"maker_delay_2s_real_taker": [0.697, 0.624], "taker_lag_T_lo_50ms": [0.452, 0.371], "taker_lag_T_lo_2s": [0.431, 0.404], "taker_lag_T_hi_2s": [0.709, 0.635], "post_match_residual_median": 0.0}, "verdict": "maker timing not binding; the take is binding on the observed book (T_lo): rejected for any examinable public-lag rule"},
    ])
    S["iterations"].append({"n": 11, "minutes": MINUTES, "best_validate_score": 0.8834,
        "paradigm": "second-venue data on chain (SX Bet fills decoded from SX Rollup calldata), the uncensored own-add unit with the wallet's value known (oracle slot ceiling) and a freshness-filtered public touch on the raw book, and a decode-independent outcome latency bound (own decisions delayed in the validated engine, stale-remainder survival on the recorded book)",
        "families": ["SX Bet on-chain second venue (X145)", "point-in-time own-state anchors (X152)", "fresh / identity-filtered touch on the raw BUILD-live book (X153)", "per-order slot ceiling with V known (X150)", "shared increments with the fast makers vs a shift null (X154 historical)", "outcome latency bound: maker delay and taker lag bounds in the validated engine (X155 / X149 step 1)", "stale-remainder survival on the recorded book (X149 step 2)", "class-wise knockout of the own maker record (X151)", "pre-game levels vs Polymarket's price (X144 step 2, Polymarket half)", "build fingerprints on the 10-31 development blocks (X156)", "Thunderpick recorder v2: pre-game line, per-match cadence, coverage fields (X144 / X148)"]})
else:
    for it in S["iterations"]:
        if it.get("n") == 11:
            it["minutes"] = MINUTES
S["next_steps"] = [
    "Development blocks with traded matches (11-01 06-12 from ~08:10 UTC; 11-02 00-06 with IEM): X133 / X144 tests on tommy_tp_odds2 (B vs P cadence, pre-game U line vs its first quotes, quiet-class event-time test, shared-vendor cross-correlation), X118 on tommy_dota_rt, X154 step 2 and X146 on the books, X156 per-title scoring, X98 pool.",
    "Re-fit the taker-size and merge-law constants on BUILD-live before any future-block exam (X156).",
    "Offline: X157 (exchange-wide disruption list from public tapes), X132 with X118.",
    "Ask the user: demos (X122 / X37), Dota replays (X129 step 2), PandaScore token (X55), HLTV page checks (X64), the Internet Archive route (X147), stream / chat routes (X4 / X22 / X53), direct bookmaker probes (X48 b), z3 for X96.",
    "Pivot rule: iterations 9-11 each moved the primary metric by < 0.01, so iteration 12 must pivot (the Thunderpick valuation test on development blocks is the planned new-data pivot).",
]
S["target_metrics_notes"]["iteration_11"] = ("No rule change; target_metrics unchanged (v5). Measured bounds: price per order capped at about 0.71-0.75 even with the wallet's own value known (X150); "
    "the best examinable historical anchor stays the last print (0.305), point-in-time own state 0.280 (X152); outcome at public lag of the take <= 0.50 / 0.41 on the observed record (X155 / X149).")
S["status"] = "continue"
S["wall_reason"] = None
S["updated"] = int(time.time())
json.dump(S, open(WS / "state.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("state written; open:", [k for k, x in S["catalog"].items() if x.get("status") == "open"])
