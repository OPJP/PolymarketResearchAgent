"""Iteration 11 state.json update: catalog X144-X157 (iteration-10 panel), statuses of tested items, components with tags,
strategy statement, live lab, hypotheses, iteration entry. Reads the iteration-11 result files; the rule (v5) is unchanged."""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
WS = ROOT / "research/reverse_engineering/tommy-cs2-maker"
RES = WS / "results"
S = json.load(open(WS / "state.json", encoding="utf-8"))


def rj(n):
    p = RES / n
    return json.load(open(p, encoding="utf-8")) if p.exists() else None


pit, ft, sc, sx, pg, fp, si, lb = (rj("pit_anchors.json"), rj("fresh_touch_v2.json"), rj("slot_ceiling.json"),
                                    rj("sx_secondvenue.json"), rj("pregame_levels.json"), rj("fingerprints_dev.json"),
                                    rj("shared_increment.json"), rj("latency_bound.json"))
cat = S["catalog"]
NOW = int(time.time())


def lbtxt():
    if not lb:
        return "latency_bound.json missing"
    out = []
    for sp in ("BUILD", "VALIDATE"):
        r = lb[sp]
        cells = []
        for L in (0, 100, 250, 500, 1000, 2000):
            c = r[f"L{L}"]
            cells.append(f"L={L} ms: A+real {c['A_plus_real_taker'][0]}/{c['A_plus_real_taker'][1]}, A+T_lo {c['A_plus_T_lo'][0]}/{c['A_plus_T_lo'][1]}, A+T_hi {c['A_plus_T_hi'][0]}/{c['A_plus_T_hi'][1]}, A alone {c['A_alone'][0]}/{c['A_alone'][1]}, A pair cost {c['A_pair_cost_median']}")
        out.append(f"{sp} ({r['markets']} markets): " + "; ".join(cells))
    return " | ".join(out)


new = {
    "X144": {"status": "open", "source": "information panel P1 (iter 10): Thunderpick as the valuation, tested pre-game, on quiet orders and on the shared-vendor branch (strong form of X133 / X48a)",
             "evidence": "Steps 1-2 implemented: own recorder v2 tommy_tp_odds2 (code/iter11/tp_odds_recorder_v2.py; worker pid 27892, launcher 24512, started 1793510977 = 11-01 05:29 UTC, hard stop 11-03 00:00 UTC, 150 MB) records the live index (B, every 3 s), the UPCOMING index with start < now + 90 min (U, every 30 s: the pre-game line) and the per-match object of matched development-unit in-play matches (P, round-robin every 2 s) for the cadence comparison; v1 (tommy_tp_odds, pid 31860) stopped 05:30 UTC before any development block, and tp_odds_analysis.py now reads both feeds (plumbing only). Probe (structure only): bo3 answers both endpoints with cache-control public max-age=15 (cf DYNAMIC); 29 of 100 upcoming CS2 matches carry bet_updates (2 of 6 starting within 6 h). Polymarket half of step 2 run on 16-22 Oct (pregame_levels.json): its filled maker orders signed BEFORE the scheduled start sit within one tick of the last public print 0.493 / 0.389 (BUILD 145 orders, 22 markets / VALIDATE 143, 21) vs 0.363 / 0.371 in play 10-60 min, offsets p10/p50/p90 -5/-1/+1c and -7/-2/+1c (in play -8/-1/+4c): pre-game it bids 1-2c under Polymarket's own price, closer than in play, so no large private prior is visible before game state exists. Tests (1)-(5) need a development block with a matched traded match (first expected 11-01 08-12 UTC). | Tests (1)-(5) and verdicts frozen in code/iter11/tp_valuation_tests.py (~06:15 UTC 11-01, before any development record of tommy_tp_odds2; dry run 0 records)."},
    "X145": {"status": "tried", "source": "information panel P2 (iter 10): second venues that settle on chain (SX Bet via the SX Rollup explorer, Azuro on Polygon)",
             "evidence": None},
    "X146": {"status": "open", "source": "information panel P3 (iter 10): Polymarket's book websocket as the public echo of Feed P, an executable protected maker for the outcome item",
             "evidence": "Not run this iteration. Bound measured instead (X155): even the wallet's OWN maker orders, delayed, keep the per-market correlation only with its real taker leg; the protected public maker must also reach pair cost <= 0.99 on VALIDATE-live (books start 10-31). Calibration on BUILD-live (echo latency of the first non-own cancel after P4e / member messages, false alarms) and the replay on VALIDATE-live remain."},
    "X147": {"status": "open", "source": "information panel P4 (iter 10): Internet Archive copies of HLTV and Liquipedia pages (archived bookmaker lines, data-partner fields)",
             "evidence": "Needs the user's clearance (the panel's condition: the original sites block automated access); asked in the return. Partial substitute run: the pre-game Polymarket half (X144 step 2) shows its opening bids 1-2c under Polymarket's own last print."},
    "X148": {"status": "open", "source": "information panel P5 (iter 10): bo3 live-coverage fields and wss://live.bo3.gg when a wallet match turns on",
             "evidence": "Step 1 done: recorder v2 stores live_coverage / live_coverage_source / live_coverage_advantage (lc / lcs / lca) in every record. The socket subscription is triggered only if a traded development-unit match shows coverage (none of the 71 + 201 development matches checked so far had it)."},
    "X149": {"status": "open", "source": "mechanics panel P1 (iter 10): the take and the repair at public sub-second lag (stale-remainder survival curve, three-leg replica)",
             "evidence": None},
    "X150": {"status": "tried", "source": "mechanics panel P2 (iter 10): the per-order price ceiling with the wallet's own value known (ladder-slot account)",
             "evidence": None},
    "X151": {"status": "open", "source": "mechanics panel P3 (iter 10): class-wise knockout of the wallet's own record (outcome localization)",
             "evidence": "Not run this iteration (engine time went to X155). Planned on the same engine with ledger_rows_iter10.cls plus the endgame class."},
    "X152": {"status": "tried", "source": "mechanics panel P4 (iter 10): examiner-proof wall account, every own-state anchor re-derived point-in-time",
             "evidence": None},
    "X153": {"status": "tried", "source": "assumptions panel P1 (iter 10): freshness- and identity-filtered touch as the public form of V",
             "evidence": None},
    "X154": {"status": "open", "source": "assumptions panel P2 (iter 10): invisible messages, maker-synchrony clock and a shared-increment test",
             "evidence": None},
    "X155": {"status": "tried", "source": "assumptions panel P3 (iter 10): the outcome item's latency bound on the wallet's own decisions",
             "evidence": None},
    "X156": {"status": "open", "source": "assumptions panel P4 (iter 10): score the forward lots by title; Dota first on VALIDATE-live; build fingerprints before a future exam",
             "evidence": None},
    "X157": {"status": "open", "source": "assumptions panel P5 (iter 10): operational continuity across exchange pauses (10-29), decided on development analogues",
             "evidence": "Partial (from iteration 7, X95): in 16-22 Oct the merge loop has exactly 6 phase breaks, all overnight (99.2% of 738 pass pairs phase-continuous), so no intraday session break occurred in development. Not built yet: the list of exchange-wide disruptions in development (zero-print minutes across in-play markets, post-only windows, status notes) and the pre-registered evaluate() reporting for events after a known pause."},
}
if pit:
    b, v = pit["BUILD"], pit["VALIDATE"]
    new["X152"]["evidence"] = (f"pit_anchors.json (code/iter11/pit_anchors.py). Within one tick, BUILD / VALIDATE: last print {b['last_print'][0]} / {v['last_print'][0]}; "
                               f"fill-selected own previous level (iteration 10) {b['own_prev_fill_selected'][0]} / {v['own_prev_fill_selected'][0]}; POINT-IN-TIME own level (its order on the token whose first fill was on chain latest before signing) {b['own_pit_first_fill'][0]} / {v['own_pit_first_fill'][0]} (last-fill version {b['own_pit_last_fill'][0]} / {v['own_pit_last_fill'][0]}); "
                               f"fill-selected predecessor with same-block co-fills excluded {b['own_prev_no_same_block'][0]} / {v['own_prev_no_same_block'][0]}; oracle union PIT own + last print {b['oracle_union_pit_and_last']} / {v['oracle_union_pit_and_last']} (fill-selected union {b['oracle_union_fill_selected_and_last (iteration 10, 0.599)']} / {v['oracle_union_fill_selected_and_last (iteration 10, 0.599)']}). "
                               "Persistence by gap, VALIDATE, fill-selected vs PIT: 2-10 s 0.591 vs 0.448, 10-60 s 0.516 vs 0.365, > 60 s 0.233 vs 0.193 (0-2 s has no PIT row: no fill can be on chain within 2 s). Signature if true holds: no own-state anchor the examiner can compute beats the last print; the 0.500 / 0.599 / 0.716 citations are replaced (kept as fill-selected footnotes).")
if ft:
    f, a = ft["fill"], ft["add"]
    new["X153"]["evidence"] = (f"fresh_touch_v2.json (code/iter11/fresh_touch_v2.py, raw tommy_cs2_near book with snapshots, BUILD-live 10-31 14:50-18:00). Touch (own size removed): filled orders {f['touch_all']} (n {f['n']}), validated own adds {a['touch_all']} (n {a['n']}). "
                               f"FT_D (best level with a non-own change in [t - D, t - 20 ms], fallback touch) never beats it: fills {min(x['within_tick'] for x in f['by_D_all'].values())}-{max(x['within_tick'] for x in f['by_D_all'].values())}, adds {min(x['within_tick'] for x in a['by_D_all'].values())}-{max(x['within_tick'] for x in a['by_D_all'].values())} over D = 0.25..60 s; on the covered rows the touch is higher at every D. "
                               f"D and offset fitted on the first half, second half: fills FT {f['fitted']['second_half']['FT']} vs touch {f['fitted']['second_half']['touch']} (event-bootstrap gain CI {f['fitted']['second_half']['gain_ci95_event_boot']}), adds {a['fitted']['second_half']['FT']} vs {a['fitted']['second_half']['touch']} ({a['fitted']['second_half']['gain_ci95_event_boot']}); new-top adds {a['fitted']['second_half']['new_top_FT']} vs {a['fitted']['second_half']['new_top_touch']}. "
                               "Signature if false holds (FT <= touch + 0.03 for every D): V is not the fast receivers' fresh levels. Version 1 on level_events_dev (no snapshots) showed a spurious +0.04..+0.14 gain because its touch missed pre-window levels (0.20 vs 0.45): an artefact, kept in fresh_touch.json as a warning. Identity form not run: 717 calldata-linked non-own adds in 3 h over 6 books (too sparse to anchor).")
if sc:
    a, f = sc["add"], sc["fill"]
    new["X150"]["evidence"] = (f"slot_ceiling.json (code/iter11/slot_ceiling.py, BUILD-live raw book, validated own label). V oracle = its own top after the burst: adds (n {a['V_after']['n']}) slot shares 0: {a['V_after']['slot_dist'].get('0')}, -1: {a['V_after']['slot_dist'].get('-1')}, -2: {a['V_after']['slot_dist'].get('-2')}, -3: {a['V_after']['slot_dist'].get('-3')}, -4: {a['V_after']['slot_dist'].get('-4')}; "
                               f"price = V within one tick {a['V_after']['within_tick_V_itself']}, LightGBM slot classifier on own-ladder + book state (leave-one-event-out) {a['V_after']['within_tick_lgbm_loeo']}; filled orders (n {f['V_after']['n']}) {f['V_after']['within_tick_V_itself']} (LightGBM {f['V_after']['within_tick_lgbm_loeo']}, small n). "
                               f"V = its own top BEFORE the decision: adds {a['own_top']['within_tick_constant_mode']} (constant +1c slot) / LightGBM {a['own_top']['within_tick_lgbm_loeo']}; fills {f['own_top']['within_tick_constant_mode']} / {f['own_top']['within_tick_lgbm_loeo']}. Touch on the same rows {a['touch_within_tick']}. "
                               "Signature if true holds: even with its own value known exactly, no rule found reaches 0.80 per order (ceiling about 0.71-0.75); the per-order price item is structurally capped for this multi-slot ladder, and the decision unit that a value decode could pass is the top level (V itself, 0.63-0.71). Oracle ceiling, never a rule.")
if sx:
    w, ov, cmp_ = sx["sx_week"], sx["overlap"], sx.get("inplay_fill_comparison", {})
    new["X145"]["evidence"] = (f"sx_fetch.py / sx_analysis.py, sx_secondvenue.json. Verified: SX Rollup Blockscout API key-free; exchange proxy 0x890482680C3a0116aBB003B17e7D694D13a6c1eB (EIP-1967, implementation 0x4336940c... initialized 10-13, unverified; the verified FillOrder ABIs' OrderFill topic is not emitted after the upgrade); fill txs (selector 0x468e5f52) decoded from calldata (maker, fill, totalBetSize, percentageOdds, isMakerBettingOutcomeOne, validated on a sample); api.sx.bet/markets/find answers key-free for finished markets. "
                               f"16-22 Oct (blocks 10,543,166-10,686,804, all before H): {w['fill_txs_all_sports']} fill txs on {w['markets_all_sports']} markets, but only {w['esports_markets']} esports markets ({w['esports_fill_txs']} fill txs) and {w['cs2_markets']} CS2 markets ({w['cs2_fill_txs']} fill txs, {w['cs2_fill_txs_inplay']} in play, ${w['cs2_fill_usdc']}). "
                               f"{ov['wallet_events_with_sx_market']} of the wallet's {ov['wallet_events_total']} traded events have an SX market; in play they hold 0-22 fill txs per ~3-h match (about 1 per hour, the panel's density bar is 1 per minute). "
                               f"On the {cmp_.get('n_fills')} matched in-play maker fills: SX implied probability - Polymarket last print {cmp_.get('sx_minus_pm_last')}, - the wallet's latest bid on the token {cmp_.get('sx_minus_wallet_bid_tok0')}: SX quotes a wide margin above Polymarket and tracks Polymarket's print (SD 3.6c) more than the wallet's level (SD 7.1c). "
                               "Signature if false holds: SX in-play fills are sparse and follow Polymarket; the SX branch of the second-venue class is closed (also closes X73's chain half). Azuro: X41 stays infeasible (subgraph DNS failure); not re-run.")
if fp:
    new["X156"]["evidence"] = (f"Step 3 (fingerprints) run on the 10-31 development blocks (fingerprints_dev.json; calldata_dev signing 10-31 00:00-18:00, 519 wallet orders): band [0.05, 0.95] holds (0 outside), whole cents 100%, Dota maker 10 shares {fp['maker_size']['dota2']['share_10']} (n {fp['maker_size']['dota2']['n']}); CS2 maker 100-share share {fp['maker_size']['cs2']['share_100']} (n {fp['maker_size']['cs2']['n']}; 88-92% on 16-22 Oct), the rest being the known event-wide size ramps (54-87 shares in 3 of its 4 CS2 events; 36% of events before), so the maker size mechanism is unchanged; CHANGED: CS2 taker median {fp['taker_size']['cs2']['median']} shares with no 1000 / 2000 caps (470 and 14.4% before); merge loop: base period holds on single-merge passes (residual 0.2 s) but only {fp['merge_loop']['share_abs_residual_le_10s']} of passes within 10 s of the 300.22 + 7.28 x merges law (99.2% before; residual median {fp['merge_loop']['residual_s_median']} s, one skipped pass), so the per-merge increment drifted. The +51-ms P4e lag is not checkable there (no P4e take in the dev-block calldata of its markets). "
                               "Steps 1-2 (per-title scoring on VALIDATE-live) wait for development blocks with traded matches. Consequence for exams: the taker-size and merge-law constants must be re-fitted on BUILD-live before a future-block exam; maker size mechanism, price band and Dota size are stable.")
if si:
    al, qu = si["all"], si["quiet"]
    new["X154"]["evidence"] = (f"Steps 3-4, historical (shared_increment.json, code/iter11/shared_increment.py): {al['pairs']} of the wallet's 24,180 filled maker orders have a filled BUY order of one of the six fast makers on the same token within +-60 ms; corr(dV_wallet, dV_peer) {al['real']['corr']} (sign agreement {al['real']['sign_agree']}, within 1c {al['real']['within_1c']}), against a shift null (the peer's order 2-30 s earlier) of {al['null_corr_p50_p95'][0]} (p95 {al['null_corr_p50_p95'][1]}, p {al['p_null_ge_real']}); quiet class {qu['real']['corr']} vs null {qu['null_corr_p50_p95'][0]} (p {qu['p_null_ge_real']}); per maker 0.25-0.40. "
                               f"Pre-registered verdict: {si['verdict_preregistered']} (corr <= 0.3, and not above the shifted control): synchronous re-pricings do not share an increment beyond the common price path. The panel's 0.56-0.58 (n 42-53, a -1..-3 s control) does not replicate at n 1,226 with the shift null. Caveat: dV between filled orders spans their gaps (censoring). Step 2 (live, uncensored cross-book synchrony) waits for VALIDATE-live.")
if lb:
    new["X155"]["evidence"] = "latency_bound.json (code/iter11/latency_bound.py, validated X57 engine set A shifted by L; taker leg real or delayed with two bounds). " + lbtxt()
    new["X149"]["evidence"] = ("Step 1 (historical feasibility) run inside X155's grid (latency_bound.json): the take re-matched at its real match time + L with a lower bound (only liquidity <= its limit that public BUY takers consumed in [m + L, m + L + 30 s]) and an upper bound (its fill minus followers' consumption in (m, m + L], no maker cancels). "
                               + lbtxt() + " Steps 2-3 (survival curve on the recorded books, executable replica) wait for VALIDATE-live.")
for k, v in new.items():
    if k in cat:
        cat[k].update({kk: vv for kk, vv in v.items() if vv is not None})
    else:
        cat[k] = v
cat["X73"]["status"] = "tried"
cat["X73"]["evidence"] = str(cat["X73"].get("evidence", "")) + " | Iteration 11: the chain half is done under X145 (SX Rollup explorer, exchange proxy found and decoded): 11 CS2 markets / 63 fill txs in all of 16-22 Oct; sparse and Polymarket-following."
cat["X133"]["evidence"] = str(cat["X133"].get("evidence", "")) + " | Iteration 11: v1 stopped 11-01 05:30 UTC (before any development block); recording continues in tommy_tp_odds2 (v2, X144) with the same B records; tp_odds_analysis.py reads both feeds."
S["catalog"] = cat
json.dump(S, open(WS / "state.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("catalog", len(cat), {s: sum(1 for x in cat.values() if x.get("status") == s) for s in ("tried", "open", "ruled_out", "not_applicable", "infeasible")})
print("open", [k for k, x in cat.items() if x.get("status") == "open"])
